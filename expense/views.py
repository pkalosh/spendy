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
from .models import Expense, Event, Operation, ExpenseGroup, CategoryBase, ExpenseCategory, EventCategory, OperationCategory,ExpenseRequestType
from .forms import ExpenseRequestForm, ExpenseApprovalForm, PaymentForm, EventExpenseForm, OperationExpenseForm
from wallet.models import Transaction, CompanyKYC, Wallet
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth, TruncYear
from datetime import datetime, timedelta
import csv
import io
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
        expense_form = ExpenseRequestForm(request.POST, company=company)
        request_type = request.POST.get('request_type')  # Fetch from submitted data
        print(request_type)

        if expense_form.is_valid():
            expense = expense_form.save(commit=False)
            expense.created_by = request.user
            expense.company = company

            # Determine wallet based on request_type
            if request_type == '1':
                wallet = Wallet.objects.filter(company=company, wallet_type='EVENT').first()
            elif request_type == '2':
                wallet = Wallet.objects.filter(company=company, wallet_type='OPERATIONS').first()
            else:
                wallet = None

            if not wallet:
                messages.error(request, f"No wallet found for type '{request_type}'.")
                return redirect('wallet:expense-requests')

            expense.wallet = wallet
            expense.save()

            # Notify expense workflow
            notify_expense_workflow(expense=expense, action='created', send_sms=True)

            messages.success(request, "Expense request submitted successfully.")
            return redirect('wallet:expense-requests')
        else:
            messages.error(request, f"Please correct the errors below.{expense_form.errors}")
    else:
        
        expense_form = ExpenseRequestForm(company=company)

    return render(request, 'users/staff/staff.html', {'expense_form': expense_form})

@login_required
def event_operation(request):
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
                name = request.POST.get('event_name')
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
                
                # Validate dates
                start_date = request.POST.get('event_start_date')
                end_date = request.POST.get('event_end_date')
                if not start_date or not end_date:
                    raise ValidationError("Start and end dates are required")
                
                # Validate budget
                budget = None
                budget_str = request.POST.get('event_budget')
                if budget_str:
                    try:
                        budget = Decimal(budget_str)
                        if budget < 0:
                            raise ValidationError("Budget cannot be negative")
                    except InvalidOperation:
                        raise ValidationError("Invalid budget value")
                
                # Get other fields
                project_lead = request.POST.get('event_project_lead')
                if not project_lead:
                    raise ValidationError("Project lead is required")
                    
                location = request.POST.get('event_location')
                if not location:
                    raise ValidationError("Location is required")
                
                # Create and save event
                event = Event(
                    name=name,
                    category=category,
                    company=company,
                    start_date=start_date,
                    end_date=end_date,
                    budget=budget,
                    project_lead=project_lead,
                    location=location,
                    created_by=request.user
                )
                
                # Run model validation
                event.full_clean()
                event.save()
                
                # Notify expense workflow
                messages.success(request, 'Event request submitted successfully.')
                return redirect('wallet:expenses')
                # Validate required fields
            elif request_type == 'operation':
                # Validate required fields
                name = request.POST.get('operation_name')
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
                
                # Validate budget
                budget = None
                budget_str = request.POST.get('operation_budget')
                if budget_str:
                    try:
                        budget = Decimal(budget_str)
                        if budget < 0:
                            raise ValidationError("Budget cannot be negative")
                    except InvalidOperation:
                        raise ValidationError("Invalid budget value")
                
                # Get other fields
                project_lead = request.POST.get('operation_project_lead')
                
                # Create and save operation
                operation = Operation(
                    name=name,
                    category=category,
                    company=company,
                    budget=budget,
                    project_lead=project_lead,
                    created_by=request.user
                )
                
                # Run model validation
                operation.full_clean()
                operation.save()
                
                # Notify expense workflow
                messages.success(request, 'Operation request submitted successfully.')
                return redirect('wallet:expenses')
                
            return redirect('wallet:expenses')
            
        except ValidationError as e:
            error_message = str(e) if hasattr(e, 'message') else str(e.messages[0]) if e.messages else "Form validation error"
            messages.error(request, f'Error: {error_message}')
            return redirect('wallet:expenses')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {str(e)}')
            return redirect('wallet:expenses')
    
    # Handle GET request - since this is a popup/modal, we don't need to render a template here
    # The form should already be in the page that opened the modal
    return redirect('wallet:expenses')


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
        'users': User.objects.all().order_by('first_name', 'last_name'),
        'expense_category_choices': ExpenseCategory.objects.all(),
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

    # Determine if we're looking at an event, operation, or specific expense
    if item_type == 'event':
        event = None
        event_queryset = Event.objects.filter(id=id)
        if event_queryset.exists():
            event = event_queryset.first()
        else:
            if hasattr(Event, 'uuid'):
                event_queryset = Event.objects.filter(uuid=id)
                if event_queryset.exists():
                    event = event_queryset.first()
        if not event:
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
        operation = None
        operation_queryset = Operation.objects.filter(id=id)
        if operation_queryset.exists():
            operation = operation_queryset.first()
        else:
            if hasattr(Operation, 'uuid'):
                operation_queryset = Operation.objects.filter(uuid=id)
                if operation_queryset.exists():
                    operation = operation_queryset.first()
        if not operation:
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
        related_expenses = Expense.objects.none()
        if event:
            related_expenses = Expense.objects.filter(event=event, **expense_filters).exclude(id=expense.id)
        elif operation:
            related_expenses = Expense.objects.filter(operation=operation, **expense_filters).exclude(id=expense.id)

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
    
    # Base filter for company
    base_filter = Q(company=company)
    
    # Add search filter
    if query:
        base_filter &= (
            Q(created_by__first_name__icontains=query) |
            Q(created_by__last_name__icontains=query) |
            Q(description__icontains=query) |
            Q(event__name__icontains=query) |
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
    
    # Event expenses
    event_expenses = filter_expenses(
        Expense.objects.filter(base_filter & Q(event__isnull=False))
        .select_related('event', 'expense_category', 'created_by', 'approved_by')
        .order_by('-created_at')
    )
    
    # Operation expenses
    operation_expenses = filter_expenses(
        Expense.objects.filter(base_filter & Q(operation__isnull=False))
        .select_related('operation', 'expense_category', 'created_by', 'approved_by')
        .order_by('-created_at')
    )
    
    # Past requests (approved or declined)
    past_requests = Expense.objects.filter(base_filter).filter(
        Q(approved=True) | Q(declined=True)
    ).select_related(
        'expense_category', 'created_by', 'approved_by', 'event', 'operation'
    ).order_by('-updated_at')
    
    # Pagination
    event_page = request.GET.get('event_page', 1)
    op_page = request.GET.get('op_page', 1)
    history_page = request.GET.get('history_page', 1)
    
    event_paginator = Paginator(event_expenses, 10)
    operation_paginator = Paginator(operation_expenses, 10)
    history_paginator = Paginator(past_requests, 10)
    
    # Get page objects
    event_requests = event_paginator.get_page(event_page)
    operation_requests = operation_paginator.get_page(op_page)
    past_requests_page = history_paginator.get_page(history_page)
    
    # Summary counts
    summary = {
        'total_pending': Expense.objects.filter(
            base_filter & Q(approved=False, declined=False)
        ).count(),
        'total_approved': Expense.objects.filter(
            base_filter & Q(approved=True)
        ).count(),
        'total_rejected': Expense.objects.filter(
            base_filter & Q(declined=True)
        ).count(),
    }
    summary['total_all'] = summary['total_pending'] + summary['total_approved'] + summary['total_rejected']
    
    context = {
        'event_requests': event_requests,
        'operation_requests': operation_requests,
        'past_requests': past_requests_page,
        'query': query,
        'status': status,
        'summary': summary,
    }
    
    return render(request, 'expenses/approvals.html', context)



@require_POST
@login_required
def approve_expenses(request, expense_id):
    try:
        expense = get_object_or_404(Expense, id=expense_id)

        # Prevent re-approving already processed items
        if expense.approved or expense.declined:
            return JsonResponse(
                {'error': 'This expense has already been processed.'},
                status=400
            )

        # Optional: Add permission check if needed
        # if not request.user.has_perm('your_app.can_approve_expense'):
        #     return JsonResponse({'error': 'Permission denied'}, status=403)

        expense.approved = True
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.declined = False  # Ensure declined is reset
        expense.decline_reason = None  # Clear any previous decline reason
        expense.save()
        notify_expense_workflow(expense=expense, action = 'approved', approver_name=expense.approved_by.get_full_name())

        return JsonResponse({
            'message': 'Expense approved successfully.',
            'approved_by_name': request.user.get_full_name() or request.user.username
        }, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Failed to approve expense: {str(e)}'}, status=500)
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

        # Prevent declining already processed expenses
        if expense.approved or expense.declined:
            return JsonResponse(
                {'error': 'This expense has already been processed.'},
                status=400
            )

        # Optional: Add permission check if needed
        # if not request.user.has_perm('your_app.can_decline_expense'):
        #     return JsonResponse({'error': 'Permission denied'}, status=403)

        expense.declined = True
        expense.declined_at = timezone.now()
        expense.decline_reason = reason
        expense.approved = False  # Ensure approved is reset
        expense.approved_by = request.user
        expense.save()
        notify_expense_workflow(expense=expense, action='declined', approver_name=expense.approved_by.get_full_name())

        return JsonResponse({
            'message': 'Expense has been declined successfully.',
            'approved_by_name': request.user.get_full_name() or request.user.username
        }, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Failed to decline expense: {str(e)}'}, status=500)
@login_required
def make_payment(request):
    """Handle payments for approved expenses via M-Pesa API with fee calculation"""
    
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

        # Validate essential fields
        if not all([expense_id, payment_method, amount]):
            return JsonResponse({
                'success': False,
                'message': 'All required fields must be filled.'
            })

        # Get and validate expense
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

        # Check exact amount match
        if input_amount != expense.amount:
            return JsonResponse({
                'success': False,
                'message': f'Amount must match the approved expense amount of KES {expense.amount}.'
            })

        # Validate expense type and get associated wallet
        if not hasattr(expense, 'request_type') or not expense.request_type:
            return JsonResponse({
                'success': False,
                'message': 'Expense must have a valid expense type.'
            })

        expense_type_wallet = expense.wallet  # Assuming this is the expense type wallet
        
        # Calculate transfer fee
        transfer_fee = calculate_transfer_fee(payment_method, input_amount)
        total_amount = input_amount + transfer_fee

        # Check expense type wallet balance first
        if expense_type_wallet.balance >= total_amount:
            selected_wallet = expense_type_wallet
            wallet_type = expense_type_wallet.wallet_type  # Assuming this field exists
        else:
            # Check primary wallet balance as fallback
            try:
                primary_wallet = Wallet.objects.get(
                    company=company,
                    wallet_type='primary'  # Adjust this field name as per your model
                )
                if primary_wallet.balance >= total_amount:
                    selected_wallet = primary_wallet
                    wallet_type = 'primary'
                else:
                    return JsonResponse({
                        'success': False,
                        'message': f'Insufficient funds. Total required: KES {total_amount} (Amount: KES {input_amount} + Fee: KES {transfer_fee}). '
                                 f'Expense wallet balance: KES {expense_type_wallet.balance}, '
                                 f'Primary wallet balance: KES {primary_wallet.balance}'
                    })
            except Wallet.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': f'Insufficient funds in expense wallet (KES {expense_type_wallet.balance}) '
                             f'and no primary wallet available. Total required: KES {total_amount}'
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
            
            # Format phone number
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
        transaction_ref = f"EXP-{expense_id}-{uuid.uuid4().hex[:4].upper()}"

        # Initiate M-Pesa payment
        mpesa_response = initiate_mpesa_payment(
            payment_method=payment_method,
            amount=int(input_amount),
            payment_details=payment_details,
            transaction_ref=transaction_ref,
            expense=expense
        )

        print(f"M-Pesa payment response: {mpesa_response}")

        if mpesa_response.get('ResponseCode') != '0':
            return JsonResponse({
                'success': False,
                'message': f'M-Pesa payment initiation failed: {mpesa_response.get("ResponseDescription", "Unknown error")}'
            })

        # Create transaction record in pending status
        with transaction.atomic():
            # Lock wallet for update
            selected_wallet = Wallet.objects.select_for_update().get(pk=selected_wallet.pk)
            
            # Create pending transaction for the expense amount
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
                mpesa_checkout_request_id=mpesa_response.get('CheckoutRequestID'),
                merchant_request_id=mpesa_response.get('MerchantRequestID'),
                payment_method=payment_method,
                payment_details=json.dumps(payment_details),
                transfer_fee=transfer_fee
            )

            # Create fee transaction if fee > 0
            if transfer_fee > 0:
                Transaction.objects.create(
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

            # Mark expense as being processed
            expense.payment_initiated = True
            expense.payment_reference = transaction_ref
            expense.payment_wallet = selected_wallet
            expense.save()

        return JsonResponse({
            'success': True,
            'message': f'Payment initiated successfully. Total amount: KES {total_amount} '
                      f'(Payment: KES {input_amount} + Fee: KES {transfer_fee}). '
                      f'Please complete the payment on your phone.',
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
def initiate_mpesa_payment(payment_method, amount, payment_details, transaction_ref, expense):
    """Initiate M-Pesa payment based on method type"""
    
    try:
        # Get access token
        mpesa = MpesaDaraja()
        access_token = mpesa.get_access_token()
        if not access_token:
            return {'success': False, 'message': 'Failed to authenticate with M-Pesa API'}

        # Common payment parameters
        callback_url = f"{settings.BASE_URL}{reverse('wallet:b2c_result')}"
        timeout_url = f"{settings.BASE_URL}{reverse('wallet:b2c_timeout')}"
        
        if payment_method == 'mpesa_number':
            # B2C Payment
            response = initiate_b2c_payment(
                mpesa=mpesa,
                amount=amount,
                phone_number=payment_details['phone_number'],
                wallet=expense.wallet,
            )
            
        elif payment_method in ['paybill_number', 'till_number']:
            # B2B Payment
            if payment_method == 'paybill_number':
                receiver_shortcode = payment_details['paybill_number']
                account_reference = payment_details['account_number']
            else:  # till_number
                receiver_shortcode = payment_details['till_number']
                account_reference = transaction_ref
            
            response = initiate_b2b_payment(
                mpesa=mpesa,
                amount=amount,
                receiver_shortcode=receiver_shortcode,
                account_reference=account_reference,
                transaction_ref=transaction_ref,
                callback_url=f"{settings.BASE_URL}{reverse('wallet:b2b_result')}",
                timeout_url=f"{settings.BASE_URL}{reverse('wallet:b2b_timeout')}",
                remarks=f"Payment for expense {expense.id} {expense.wallet.wallet_number}"
            )
        
        else:
            return {'success': False, 'message': 'Unsupported payment method'}

        return response

    except Exception as e:
        logger.error(f"M-Pesa payment initiation error: {str(e)}", exc_info=True)
        return {'success': False, 'message': 'Payment service temporarily unavailable'}

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