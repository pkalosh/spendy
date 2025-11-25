import json
import logging
import uuid
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden,HttpResponse,HttpResponseRedirect,HttpResponseNotAllowed
from django.db import transaction
from django.views.decorators.http import require_POST,require_GET
from django.urls import reverse
from django.utils.decorators import method_decorator
from .models import Expense, Event,BatchPayments, Operation,InventoryItem, InventoryTransaction, Supplier, SupplierInvoice, InvoiceItem, ExpenseGroup, CategoryBase, ExpenseCategory, EventCategory, OperationCategory,ExpenseRequestType, Activation, ActivationCategory
from .forms import (
        ExpenseRequestForm,
        ExpenseApprovalForm,
        PaymentForm, 
        EventExpenseForm, 
        OperationExpenseForm,
        ActivationExpenseForm,
        InventoryItemForm,
        InventoryTransactionForm,
        SupplierForm,
        SupplierInvoiceForm,
        InvoiceItemForm,
        )
from wallet.models import Transaction, CompanyKYC, Wallet,TransactionFee,Client,StaffProfile
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth, TruncYear
from datetime import datetime, timedelta
import csv
from django.http import Http404
import pandas as pd
import io
from io import StringIO
from django.core.paginator import Paginator
from collections import defaultdict
from datetime import datetime, timedelta
import calendar
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from userauths.models import User
from wallet.utility import NotificationService,  notify_expense_workflow
from wallet.models import Notification
from wallet.views import (
    initiate_b2c_payment,
    initiate_b2b_payment    
)
from wallet.mpesa_service import MpesaDaraja
from django.utils.crypto import get_random_string

logger = logging.getLogger(__name__)



def calculate_transfer_fee(payment_method, amount):
    """Calculate transfer fees based on payment method and amount"""
    amount = Decimal(str(amount))
    
    if payment_method == 'till_number':
        # KES 20 flat or 1.5% (whichever is higher)
        flat_fee = Decimal('20.00')
        percentage_fee = amount * Decimal('0.015')
        return max(flat_fee, percentage_fee)
    
    elif payment_method == 'paybill_number':
        # KES 30 flat or 2% (whichever is higher)
        flat_fee = Decimal('30.00')
        percentage_fee = amount * Decimal('0.02')
        return max(flat_fee, percentage_fee)
    
    elif payment_method == 'mpesa_number':
        # Tiered fee structure for M-Pesa numbers
        if amount <= 1000:
            return Decimal('15.00')
        elif amount <= 10000:
            return Decimal('30.00')
        else:
            return Decimal('50.00')
    
    return Decimal('0.00')
def format_phone_number(phone_number):
    """Format phone number to M-Pesa format (254XXXXXXXXX)"""
    
    # Remove any non-digit characters
    phone = ''.join(filter(str.isdigit, phone_number))
    
    # Handle different formats
    if phone.startswith('254'):
        return phone
    elif phone.startswith('0'):
        return '254' + phone[1:]
    elif len(phone) == 9:
        return '254' + phone
    else:
        raise ValueError(f"Invalid phone number format: {phone_number}")
def is_admin(user):
    """Check if user is admin either through Django admin or through StaffProfile"""
    if user.is_staff or user.is_superuser:
        return True
    
    # Check if user has StaffProfile with is_admin=True
    try:
        return user.staffprofile.role.is_admin
    except (AttributeError, Exception):
        return False

@login_required
def dashboard(request):
    """Display dashboard with wallets, expenses and transactions"""
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    
    # Get wallets
    if company:
        wallets = Wallet.objects.filter(company=company)
    else:
        wallets = Wallet.objects.filter(owner=user)
    
    # Get expenses
    if is_admin(user):
        # Admins see all expenses for their company
        if company:
            expenses = Expense.objects.filter(company=company).order_by('-created_at')
        else:
            expenses = Expense.objects.all().order_by('-created_at')
    else:
        # Regular users see only their expenses
        expenses = Expense.objects.filter(created_by=user).order_by('-created_at')
    
    pending_expenses = expenses.filter(approved=False, declined=False)
    approved_expenses = expenses.filter(approved=True)
    declined_expenses = expenses.filter(declined=True)
    
    # Initialize forms
    expense_form = ExpenseRequestForm(user=user, company=company)
    payment_form = PaymentForm(user=user)
    
    context = {
        'wallets': wallets,
        'pending_expenses': pending_expenses,
        'approved_expenses': approved_expenses,
        'declined_expenses': declined_expenses,
        'expense_form': expense_form,
        'payment_form': payment_form,
        'is_admin': is_admin(user),
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def submit_expense(request):
    try:
        company = request.user.staffprofile.company
    except AttributeError:
        messages.error(request, "Company profile not found.")
        return redirect('wallet:staff-dashboard')

    if request.method == 'POST':
        expense_form = ExpenseRequestForm(request.POST, request.FILES, company=company)
        request_type_id = request.POST.get('request_type')
        if expense_form.is_valid():
            expense = expense_form.save(commit=False)
            expense.created_by = request.user
            expense.company = company

            try:
                request_type = ExpenseRequestType.objects.get(id=request_type_id, company=company, is_active=True)
                if 'event' in request_type.name.lower():
                    wallet = Wallet.objects.filter(company=company, wallet_type='EVENT').first()
                elif 'operation' in request_type.name.lower():
                    wallet = Wallet.objects.filter(company=company, wallet_type='OPERATIONS').first()
                elif 'activation' in request_type.name.lower():
                    wallet = Wallet.objects.filter(company=company, wallet_type='ACTIVATION').first()
                else:
                    wallet = None
            except ExpenseRequestType.DoesNotExist:
                messages.error(request, f"Invalid request type selected.")
                return redirect('wallet:expense-requests')

            if not wallet:
                messages.error(request, f"No wallet found for request type '{request_type.name}'.")
                return redirect('wallet:expense-requests')

            expense.wallet = wallet
            expense.save()

            if expense.batch_disbursement_type and 'batch_file' in request.FILES:
                batch_file = request.FILES['batch_file']
                BatchPayments.objects.create(
                    expense=expense,
                    created_by=request.user,
                    file=batch_file,
                    company=company
                )

            notify_expense_workflow(expense=expense, action='created', send_sms=True)
            messages.success(request, "Expense request submitted successfully.")
            return redirect('wallet:expense-requests')
        else:
            messages.error(request, f"Please correct the errors below: {expense_form.errors}")
            # Retain form data for errors, but reset request_type
            expense_form = ExpenseRequestForm(
                company=company,
                initial={
                    'amount': request.POST.get('amount'),
                    'description': request.POST.get('description'),
                    'expense_category': request.POST.get('expense_category'),
                    'batch_disbursement_type': request.POST.get('batch_disbursement_type'),
                    'event': request.POST.get('event'),
                    'operation': request.POST.get('operation'),
                    'activation': request.POST.get('activation'),
                }
            )
    else:
        expense_form = ExpenseRequestForm(company=company)
        request_types = ExpenseRequestType.objects.filter(company=company, is_active=True)

    return render(request, 'users/staff/request.html', {
        'expense_form': expense_form,
        'request_types': request_types,
    })

@login_required
def download_batch_template(request):
    """Generate a downloadable CSV template for batch disbursements."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="batch_disbursement_template.csv"'

    writer = csv.writer(response)
    writer.writerow(['name', 'amount', 'mobile','id_number'])
    writer.writerow(['John Doe', '1000.00', '+254725797597', '12345678'])
    writer.writerow(['Jane Smith', '2000.00', '+254725797597', '87654321'])

    return response


# @login_required
# def event_operation(request):
#     if request.method == "POST":
#         form = EventExpenseForm(request.POST)
#         print(form)
#         if form.is_valid():
#             event = form.save(commit=False)
#             event.created_by = request.user
#             event.company = get_object_or_404(CompanyKYC, user=request.user)
#             event.save()
#             # Notify expense workflow
#             notify_expense_workflow(expense=event, action='created', send_sms=True)
#             messages.success(request, 'Event created successfully.')
#             return redirect('expenses:expense')
#         else:
#             messages.error(request, 'Error creating event.')
#     return redirect('expenses:expense')


@login_required
def create_event(request):
    if request.method == "POST":
        form = EventExpenseForm(request.POST)
        print(form)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.company = get_object_or_404(CompanyKYC, user=request.user)
            event.save()
            # Notify expense workflow
            notify_expense_workflow(expense=event, action='created', send_sms=True)
            messages.success(request, 'Event created successfully.')
            return redirect('expenses:expense')
        else:
            messages.error(request, 'Error creating event.')
    return redirect('expenses:expense')


@login_required
def event_operation(request):
    if request.method == "POST":
        request_type = request.POST.get('request_type')
        
        try:
            company = get_object_or_404(CompanyKYC, user=request.user)
            
            if request_type == 'event':
                # Validate required fields
                name = request.POST.get('event_name', '').strip()
                if not name:
                    raise ValidationError("Event name is required")
                    
                # Get and validate category
                try:
                    category_id = request.POST.get('event_category')
                    if not category_id:
                        raise ValidationError("Event category is required")
                    category = EventCategory.objects.get(id=category_id)
                except (EventCategory.DoesNotExist, ValueError):
                    raise ValidationError("Invalid event category")

                # Get and validate client (optional)
                client = None
                client_id = request.POST.get('event_client')
                if client_id:
                    try:
                        client = Client.objects.get(id=client_id)
                    except (Client.DoesNotExist, ValueError):
                        raise ValidationError("Invalid event client")

                # Validate dates
                start_date = request.POST.get('event_start_date')
                end_date = request.POST.get('event_end_date')
                if not start_date or not end_date:
                    raise ValidationError("Start and end dates are required")
                
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    
                    if start_date_obj > end_date_obj:
                        raise ValidationError("End date must be after start date")
                except ValueError:
                    raise ValidationError("Invalid date format")
                
                # Validate budget
                budget = None
                budget_str = request.POST.get('event_budget')
                if not budget_str:
                    raise ValidationError("Event budget is required")
                
                try:
                    budget = Decimal(budget_str)
                    if budget < 0:
                        raise ValidationError("Budget cannot be negative")
                except (InvalidOperation, ValueError):
                    raise ValidationError("Invalid budget value")
                
                # Get other required fields
                project_lead = request.POST.get('event_project_lead', '').strip()
                if not project_lead:
                    raise ValidationError("Project lead is required")
                    
                location = request.POST.get('event_location', '').strip()
                if not location:
                    raise ValidationError("Location is required")
                
                # Handle budget file upload
                budget_file = request.FILES.get('event_budget_file')
                
                # Create and save event
                event = Event(
                    name=name,
                    category=category,
                    client=client,
                    company=company,
                    start_date=start_date,
                    end_date=end_date,
                    budget=budget,
                    budget_file=budget_file,
                    project_lead=project_lead,
                    location=location,
                    created_by=request.user
                )
                
                # Run model validation
                event.full_clean()
                event.save()
                
                messages.success(request, 'Event created successfully.')
                return redirect('wallet:expenses')
                
            elif request_type == 'operation':
                # Validate required fields
                name = request.POST.get('operation_name', '').strip()
                if not name:
                    raise ValidationError("Operation name is required")
                    
                # Get and validate category
                try:
                    category_id = request.POST.get('operation_category')
                    if not category_id:
                        raise ValidationError("Operation category is required")
                    category = OperationCategory.objects.get(id=category_id)
                except (OperationCategory.DoesNotExist, ValueError):
                    raise ValidationError("Invalid operation category")

                # Get and validate client (optional)
                client = None
                client_id = request.POST.get('operation_client')
                if client_id:
                    try:
                        client = Client.objects.get(id=client_id)
                    except (Client.DoesNotExist, ValueError):
                        raise ValidationError("Invalid operation client")

                # Validate budget
                budget = None
                budget_str = request.POST.get('operation_budget')
                if not budget_str:
                    raise ValidationError("Operation budget is required")
                
                try:
                    budget = Decimal(budget_str)
                    if budget < 0:
                        raise ValidationError("Budget cannot be negative")
                except (InvalidOperation, ValueError):
                    raise ValidationError("Invalid budget value")
                
                # Get project lead (required for operations)
                project_lead = request.POST.get('operation_project_lead', '').strip()
                if not project_lead:
                    raise ValidationError("Project lead is required")
                
                # Handle budget file upload
                budget_file = request.FILES.get('operation_budget_file')
                
                # Create and save operation
                operation = Operation(
                    name=name,
                    category=category,
                    client=client,
                    company=company,
                    budget=budget,
                    budget_file=budget_file,
                    project_lead=project_lead,
                    created_by=request.user
                )
                
                # Run model validation
                operation.full_clean()
                operation.save()
                
                messages.success(request, 'Operation created successfully.')
                return redirect('wallet:expenses')
                
            elif request_type == 'activation':
                # Validate required fields
                name = request.POST.get('activation_name', '').strip()
                if not name:
                    raise ValidationError("Activation name is required")
                    
                # Get and validate category
                try:
                    category_id = request.POST.get('activation_category')
                    if not category_id:
                        raise ValidationError("Activation category is required")
                    category = ActivationCategory.objects.get(id=category_id)
                except (ActivationCategory.DoesNotExist, ValueError):
                    raise ValidationError("Invalid activation category")

                # Get and validate client (optional)
                client = None
                client_id = request.POST.get('activation_client')
                if client_id:
                    try:
                        client = Client.objects.get(id=client_id)
                    except (Client.DoesNotExist, ValueError):
                        raise ValidationError("Invalid activation client")

                # Validate budget (optional for activations based on your model)
                budget = None
                budget_str = request.POST.get('activation_budget')
                if budget_str:
                    try:
                        budget = Decimal(budget_str)
                        if budget < 0:
                            raise ValidationError("Budget cannot be negative")
                    except (InvalidOperation, ValueError):
                        raise ValidationError("Invalid budget value")
                
                # Get project lead (optional for activations based on your model)
                project_lead = request.POST.get('activation_project_lead', '').strip()
                
                # Get description (optional)
                description = request.POST.get('activation_description', '').strip()
                
                # Handle budget file upload
                budget_file = request.FILES.get('activation_budget_file')
                
                # Create and save activation
                activation = Activation(
                    name=name,
                    category=category,
                    client=client,
                    company=company,
                    budget=budget,
                    budget_file=budget_file,
                    description=description,
                    project_lead=project_lead,
                    created_by=request.user
                )
                
                # Run model validation
                activation.full_clean()
                activation.save()
                
                messages.success(request, 'Activation created successfully.')
                return redirect('wallet:expenses')
            
            else:
                raise ValidationError("Invalid request type")
                
        except ValidationError as e:
            # Handle ValidationError properly
            if hasattr(e, 'message_dict'):
                # Field-specific errors
                error_messages = []
                for field, messages_list in e.message_dict.items():
                    for msg in messages_list:
                        error_messages.append(f"{field}: {msg}")
                error_message = "; ".join(error_messages)
            elif hasattr(e, 'messages'):
                # Multiple error messages
                error_message = "; ".join(e.messages)
            else:
                # Single error message
                error_message = str(e)
            
            messages.error(request, f'Validation Error: {error_message}')
            return redirect('wallet:expenses')
            
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {str(e)}')
            return redirect('wallet:expenses')
    
    # Handle GET request
    return redirect('wallet:expenses')

@login_required
def activation_expense_detail(request, pk):
    activation = get_object_or_404(Activation, pk=pk, company__user=request.user)
    # Add your expense detail logic here
    context = {
        'activation': activation,
        # Add other context variables as needed
    }
    return render(request, 'expenses/activation_detail.html', context)


def is_admin(user):
    # Replace with your logic to check if the user is an admin
    return user.is_staff or user.has_perm('expense.can_approve_expense')

@login_required
def expense_detail(request, id, item_type=None):
    user = request.user
    company = getattr(user, 'company', None) or getattr(user, 'companykyc', None)

    # Initialize context variables
    context = {
        'is_admin': is_admin(user),
        'user': StaffProfile.objects.filter(company=company),
        'expense_category_choices': ExpenseCategory.objects.filter(company=company, is_active=True).order_by('name'),
    }

    # Handle query parameters for expense filters
    expense_filters = {}
    if request.GET.get('expense_user'):
        expense_filters['created_by_id'] = request.GET['expense_user']
    if request.GET.get('expense_category'):
        expense_filters['expense_category_id'] = request.GET['expense_category']
    if request.GET.get('expense_status'):
        if request.GET['expense_status'] == 'pending':
            expense_filters['approved'] = False
            expense_filters['declined'] = False
        elif request.GET['expense_status'] == 'approved':
            expense_filters['approved'] = True
            expense_filters['declined'] = False
        elif request.GET['expense_status'] == 'declined':
            expense_filters['declined'] = True

    # Handle query parameters for transaction filters
    txn_filters = {}
    if request.GET.get('txn_user'):
        txn_filters['user_id'] = request.GET['txn_user']
    if request.GET.get('txn_status'):
        txn_filters['status'] = request.GET['txn_status']
    if request.GET.get('txn_date_from'):
        txn_filters['date__gte'] = request.GET['txn_date_from']
    if request.GET.get('txn_date_to'):
        txn_filters['date__lte'] = request.GET['txn_date_to']

    # Determine if we're looking at an event, operation, activation, or specific expense
    if item_type == 'event':
        # Try UUID first since your model likely uses UUIDField as primary key
        try:
            event = get_object_or_404(Event, id=id)
        except ValueError:
            # If UUID parsing fails, try string lookup
            try:
                event = get_object_or_404(Event, pk=id)
            except (Event.DoesNotExist, ValueError):
                return HttpResponse(f"Event with ID {id} not found.", status=404)

        if company and event.company != company:
            return HttpResponseForbidden("You don't have permission to view this event")

        expenses = Expense.objects.filter(event=event, **expense_filters)
        approved_expenses = expenses.filter(approved=True, declined=False)
        event_form = EventExpenseForm(instance=event)

        # Paginate expenses
        expense_paginator = Paginator(expenses, 10)
        expense_page_number = request.GET.get('page', 1)
        expenses_page = expense_paginator.get_page(expense_page_number)

        # Get transactions
        approved_paid_expenses = expenses.filter(approved=True, declined=False, paid=True)
        expense_transactions = []
        for expense in approved_paid_expenses:
            transactions = Transaction.objects.filter(expense=expense, **txn_filters)
            expense_transactions.extend(transactions)

        # Paginate transactions
        txn_paginator = Paginator(expense_transactions, 10)
        txn_page_number = request.GET.get('txn_page', 1)
        txn_page = txn_paginator.get_page(txn_page_number)

        expense_summary = {
            'pending': expenses.filter(approved=False, declined=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'approved': expenses.filter(approved=True, declined=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'declined': expenses.filter(declined=True).aggregate(Sum('amount'))['amount__sum'] or 0,
        }

        expense_categories = approved_expenses.select_related('expense_category').values(
            'expense_category__name'
        ).annotate(total=Sum('amount')).order_by('-total')

        total_amount = sum(cat['total'] for cat in expense_categories) if expense_categories else 0

        context.update({
            'item': event,
            'item_type': 'event',
            'expenses': expenses_page,
            'approved_expenses': approved_expenses,
            'expense_transactions': txn_page,
            'expense_summary': expense_summary,
            'expense_categories': expense_categories,
            'total_amount': total_amount,
            'event_form': event_form,
            'expense_query_string': request.GET.urlencode().replace('page=', ''),
            'txn_query_string': request.GET.urlencode().replace('txn_page=', ''),
        })

    elif item_type == 'operation':
        # Try UUID first since your model likely uses UUIDField as primary key
        try:
            operation = get_object_or_404(Operation, id=id)
        except ValueError:
            # If UUID parsing fails, try string lookup
            try:
                operation = get_object_or_404(Operation, pk=id)
            except (Operation.DoesNotExist, ValueError):
                return HttpResponse(f"Operation with ID {id} not found.", status=404)

        if company and operation.company != company:
            return HttpResponseForbidden("You don't have permission to view this operation")

        expenses = Expense.objects.filter(operation=operation, **expense_filters)
        approved_expenses = expenses.filter(approved=True, declined=False)
        operation_form = OperationExpenseForm(instance=operation)

        # Paginate expenses
        expense_paginator = Paginator(expenses, 10)
        expense_page_number = request.GET.get('page', 1)
        expenses_page = expense_paginator.get_page(expense_page_number)

        # Get transactions
        approved_paid_expenses = expenses.filter(approved=True, declined=False, paid=True)
        expense_transactions = []
        for expense in approved_paid_expenses:
            transactions = Transaction.objects.filter(expense=expense, **txn_filters)
            expense_transactions.extend(transactions)

        # Paginate transactions
        txn_paginator = Paginator(expense_transactions, 10)
        txn_page_number = request.GET.get('txn_page', 1)
        txn_page = txn_paginator.get_page(txn_page_number)

        expense_summary = {
            'pending': expenses.filter(approved=False, declined=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'approved': expenses.filter(approved=True, declined=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'declined': expenses.filter(declined=True).aggregate(Sum('amount'))['amount__sum'] or 0,
        }

        expense_categories = approved_expenses.select_related('expense_category').values(
            'expense_category__name'
        ).annotate(total=Sum('amount')).order_by('-total')

        total_amount = sum(cat['total'] for cat in expense_categories) if expense_categories else 0

        context.update({
            'item': operation,
            'item_type': 'operation',
            'expenses': expenses_page,
            'approved_expenses': approved_expenses,
            'expense_transactions': txn_page,
            'expense_summary': expense_summary,
            'expense_categories': expense_categories,
            'total_amount': total_amount,
            'operation_form': operation_form,
            'expense_query_string': request.GET.urlencode().replace('page=', ''),
            'txn_query_string': request.GET.urlencode().replace('txn_page=', ''),
        })

    elif item_type == 'activation':
        activation = None
        # Try UUID first since your model uses UUIDField as primary key
        try:
            activation = get_object_or_404(Activation, id=id)
            print(f"Found activation by UUID: {activation}")
        except ValueError:
            # If UUID parsing fails, try string lookup
            try:
                activation = get_object_or_404(Activation, pk=id)
            except (Activation.DoesNotExist, ValueError):
                return HttpResponse(f"Activation with ID {id} not found.", status=404)

        if company and activation.company != company:
            return HttpResponseForbidden("You don't have permission to view this activation")

        expenses = Expense.objects.filter(activation=activation, **expense_filters)
        approved_expenses = expenses.filter(approved=True, declined=False)
        activation_form = ActivationExpenseForm(instance=activation)

        # Paginate expenses
        expense_paginator = Paginator(expenses, 10)
        expense_page_number = request.GET.get('page', 1)
        expenses_page = expense_paginator.get_page(expense_page_number)

        # Get transactions
        approved_paid_expenses = expenses.filter(approved=True, declined=False, paid=True)
        expense_transactions = []
        for expense in approved_paid_expenses:
            transactions = Transaction.objects.filter(expense=expense, **txn_filters)
            expense_transactions.extend(transactions)

        # Paginate transactions
        txn_paginator = Paginator(expense_transactions, 10)
        txn_page_number = request.GET.get('txn_page', 1)
        txn_page = txn_paginator.get_page(txn_page_number)

        expense_summary = {
            'pending': expenses.filter(approved=False, declined=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'approved': expenses.filter(approved=True, declined=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'declined': expenses.filter(declined=True).aggregate(Sum('amount'))['amount__sum'] or 0,
        }

        expense_categories = approved_expenses.select_related('expense_category').values(
            'expense_category__name'
        ).annotate(total=Sum('amount')).order_by('-total')

        total_amount = sum(cat['total'] for cat in expense_categories) if expense_categories else 0

        context.update({
            'item': activation,
            'item_type': 'activation',
            'expenses': expenses_page,
            'approved_expenses': approved_expenses,
            'expense_transactions': txn_page,
            'expense_summary': expense_summary,
            'expense_categories': expense_categories,
            'total_amount': total_amount,
            'activation_form': activation_form,
            'expense_query_string': request.GET.urlencode().replace('page=', ''),
            'txn_query_string': request.GET.urlencode().replace('txn_page=', ''),
        })

    else:
        expense = None
        expense_queryset = Expense.objects.filter(id=id)
        if expense_queryset.exists():
            expense = expense_queryset.first()
        else:
            if hasattr(Expense, 'uuid'):
                expense_queryset = Expense.objects.filter(uuid=id)
                if expense_queryset.exists():
                    expense = expense_queryset.first()
        if not expense:
            return HttpResponse(f"Expense with ID {id} not found.", status=404)

        if not is_admin(user) and expense.created_by != user:
            return HttpResponseForbidden("You don't have permission to view this expense")

        event = expense.event if hasattr(expense, 'event') and expense.event else None
        operation = expense.operation if hasattr(expense, 'operation') and expense.operation else None
        activation = expense.activation if hasattr(expense, 'activation') and expense.activation else None
        
        related_expenses = Expense.objects.none()
        if event:
            related_expenses = Expense.objects.filter(event=event, **expense_filters).exclude(id=expense.id)
        elif operation:
            related_expenses = Expense.objects.filter(operation=operation, **expense_filters).exclude(id=expense.id)
        elif activation:
            related_expenses = Expense.objects.filter(activation=activation, **expense_filters).exclude(id=expense.id)

        # Paginate related expenses
        expense_paginator = Paginator(related_expenses, 10)
        expense_page_number = request.GET.get('page', 1)
        expenses_page = expense_paginator.get_page(expense_page_number)

        approval_form = ExpenseApprovalForm(instance=expense) if is_admin(user) and not expense.approved and not expense.declined else None
        payment_form = PaymentForm(user=user, company=company, initial={'expense': expense}) if expense.approved and not expense.declined else None

        expense_requests = []
        if event:
            expense_categories = Expense.objects.filter(
                event=event, approved=True, declined=False
            ).values('expense_category').annotate(amount=Sum('amount')).order_by('-amount')
            expense_requests = [{'category': cat['expense_category'], 'amount': cat['amount']} for cat in expense_categories]
        elif operation:
            expense_categories = Expense.objects.filter(
                operation=operation, approved=True, declined=False
            ).values('expense_category').annotate(amount=Sum('amount')).order_by('-amount')
            expense_requests = [{'category': cat['expense_category'], 'amount': cat['amount']} for cat in expense_categories]
        elif activation:
            expense_categories = Expense.objects.filter(
                activation=activation, approved=True, declined=False
            ).values('expense_category').annotate(amount=Sum('amount')).order_by('-amount')
            expense_requests = [{'category': cat['expense_category'], 'amount': cat['amount']} for cat in expense_categories]

        total_amount = sum(request['amount'] for request in expense_requests) if expense_requests else 0
        summaries = [{'status': 'Current Status', 'amount': expense.amount}]

        approved_requests = []
        if event:
            approved_requests = Expense.objects.filter(
                event=event, approved=True, declined=False
            ).values('created_by__first_name', 'created_by__last_name', 'expense_category', 'amount')
        elif operation:
            approved_requests = Expense.objects.filter(
                operation=operation, approved=True, declined=False
            ).values('created_by__first_name', 'created_by__last_name', 'expense_category', 'amount')
        elif activation:
            approved_requests = Expense.objects.filter(
                activation=activation, approved=True, declined=False
            ).values('created_by__first_name', 'created_by__last_name', 'expense_category', 'amount')

        formatted_approved_requests = [
            {
                'created_by': f"{req['created_by__first_name']} {req['created_by__last_name']}",
                'expense_type': req['expense_category'],
                'status': 'Approved',
                'amount': req['amount']
            } for req in approved_requests
        ]

        # Get transactions for the expense
        expense_transactions = Transaction.objects.filter(expense=expense, **txn_filters)
        txn_paginator = Paginator(expense_transactions, 10)
        txn_page_number = request.GET.get('txn_page', 1)
        txn_page = txn_paginator.get_page(txn_page_number)

        context.update({
            'expense': expense,
            'approval_form': approval_form,
            'payment_form': payment_form,
            'related_expenses': expenses_page,
            'event': event,
            'operation': operation,
            'activation': activation,
            'summaries': summaries,
            'expense_requests': expense_requests,
            'total_amount': total_amount,
            'approved_requests': formatted_approved_requests,
            'expense_transactions': txn_page,
            'expense_query_string': request.GET.urlencode().replace('page=', ''),
            'txn_query_string': request.GET.urlencode().replace('txn_page=', ''),
        })

    return render(request, 'expenses/expense_detail.html', context)

@login_required
def edit_item(request, id, item_type):
    """
    Handle editing of event or operation details (only dates can be modified)
    """
    user = request.user
    company = getattr(user, 'company', None) or getattr(user, 'companykyc', None)
    
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    
    if item_type == 'event':
        # Handle event editing
        event = None
        
        # Try direct id lookup first
        event_queryset = Event.objects.filter(id=id)
        if event_queryset.exists():
            event = event_queryset.first()
        else:
            # Check if the model has a uuid field
            if hasattr(Event, 'uuid'):
                event_queryset = Event.objects.filter(uuid=id)
                if event_queryset.exists():
                    event = event_queryset.first()
        
        if not event:
            messages.error(request, f"Event with ID {id} not found.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
            
        # Check permissions
        if company and event.company != company:
            messages.error(request, "You don't have permission to edit this event.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        
        # Check if user is admin or event creator
        if not is_admin(user) and event.created_by != user:
            messages.error(request, "You don't have permission to edit this event.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        
        # Get form data
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Validate dates
        if not start_date or not end_date:
            messages.error(request, "Both start date and end date are required for events.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if start_date_obj > end_date_obj:
                messages.error(request, "Start date cannot be later than end date.")
                return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
            
            # Update the event
            event.start_date = start_date_obj
            event.end_date = end_date_obj
            event.save()
            
            messages.success(request, "Event dates updated successfully.")
            return redirect('expense:event_expense_detail', id=str(id),item_type=item_type)
            
        except ValueError:
            messages.error(request, "Invalid date format.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
    
    elif item_type == 'operation':
        # Handle operation editing
        operation = None
        
        # Try direct id lookup first
        operation_queryset = Operation.objects.filter(id=id)
        if operation_queryset.exists():
            operation = operation_queryset.first()
        else:
            # Check if the model has a uuid field
            if hasattr(Operation, 'uuid'):
                operation_queryset = Operation.objects.filter(uuid=id)
                if operation_queryset.exists():
                    operation = operation_queryset.first()
        
        if not operation:
            messages.error(request, f"Operation with ID {id} not found.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
            
        # Check permissions
        if company and operation.company != company:
            messages.error(request, "You don't have permission to edit this operation.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        
        # Check if user is admin or operation creator
        if not is_admin(user) and operation.created_by != user:
            messages.error(request, "You don't have permission to edit this operation.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        
        # Get form data
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        try:
            from datetime import datetime
            
            # Update dates (they can be optional for operations)
            if start_date:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                operation.start_date = start_date_obj
            else:
                operation.start_date = None
                
            if end_date:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                operation.end_date = end_date_obj
            else:
                operation.end_date = None
            
            # Validate date logic if both dates are provided
            if operation.start_date and operation.end_date and operation.start_date > operation.end_date:
                messages.error(request, "Start date cannot be later than end date.")
                return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
            
            operation.save()
            
            messages.success(request, "Operation dates updated successfully.")
            return redirect('expense:operation_expense_detail', id=str(id), item_type=item_type)
            
        except ValueError:
            messages.error(request, "Invalid date format.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
    
    else:
        messages.error(request, "Invalid item type.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
@login_required
def approve_expense(request, expense_id):
    """Handle expense approval or rejection"""
    user = request.user
    
    # Check if user is admin
    if not is_admin(user):
        return HttpResponseForbidden("You don't have permission to approve expenses")
    
    expense = get_object_or_404(Expense, id=expense_id)
    
    if request.method == 'POST':
        form = ExpenseApprovalForm(request.POST, instance=expense)
        print(form)
        
        if form.is_valid():
            with transaction.atomic():
                approval = form.save(commit=False)
                
                # If not approved, mark as declined
                if not approval.approved:
                    approval.declined = True
                    messages.success(request, 'Expense request declined.')
                else:
                    messages.success(request, 'Expense request approved.')
                
                approval.approved_by = user
                approval.save()
                
                # Notify expense workflow
                notify_expense_workflow(expense, 'approved' if approval.approved else 'declined', approver_name=user.get_full_name())
                
                return redirect('expense:expense_detail', id=expense.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return redirect('expense:expense_detail', id=expense.id)


@login_required
def expense_approvals(request):
    company = request.user.companykyc
    query = request.GET.get('q', '')
    status = request.GET.get('status', 'all')
    active_tab = request.GET.get('tab', 'activation')

    # Base filter for company and search
    base_filter = Q(company=company)
    if query:
        base_filter &= (
            Q(created_by__first_name__icontains=query) |
            Q(created_by__last_name__icontains=query) |
            Q(description__icontains=query) |
            Q(event__name__icontains=query) |
            Q(operation__name__icontains=query) |  # Added operation name search
            Q(activation__name__icontains=query) |  # Added activation name search
            Q(expense_category__name__icontains=query)
        )

    def filter_expenses(base_queryset):
        if status == 'approved':
            return base_queryset.filter(approved=True)
        elif status == 'rejected':
            return base_queryset.filter(declined=True)
        elif status == 'pending':
            return base_queryset.filter(approved=False, declined=False)
        return base_queryset  # 'all'

    # Define base querysets without status filter, with prefetch for batchpayments_set
    base_activation = Expense.objects.filter(base_filter & Q(activation__isnull=False, approved=False, declined=False)) \
        .select_related('activation', 'expense_category', 'created_by', 'approved_by') \
        .prefetch_related('batchpayments_set') \
        .order_by('-created_at')
    
    base_event = Expense.objects.filter(base_filter & Q(event__isnull=False)) \
        .select_related('event', 'expense_category', 'created_by', 'approved_by') \
        .prefetch_related('batchpayments_set') \
        .order_by('-created_at')

    base_operation = Expense.objects.filter(base_filter & Q(operation__isnull=False)) \
        .select_related('operation', 'expense_category', 'created_by', 'approved_by') \
        .prefetch_related('batchpayments_set') \
        .order_by('-created_at')

    base_history = Expense.objects.filter(base_filter & (Q(approved=True) | Q(declined=True))) \
        .select_related('expense_category', 'created_by', 'approved_by', 'event', 'activation', 'operation') \
        .prefetch_related('batchpayments_set') \
        .order_by('-updated_at')

    # Compute tab-specific summaries
    activation_summary = {
        'total': Expense.objects.filter(base_filter & Q(activation__isnull=False)).count(),
        'all': Expense.objects.filter(base_filter & Q(activation__isnull=False)).count(),
        'pending': base_activation.count(),
        'approved': Expense.objects.filter(base_filter & Q(activation__isnull=False, approved=True)).count(),
        'rejected': Expense.objects.filter(base_filter & Q(activation__isnull=False, declined=True)).count(),
    }

    event_summary = {
        'total': base_event.count(),
        'all': base_event.count(),
        'pending': base_event.filter(approved=False, declined=False).count(),
        'approved': base_event.filter(approved=True).count(),
        'rejected': base_event.filter(declined=True).count(),
    }

    operation_summary = {
        'total': base_operation.count(),
        'all': base_operation.count(),
        'pending': base_operation.filter(approved=False, declined=False).count(),
        'approved': base_operation.filter(approved=True).count(),
        'rejected': base_operation.filter(declined=True).count(),
    }

    history_summary = {
        'total': base_history.count(),
        'all': base_history.count(),
        'pending': base_history.filter(approved=False, declined=False).count(),  # Should be 0
        'approved': base_history.filter(approved=True).count(),
        'rejected': base_history.filter(declined=True).count(),
    }

    # Apply status filter for listings
    activation_expenses = filter_expenses(base_activation)
    event_expenses = filter_expenses(base_event)
    operation_expenses = filter_expenses(base_operation)
    past_requests = filter_expenses(base_history)

    # Pagination
    activation_paginator = Paginator(activation_expenses, 10)
    event_paginator = Paginator(event_expenses, 10)
    operation_paginator = Paginator(operation_expenses, 10)
    history_paginator = Paginator(past_requests, 10)

    activation_page = request.GET.get('activation_page', 1)
    event_page = request.GET.get('event_page', 1)
    op_page = request.GET.get('op_page', 1)
    history_page = request.GET.get('history_page', 1)

    activation_requests = activation_paginator.get_page(activation_page)
    event_requests = event_paginator.get_page(event_page)
    operation_requests = operation_paginator.get_page(op_page)
    past_requests_page = history_paginator.get_page(history_page)

    context = {
        'activation_requests': activation_requests,
        'event_requests': event_requests,
        'operation_requests': operation_requests,
        'past_requests': past_requests_page,
        'query': query,
        'status': status,
        'active_tab': active_tab,
        'activation_summary': activation_summary,
        'event_summary': event_summary,
        'operation_summary': operation_summary,
        'history_summary': history_summary,
    }

    return render(request, 'expenses/approvals.html', context)


@require_POST
@login_required
def approve_expenses(request, expense_id):
    try:
        expense = get_object_or_404(Expense, id=expense_id)
        if expense.approved or expense.declined:
            return JsonResponse(
                {'error': 'This expense has already been processed.'},
                status=400
            )
        if expense.wallet.balance < expense.amount:
            return JsonResponse(
                {'error': 'Insufficient funds in the wallet.'},
                status=400
            )

        # Deduct from wallet (for both single and batch - batch total is expense.amount)
        expense.wallet.balance -= expense.amount
        expense.wallet.save()

        # Mark expense as approved (no batch processing here - preview only)
        expense.approved = True
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.declined = False
        expense.decline_reason = None
        expense.save()

        # Notification
        notify_expense_workflow(
            expense=expense, 
            action='approved', 
            approver_name=expense.approved_by.get_full_name()
        )

        message = 'Expense approved successfully.'
        return JsonResponse({
            'message': message,
            'approved_by_name': request.user.get_full_name() or request.user.username
        }, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Failed to approve expense: {str(e)}'}, status=500)


@login_required
def preview_expense_csv(request, expense_id):
    """
    View to preview CSV file associated with an expense via BatchPayments.
    """
    expense = get_object_or_404(Expense, id=expense_id)
    if not request.user.companykyc == expense.company:
        raise Http404("Permission denied")

    if not expense.batch_disbursement_type:
        return JsonResponse({'error': 'This is not a batch disbursement expense.'}, status=400)

    batch_payment = expense.batchpayments_set.first()
    if not batch_payment or not batch_payment.file:
        return JsonResponse({'error': 'No CSV file attached to this batch disbursement.'}, status=404)

    try:
        # Read CSV using pandas
        df = pd.read_csv(batch_payment.file.path)
        if df.empty:
            return JsonResponse({'error': 'CSV file is empty.'}, status=400)

        # Ensure required columns: name, amount, mobile, id_number
        required_cols = ['name', 'amount', 'mobile', 'id_number']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return JsonResponse({'error': f'Missing required columns: {", ".join(missing_cols)}'}, status=400)

        # Preview first 10 rows
        max_rows = 10
        preview_df = df[required_cols].head(max_rows)
        html_table = preview_df.to_html(
            classes='table table-striped table-sm table-responsive',
            index=False,
            escape=False,
            table_id='csv-preview-table'
        )

        # Add note if truncated
        total_rows = len(df)
        note = f"<p class='text-muted small mt-2'>Showing first {max_rows} of {total_rows} rows. <a href='{batch_payment.file.url}' target='_blank' class='btn btn-sm btn-outline-primary'>Download full CSV</a></p>" if total_rows > max_rows else "<p class='text-muted small mt-2'>Full CSV preview ({total_rows} rows).</p>"

        return JsonResponse({
            'success': True,
            'html': html_table + note,
            'total_rows': total_rows
        })
    except pd.errors.EmptyDataError:
        return JsonResponse({'error': 'CSV file is empty or invalid.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to parse CSV: {str(e)}'}, status=500)

@require_POST
@login_required
def decline_expense(request, expense_id):
    try:
        reason = request.POST.get("reason", "").strip()
        if not reason:
            return JsonResponse(
                {'error': 'Decline reason is required.'},
                status=400
            )
        expense = get_object_or_404(Expense, id=expense_id)
        if expense.approved or expense.declined:
            return JsonResponse(
                {'error': 'This expense has already been processed.'},
                status=400
            )
        expense.declined = True
        expense.declined_at = timezone.now()
        expense.decline_reason = reason
        expense.approved = False
        expense.approved_by = request.user
        expense.save()
        notify_expense_workflow(expense=expense, action='declined', approver_name=expense.approved_by.get_full_name())
        return JsonResponse({
            'message': 'Expense has been declined successfully.',
            'approved_by_name': request.user.get_full_name() or request.user.username
        }, status=200)
    except Exception as e:
        return JsonResponse({'error': f'Failed to decline expense: {str(e)}'}, status=500)

@require_POST
@login_required
def undo_expense_action(request, expense_id):
    try:
        expense = get_object_or_404(Expense, id=expense_id)
        if expense.paid:
            return JsonResponse(
                {'error': 'Cannot undo action on a paid expense.'},
                status=400
            )
        if not (expense.approved or expense.declined):
            return JsonResponse(
                {'error': 'This expense is already pending.'},
                status=400
            )
        # Reset to pending state
        action = 'approved' if expense.approved else 'declined'
        expense.approved = False
        expense.declined = False
        expense.approved_by = None
        expense.approved_at = None
        expense.declined_at = None
        expense.decline_reason = None
        expense.save()
        notify_expense_workflow(expense=expense, action='undo_' + action, approver_name=request.user.get_full_name())
        return JsonResponse({
            'message': 'Expense action undone successfully.',
            'approved_by_name': request.user.get_full_name() or request.user.username
        }, status=200)
    except Exception as e:
        return JsonResponse({'error': f'Failed to undo expense action: {str(e)}'}, status=500)


@login_required
def make_payment(request):
    """Handle payments for approved expenses via M-Pesa API with fee calculation, including batch payments"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    # Get user and company
    user = request.user
    company = getattr(user, 'company', None)
    if not company and hasattr(user, 'staffprofile'):
        company = getattr(user.staffprofile, 'company', None)

    if not company:
        return JsonResponse({
            'success': False, 
            'message': 'User is not associated with any company.'
        })

    try:
        # Extract and validate form data
        expense_id = request.POST.get('expense')
        payment_method = request.POST.get('payment_method')
        amount = request.POST.get('amount')
        batch_disbursement = request.POST.get('batch_disbursement', 'false').lower() == 'true'

        # Handle batch payment
        if batch_disbursement:
            if not expense_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Expense ID is required for batch payments.'
                })

            expense = get_object_or_404(Expense, id=expense_id)
            if not expense.batch_disbursement_type:
                return JsonResponse({
                    'success': False,
                    'message': 'This expense is not configured for batch disbursement.'
                })

            if not expense.approved or expense.declined:
                return JsonResponse({
                    'success': False,
                    'message': 'Payment can only be made for approved expenses.'
                })

            if expense.paid:
                return JsonResponse({
                    'success': False,
                    'message': 'This expense has already been paid.'
                })

            # Get batch payment file
            batch_payment = BatchPayments.objects.filter(expense=expense, company=company).first()
            if not batch_payment or not batch_payment.file:
                return JsonResponse({
                    'success': False,
                    'message': 'No batch payment file found for this expense.'
                })

            # Read and process CSV file
            results = []
            total_amount = Decimal('0.00')
            total_fees = Decimal('0.00')
            selected_wallet = expense.wallet
            valid_transactions = 0

            # Validate payment method for batch (only mpesa_number)
            if batch_payment:
                payment_method = 'mpesa_number'
                

            # Read CSV file
            with batch_payment.file.open('r') as file:
                # Read the file content
                csv_content = file.read()
                # Check if content is bytes and needs decoding
                if isinstance(csv_content, bytes):
                    csv_content = csv_content.decode('utf-8')
                # Ensure content is a string
                if not isinstance(csv_content, str):
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid CSV file content.'
                    })

                csv_reader = csv.DictReader(StringIO(csv_content))
                
                # Expected CSV headers: name, amount, mobile_number
                required_headers = {'name', 'amount', 'mobile_number'}
                if not all(header in csv_reader.fieldnames for header in required_headers):
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid CSV format. Required headers: name, amount, mobile_number.'
                    })

                # Check if CSV has at least one row
                rows = list(csv_reader)
                if not rows:
                    logger.error(f"Empty CSV file for expense #{expense.id}")
                    return JsonResponse({
                        'success': False,
                        'message': 'CSV file is empty. Please upload a valid file with at least one payment.'
                    })

                with transaction.atomic():
                    # Lock wallet for update
                    selected_wallet = Wallet.objects.select_for_update().get(pk=selected_wallet.pk)

                    for row in rows:
                        recipient_name = row['name'].strip()
                        mobile_number = row['mobile_number'].strip()
                        try:
                            row_amount = Decimal(row['amount'])
                            if row_amount <= 0:
                                raise ValueError("Amount must be positive")
                        except (InvalidOperation, ValueError) as e:
                            logger.warning(f"Invalid amount in CSV row: {row}, error: {str(e)}")
                            results.append({
                                'mobile_number': mobile_number,
                                'name': recipient_name,
                                'success': False,
                                'message': f'Invalid amount in CSV: {row.get("amount", "missing")}'
                            })
                            continue

                        # Normalize and validate phone number
                        normalized_number = mobile_number.replace('+', '').strip()
                        if normalized_number.startswith('254'):
                            normalized_number = normalized_number[3:]  # Remove 254 prefix
                        elif normalized_number.startswith('0'):
                            normalized_number = normalized_number[1:]  # Remove leading 0
                        formatted_phone = format_phone_number(normalized_number)
                        if not normalized_number.isdigit() or len(normalized_number) != 9:
                            logger.warning(f"Invalid mobile number in CSV row: {row}, normalized: {normalized_number}")
                            results.append({
                                'mobile_number': mobile_number,
                                'name': recipient_name,
                                'success': False,
                                'message': f'Invalid M-Pesa number: {mobile_number}. Must be a 9-digit number (e.g., 712345678) or start with 254.'
                            })
                            continue

                        # Calculate fee
                        transfer_fee = calculate_transfer_fee(payment_method, row_amount)
                        row_total = row_amount + transfer_fee

                        # Check wallet balance
                        if selected_wallet.balance < row_total:
                            logger.warning(f"Insufficient balance for CSV row: {row}, required: {row_total}, available: {selected_wallet.balance}")
                            results.append({
                                'mobile_number': mobile_number,
                                'name': recipient_name,
                                'success': False,
                                'message': f'Insufficient wallet balance for {recipient_name}.'
                            })
                            continue

                        # Generate unique transaction reference
                        random_code = get_random_string(6).upper()
                        transaction_ref = f"EXP-{random_code}"
                        print(transaction_ref)

                        # Create transaction record
                        payment_details = {
                            'phone_number': formatted_phone,
                            'method_type': 'B2C',
                            'recipient_name': recipient_name
                        }

                        transaction_record = Transaction.objects.create(
                            company=company,
                            user=user,
                            sender=user,
                            sender_wallet=selected_wallet,
                            amount=row_amount,
                            description=f"Batch payment for expense #{expense.id} to {recipient_name} ({mobile_number})",
                            status="pending",
                            transaction_type="withdraw",
                            transaction_code=transaction_ref,
                            payment_method=payment_method,
                            payment_details=payment_details,
                            transfer_fee=transfer_fee,
                            expense=expense
                        )

                        # Create fee transaction if applicable
                        fee_transaction = None
                        if transfer_fee > 0:
                            fee_transaction = TransactionFee.objects.create(
                                company=company,
                                user=user,
                                sender=user,
                                sender_wallet=selected_wallet,
                                amount=transfer_fee,
                                description=f"Transfer fee for batch payment to {recipient_name} ({mobile_number})",
                                status="pending",
                                transaction_type="fee",
                                transaction_code=f"FEE-{transaction_ref}",
                                parent_transaction=transaction_record,
                                payment_method=payment_method
                            )

                        # Initiate M-Pesa payment
                        mpesa_response = initiate_mpesa_payment(
                            payment_method=payment_method,
                            amount=int(row_amount),
                            payment_details=payment_details,
                            transaction_ref=transaction_ref,
                            expense=expense,
                            transaction_record=transaction_record
                        )

                        if mpesa_response.get('ResponseCode') != '0':
                            if fee_transaction:
                                fee_transaction.delete()
                            transaction_record.delete()
                            logger.error(f"M-Pesa payment failed for CSV row: {row}, error: {mpesa_response.get('ResponseDescription')}")
                            results.append({
                                'mobile_number': mobile_number,
                                'name': recipient_name,
                                'success': False,
                                'message': f'Payment failed: {mpesa_response.get("ResponseDescription", "Unknown error")}'
                            })
                            continue

                        # Update transaction record
                        transaction_record.mpesa_checkout_request_id = mpesa_response.get('CheckoutRequestID')
                        transaction_record.merchant_request_id = mpesa_response.get('MerchantRequestID')
                        transaction_record.conversation_id = mpesa_response.get('ConversationID')
                        transaction_record.originator_conversation_id = mpesa_response.get('OriginatorConversationID')
                        transaction_record.save()

                        total_amount += row_amount
                        total_fees += transfer_fee
                        valid_transactions += 1
                        results.append({
                            'mobile_number': mobile_number,
                            'name': recipient_name,
                            'success': True,
                            'message': 'Payment initiated successfully.',
                            'amount': str(row_amount),
                            'fee': str(transfer_fee),
                            'transaction_ref': transaction_ref
                        })

                    # Check if any valid transactions were processed
                    if valid_transactions == 0:
                        logger.error(f"No valid transactions processed for expense #{expense.id}, results: {results}")
                        return JsonResponse({
                            'success': False,
                            'message': 'No valid payments were processed. Check CSV data for errors.',
                            'results': results
                        })

                    # Validate total amount against expense
                    if total_amount != expense.amount:
                        logger.error(f"Total batch payment amount KES {total_amount} does not match expense amount KES {expense.amount}")
                        return JsonResponse({
                            'success': False,
                            'message': f'Total batch payment amount KES {total_amount} does not match expense amount KES {expense.amount}',
                            'results': results
                        })

                    # Update expense
                    expense.payment_initiated = True
                    expense.payment_reference = f"BATCH-EXP-{expense.id}"
                    expense.payment_wallet = selected_wallet
                    expense.save()

            return JsonResponse({
                'success': True,
                'message': f'Batch payment initiated. Total: KES {total_amount + total_fees} (Payments: KES {total_amount}, Fees: KES {total_fees})',
                'results': results
            })

        # Single payment logic
        if not all([expense_id, payment_method, amount]):
            return JsonResponse({
                'success': False,
                'message': 'All required fields must be filled.'
            })

        expense = get_object_or_404(Expense, id=expense_id)
        if not expense.approved or expense.declined:
            return JsonResponse({
                'success': False,
                'message': 'Payment can only be made for approved expenses.'
            })

        if expense.paid:
            return JsonResponse({
                'success': False,
                'message': 'This expense has already been paid.'
            })

        # Validate amount
        try:
            input_amount = Decimal(str(amount))
            if input_amount <= 0:
                raise ValueError("Amount must be positive")
        except (InvalidOperation, ValueError):
            return JsonResponse({
                'success': False,
                'message': 'Invalid amount provided.'
            })

        if input_amount != expense.amount:
            return JsonResponse({
                'success': False,
                'message': f'Amount must match the approved expense amount of KES {expense.amount}.'
            })

        expense_type_wallet = expense.wallet
        transfer_fee = calculate_transfer_fee(payment_method, input_amount)
        total_amount = input_amount + transfer_fee

        if expense_type_wallet.balance >= total_amount:
            selected_wallet = expense_type_wallet
            wallet_type = expense_type_wallet.wallet_type
        else:
            return JsonResponse({
                'success': False,
                'message': f'Insufficient funds. Total required: KES {total_amount} (Amount: KES {input_amount} + Fee: KES {transfer_fee}).'
            })

        # Validate payment method and extract details
        payment_details = {}
        if payment_method == 'mpesa_number':
            mpesa_number = request.POST.get('mpesa_number', '').strip()
            if not mpesa_number or not mpesa_number.isdigit() or len(mpesa_number) != 9:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid M-Pesa number. Please enter a valid 9-digit number.'
                })
            formatted_phone = format_phone_number(mpesa_number)
            payment_details = {
                'phone_number': formatted_phone,
                'method_type': 'B2C'
            }
        elif payment_method == 'paybill_number':
            paybill_number = request.POST.get('paybill_number', '').strip()
            account_number = request.POST.get('account_number', '').strip()
            if not paybill_number or not paybill_number.isdigit() or len(paybill_number) not in [5, 6]:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid paybill number. Please enter a valid 5-6 digit number.'
                })
            if not account_number:
                return JsonResponse({
                    'success': False,
                    'message': 'Account number is required for paybill payments.'
                })
            payment_details = {
                'paybill_number': paybill_number,
                'account_number': account_number,
                'method_type': 'B2B'
            }
        elif payment_method == 'till_number':
            till_number = request.POST.get('till_number', '').strip()
            if not till_number or not till_number.isdigit() or len(till_number) not in [5, 6]:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid till number. Please enter a valid 5-6 digit number.'
                })
            payment_details = {
                'till_number': till_number,
                'method_type': 'B2B'
            }
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid payment method selected.'
            })

        # Generate unique transaction reference
        random_code = get_random_string(6).upper()
        transaction_ref = f"EXP-{expense.id}-{random_code}"

        with transaction.atomic():
            selected_wallet = Wallet.objects.select_for_update().get(pk=selected_wallet.pk)
            transaction_record = Transaction.objects.create(
                company=company,
                user=user,
                sender=user,
                sender_wallet=selected_wallet,
                amount=input_amount,
                description=f"Payment for expense #{expense.id}: {getattr(expense, 'title', 'Expense')} via {payment_method}",
                status="pending",
                transaction_type="withdraw",
                transaction_code=transaction_ref,
                payment_method=payment_method,
                payment_details=payment_details,
                transfer_fee=transfer_fee,
                expense=expense
            )

            fee_transaction = None
            if transfer_fee > 0:
                fee_transaction = TransactionFee.objects.create(
                    company=company,
                    user=user,
                    sender=user,
                    sender_wallet=selected_wallet,
                    amount=transfer_fee,
                    description=f"Transfer fee for expense #{expense.id} payment via {payment_method}",
                    status="pending",
                    transaction_type="fee",
                    transaction_code=f"FEE-{transaction_ref}",
                    parent_transaction=transaction_record,
                    payment_method=payment_method
                )

            mpesa_response = initiate_mpesa_payment(
                payment_method=payment_method,
                amount=int(input_amount),
                payment_details=payment_details,
                transaction_ref=transaction_ref,
                expense=expense,
                transaction_record=transaction_record
            )

            if mpesa_response.get('ResponseCode') != '0':
                if fee_transaction:
                    fee_transaction.delete()
                transaction_record.delete()
                return JsonResponse({
                    'success': False,
                    'message': f'M-Pesa payment initiation failed: {mpesa_response.get("ResponseDescription", "Unknown error")}'
                })

            transaction_record.mpesa_checkout_request_id = mpesa_response.get('CheckoutRequestID')
            transaction_record.merchant_request_id = mpesa_response.get('MerchantRequestID')
            transaction_record.conversation_id = mpesa_response.get('ConversationID')
            transaction_record.originator_conversation_id = mpesa_response.get('OriginatorConversationID')
            transaction_record.save()

            expense.payment_initiated = True
            expense.payment_reference = transaction_ref
            expense.payment_wallet = selected_wallet
            expense.save()

        return JsonResponse({
            'success': True,
            'message': f'Payment initiated successfully. Total amount: KES {total_amount} '
                      f'(Payment: KES {input_amount} + Fee: KES {transfer_fee}). '
                      f'Please confirm the payment on your phone.',
            'transaction_ref': transaction_ref,
            'checkout_request_id': mpesa_response.get('CheckoutRequestID'),
            'amount': str(input_amount),
            'fee': str(transfer_fee),
            'total_amount': str(total_amount),
            'wallet_used': wallet_type
        })

    except Exception as e:
        logger.error(f"Payment initiation error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'An unexpected error occurred. Please try again.'
        })

def initiate_mpesa_payment(payment_method, amount, payment_details, transaction_ref, expense, transaction_record):
    """Initiate M-Pesa payment based on method type"""
    
    try:
        # Get access token
        mpesa = MpesaDaraja()
        access_token = mpesa.get_access_token()
        if not access_token:
            return {'ResponseCode': '1', 'ResponseDescription': 'Failed to authenticate with M-Pesa API'}

        # Common payment parameters
        callback_url = f"{settings.BASE_URL}{reverse('wallet:b2c_result')}"
        timeout_url = f"{settings.BASE_URL}{reverse('wallet:b2c_timeout')}"
        
        if payment_method == 'mpesa_number':
            # B2C Payment - Pass the transaction_record
            response = initiate_b2c_payment(
                mpesa=mpesa,
                amount=amount,
                phone_number=payment_details['phone_number'],
                wallet=expense.wallet,
                transaction=transaction_record  # Pass the transaction record
            )
            
        elif payment_method in ['paybill_number', 'till_number']:
            # B2B Payment
            if payment_method == 'paybill_number':
                receiver_shortcode = payment_details['paybill_number']
                account_reference = payment_details['account_number']
                command_id = 'BusinessPayBill'
            else:  # till_number
                receiver_shortcode = payment_details['till_number']
                account_reference = transaction_ref
                command_id = 'BusinessBuyGoods'
            
            response = initiate_b2b_payment(
                mpesa=mpesa,
                amount=amount,
                business_id=receiver_shortcode,
                wallet=expense.wallet,
                account_reference=account_reference,  # Now passed correctly
                command_id=command_id,  # Dynamic based on method
                transaction=transaction_record
            )
        else:
            return {'ResponseCode': '1', 'ResponseDescription': 'Unsupported payment method'}

        return response

    except Exception as e:
        logger.error(f"M-Pesa payment initiation error: {str(e)}", exc_info=True)
        return {'ResponseCode': '1', 'ResponseDescription': 'Payment service temporarily unavailable'}

# def initiate_mpesa_payment(payment_method, amount, payment_details, transaction_ref, expense, transaction_record):
#     """Initiate M-Pesa payment based on method type"""
    
#     try:
#         # Get access token
#         mpesa = MpesaDaraja()
#         access_token = mpesa.get_access_token()
#         if not access_token:
#             return {'ResponseCode': '1', 'ResponseDescription': 'Failed to authenticate with M-Pesa API'}

#         # Common payment parameters
#         callback_url = f"{settings.BASE_URL}{reverse('wallet:b2c_result')}"
#         timeout_url = f"{settings.BASE_URL}{reverse('wallet:b2c_timeout')}"
        
#         if payment_method == 'mpesa_number':
#             # B2C Payment - Pass the transaction_record
#             response = initiate_b2c_payment(
#                 mpesa=mpesa,
#                 amount=amount,
#                 phone_number=payment_details['phone_number'],
#                 wallet=expense.wallet,
#                 transaction=transaction_record  # Pass the transaction record
#             )
            
#         elif payment_method in ['paybill_number', 'till_number']:
#             # B2B Payment
#             if payment_method == 'paybill_number':
#                 receiver_shortcode = payment_details['paybill_number']
#                 account_reference = payment_details['account_number']
#             else:  # till_number
#                 receiver_shortcode = payment_details['till_number']
#                 account_reference = transaction_ref
            
#             response = initiate_b2b_payment(
#                 mpesa=mpesa,
#                 amount=amount,
#                 business_id=receiver_shortcode,
#                 wallet=expense.wallet,
#                 transaction=transaction_record  # Pass the transaction record
#             )
#         else:
#             return {'ResponseCode': '1', 'ResponseDescription': 'Unsupported payment method'}

#         return response

#     except Exception as e:
#         logger.error(f"M-Pesa payment initiation error: {str(e)}", exc_info=True)
#         return {'ResponseCode': '1', 'ResponseDescription': 'Payment service temporarily unavailable'}

@login_required
def get_expense_options(request):
    """AJAX view to get event/operation options based on expense group"""
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    expense_group = request.GET.get('expense_group')
    
    if expense_group == ExpenseGroup.EVENT:
        if company:
            events = Event.objects.filter(company=company).values('id', 'name')
        else:
            events = Event.objects.all().values('id', 'name')
        return JsonResponse({'options': list(events)})
    
    elif expense_group == ExpenseGroup.OPERATION:
        if company:
            operations = Operation.objects.filter(company=company).values('id', 'name')
        else:
            operations = Operation.objects.all().values('id', 'name')
        return JsonResponse({'options': list(operations)})
    
    return JsonResponse({'options': []})





@require_POST
def create_event(request):
    """AJAX endpoint to create a new event"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': 'Invalid request'})
        
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    
    form = EventExpenseForm(request.POST)
    if company:
        form.instance.company = company
    if user:
        form.instance.created_by = user
        
    if form.is_valid():
        event = form.save()
        return JsonResponse({
            'success': True,
            'id': event.id,
            'name': event.name
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)

@require_POST
def create_operation(request):
    """AJAX endpoint to create a new operation"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': 'Invalid request'})
        
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    
    form = OperationExpenseForm(request.POST)
    if company:
        form.instance.company = company
    if user:
        form.instance.created_by = user
        
    if form.is_valid():
        operation = form.save()
        return JsonResponse({
            'success': True,
            'id': operation.id,
            'name': operation.name
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)
    
@login_required
def reports(request):
    """Render the analytics dashboard template with all analytics data"""

    user = request.user
    company = getattr(user, 'staffprofile', None) and user.staffprofile.company or getattr(user, 'companykyc', None)

    if not company:
        return render(request, 'reports/analytics.html', {'error': 'No associated company found.'})

    # Filtered expenses
    expenses = Expense.objects.filter(company=company)

    # Prepare trend data (monthly)
    monthly_data = defaultdict(lambda: {'event': 0, 'operation': 0})
    for exp in expenses:
        month = exp.created_at.strftime('%Y-%m')
        type_key = 'event' if exp.event else 'operation'
        monthly_data[month][type_key] += float(exp.amount)

    trend_chart = {
        'labels': list(monthly_data.keys()),
        'event': [monthly_data[m]['event'] for m in monthly_data],
        'operation': [monthly_data[m]['operation'] for m in monthly_data]
    }

    # Prepare category distribution data
    category_data = expenses.values('expense_category__name') \
        .annotate(total=Sum('amount')) \
        .order_by('-total')
    pie_chart = {
        'labels': [c['expense_category__name'] or 'Uncategorized' for c in category_data],
        'amounts': [float(c['total']) for c in category_data],
    }

    # Prepare status bar chart data
    last_12_months = get_past_12_months()
    status_bar_chart = get_status_bar_chart_data(expenses, last_12_months)

    context = {
        'categories': ExpenseCategory.objects.filter(is_active=True),
        'request_types': ExpenseRequestType.objects.filter(is_active=True),
        'events': Event.objects.filter(is_active=True, company=company),
        'operations': Operation.objects.filter(is_active=True, company=company),
        'trend_chart': trend_chart,
        'pie_chart': pie_chart,
        'status_bar_chart': status_bar_chart,
    }

    return render(request, 'reports/analytics.html', context)


def get_past_12_months():
    now = datetime.now()
    months = []
    for i in range(11, -1, -1):  # from 11 months ago to now
        year = (now.year if now.month - i > 0 else now.year - 1)
        month = (now.month - i - 1) % 12 + 1
        months.append(f"{year}-{month:02}")
    return months


def get_status_bar_chart_data(expenses, months):
    """Generate status bar chart data for events and operations"""
    
    # Initialize data structure
    status_data = {
        'events': {
            'approved': [0] * len(months),
            'completed': [0] * len(months),
            'declined': [0] * len(months)
        },
        'operations': {
            'approved': [0] * len(months),
            'completed': [0] * len(months),
            'declined': [0] * len(months)
        }
    }
    
    # Process expenses and categorize by status and type
    for exp in expenses:
        month = exp.created_at.strftime('%Y-%m')
        if month in months:
            month_index = months.index(month)
            
            # Determine expense type
            exp_type = 'events' if exp.event else 'operations'
            
            # Determine status - adjust these field names based on your Expense model
            status = get_expense_status(exp)
            
            if status in status_data[exp_type]:
                status_data[exp_type][status][month_index] += float(exp.amount)
    
    return {
        'labels': months,
        'events': status_data['events'],
        'operations': status_data['operations']
    }


def get_expense_status(expense):
    """
    Determine the status of an expense based on your model fields.
    Adjust this function based on your actual Expense model structure.
    """
    # Example implementation - modify based on your actual model fields
    if hasattr(expense, 'status'):
        status = expense.status.lower() if expense.status else 'pending'
        if status in ['approved', 'accept', 'accepted']:
            return 'approved'
        elif status in ['completed', 'complete', 'done']:
            return 'completed'
        elif status in ['declined', 'rejected', 'reject', 'deny', 'denied']:
            return 'declined'
    
    # If you have separate boolean fields, use this approach:
    # if hasattr(expense, 'is_approved') and expense.is_approved:
    #     return 'approved'
    # elif hasattr(expense, 'is_completed') and expense.is_completed:
    #     return 'completed'
    # elif hasattr(expense, 'is_declined') and expense.is_declined:
    #     return 'declined'
    
    # Default to approved if no clear status
    return 'approved'


@require_GET
@login_required
def analytics_data(request):
    user = request.user
    company = getattr(user, 'staffprofile', None) and user.staffprofile.company or getattr(user, 'companykyc', None)

    if not company:
        return JsonResponse({'error': 'No associated company'}, status=400)

    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    status_filter = request.GET.get('status')

    expenses = Expense.objects.filter(company=company)
    
    # Apply date filters
    if start_date and end_date:
        start_date = timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
        end_date = timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d")) + timezone.timedelta(days=1)
        expenses = expenses.filter(created_at__range=[start_date, end_date])

    # Apply status filter
    if status_filter:
        expenses = filter_expenses_by_status(expenses, status_filter)

    # Trend chart data (12-monthly)
    monthly_data = defaultdict(lambda: {'event': 0, 'operation': 0})
    for exp in expenses:
        month = exp.created_at.strftime('%Y-%m')
        key = 'event' if exp.event else 'operation'
        monthly_data[month][key] += float(exp.amount)

    # Ensure we have 12 months, even with zero values
    last_12_months = get_past_12_months()
    trend_chart = {
        'labels': last_12_months,
        'event': [monthly_data[m]['event'] for m in last_12_months],
        'operation': [monthly_data[m]['operation'] for m in last_12_months],
    }

    # Pie chart data
    category_data = expenses.values('expense_category__name') \
        .annotate(total=Sum('amount')) \
        .order_by('-total')
    pie_chart = {
        'labels': [c['expense_category__name'] or 'Uncategorized' for c in category_data],
        'amounts': [float(c['total']) for c in category_data]
    }

    # Status bar chart data
    status_bar_chart = get_status_bar_chart_data(expenses, last_12_months)

    return JsonResponse({
        'trend_chart': trend_chart,
        'pie_chart': pie_chart,
        'status_bar_chart': status_bar_chart,
    })


def filter_expenses_by_status(expenses, status_filter):
    """Filter expenses based on status - adjust based on your model structure"""
    
    if status_filter == 'approved':
        # Modify this condition based on your actual model fields
        return expenses.filter(status__iexact='approved')
        # or if using boolean fields: return expenses.filter(is_approved=True)
        
    elif status_filter == 'completed':
        return expenses.filter(status__iexact='completed')
        # or: return expenses.filter(is_completed=True)
        
    elif status_filter == 'declined':
        return expenses.filter(status__iexact='declined')
        # or: return expenses.filter(is_declined=True)
        # or for multiple declined statuses: 
        # return expenses.filter(status__iexact__in=['declined', 'rejected'])
    
    return expenses



@login_required
def inventory_list(request):
    org = None
    # If organization scope is needed: pass organization in context / filter by organization
    items = InventoryItem.objects.filter(is_active=True).select_related("captured_by", "organization")
    # For each item create edit form instance (server-rendered modal)
    item_edit_forms = {item.id: InventoryItemForm(instance=item) for item in items}

    new_form = InventoryItemForm(initial={"captured_by": request.user})
    # Transaction forms per item
    checkout_forms = {item.id: InventoryTransactionForm(initial={"item": item, "transaction_type": "Check Out"}) for item in items}
    checkin_forms = {item.id: InventoryTransactionForm(initial={"item": item, "transaction_type": "Check In"}) for item in items}

    context = {
        "items": items,
        "new_form": new_form,
        "item_edit_forms": item_edit_forms,
        "checkout_forms": checkout_forms,
        "checkin_forms": checkin_forms,
    }
    return render(request, "inventory/inventory_list.html", context)


@login_required
def inventory_create(request):
    if request.method == "POST":
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            if not item.captured_by:
                item.captured_by = request.user
            item.save()
            messages.success(request, "Inventory item created.")
        else:
            messages.error(request, "Error creating inventory item.")
    return redirect("inventory:list")


@login_required
def inventory_edit(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == "POST":
        form = InventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Inventory item updated.")
        else:
            messages.error(request, "Error updating inventory item.")
    return redirect("inventory:list")


@login_required
def inventory_delete(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == "POST":
        item.is_active = False
        item.save()
        messages.success(request, "Inventory item deleted.")
    return redirect("inventory:list")


@login_required
def inventory_check_out(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == "POST":
        form = InventoryTransactionForm(request.POST)
        if form.is_valid():
            trx = form.save(commit=False)
            trx.item = item
            trx.transaction_type = "Check Out"
            if not trx.check_out_date:
                trx.check_out_date = timezone.now()
            trx.save()
            item.state = "Checked Out"
            item.save()
            messages.success(request, f"{item.name} checked out.")
        else:
            messages.error(request, "Error checking out item.")
    return redirect("inventory:list")


@login_required
def inventory_check_in(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == "POST":
        form = InventoryTransactionForm(request.POST)
        if form.is_valid():
            trx = form.save(commit=False)
            trx.item = item
            trx.transaction_type = "Check In"
            if not trx.check_in_date:
                trx.check_in_date = timezone.now()
            trx.save()
            item.state = "Available"
            item.save()
            messages.success(request, f"{item.name} checked in.")
        else:
            messages.error(request, "Error checking in item.")
    return redirect("inventory:list")

@login_required
def suppliers_list(request):
    suppliers = Supplier.objects.filter(organization__isnull=False)  # adjust filter as needed
    supplier_edit_forms = {s.id: SupplierForm(instance=s) for s in suppliers}
    new_form = SupplierForm(initial={"captured_by": request.user})
    context = {
        "suppliers": suppliers,
        "new_form": new_form,
        "supplier_edit_forms": supplier_edit_forms,
    }
    return render(request, "inventory/suppliers_list.html", context)


@login_required
def supplier_create(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            sup = form.save(commit=False)
            if not sup.captured_by:
                sup.captured_by = request.user
            sup.save()
            messages.success(request, "Supplier created.")
        else:
            messages.error(request, "Error creating supplier.")
    return redirect("inventory:suppliers")


@login_required
def supplier_edit(request, pk):
    sup = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=sup)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier updated.")
        else:
            messages.error(request, "Error updating supplier.")
    return redirect("inventory:suppliers")


@login_required
def supplier_delete(request, pk):
    sup = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        sup.is_active = False
        sup.save()
        messages.success(request, "Supplier removed.")
    return redirect("inventory:suppliers")


# Supplier invoices

@login_required
def supplier_invoices(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    invoices = SupplierInvoice.objects.filter(supplier=supplier).order_by("-date_issued")
    invoice_forms = {inv.id: SupplierInvoiceForm(instance=inv) for inv in invoices}
    new_invoice_form = SupplierInvoiceForm(initial={"supplier": supplier, "created_by": request.user})
    # invoice items listing via InvoiceItem model
    context = {
        "supplier": supplier,
        "invoices": invoices,
        "invoice_forms": invoice_forms,
        "new_invoice_form": new_invoice_form,
    }
    return render(request, "inventory/supplier_invoices.html", context)


@login_required
def supplier_invoice_create(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    if request.method == "POST":
        form = SupplierInvoiceForm(request.POST)
        if form.is_valid():
            inv = form.save(commit=False)
            inv.supplier = supplier
            if not inv.created_by:
                inv.created_by = request.user
            inv.save()
            messages.success(request, "Invoice created.")
        else:
            messages.error(request, "Error creating invoice.")
    return redirect("inventory:supplier_invoices", supplier_id=supplier.id)


@login_required
def supplier_invoice_edit(request, supplier_id, invoice_id):
    inv = get_object_or_404(SupplierInvoice, pk=invoice_id, supplier_id=supplier_id)
    if request.method == "POST":
        form = SupplierInvoiceForm(request.POST, instance=inv)
        if form.is_valid():
            form.save()
            messages.success(request, "Invoice updated.")
        else:
            messages.error(request, "Error updating invoice.")
    return redirect("inventory:supplier_invoices", supplier_id=supplier_id)


@login_required
def supplier_invoice_delete(request, supplier_id, invoice_id):
    inv = get_object_or_404(SupplierInvoice, pk=invoice_id, supplier_id=supplier_id)
    if request.method == "POST":
        inv.delete()
        messages.success(request, "Invoice deleted.")
    return redirect("inventory:supplier_invoices", supplier_id=supplier_id)


# Optional: invoice item create/edit/delete endpoints
@login_required
def invoice_item_create(request, supplier_id, invoice_id):
    inv = get_object_or_404(SupplierInvoice, pk=invoice_id, supplier_id=supplier_id)
    if request.method == "POST":
        form = InvoiceItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.invoice = inv
            item.save()
            messages.success(request, "Invoice item added.")
        else:
            messages.error(request, "Error adding invoice item.")
    return redirect("inventory:supplier_invoices", supplier_id=supplier_id)