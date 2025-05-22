from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden,HttpResponse
from django.db import transaction
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.views.decorators.http import require_GET
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
from collections import defaultdict
from datetime import datetime, timedelta
import calendar

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

            messages.success(request, "Expense request submitted successfully.")
            return redirect('wallet:expense-requests')
        else:
            messages.error(request, "Please correct the errors below.")
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
                description = request.POST.get('event_description')
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
                    description=description,
                    project_lead=project_lead,
                    location=location,
                    created_by=request.user
                )
                
                # Run model validation
                event.full_clean()
                event.save()
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
                description = request.POST.get('operation_description')
                project_lead = request.POST.get('operation_project_lead')
                
                # Create and save operation
                operation = Operation(
                    name=name,
                    category=category,
                    company=company,
                    budget=budget,
                    description=description,
                    project_lead=project_lead,
                    created_by=request.user
                )
                
                # Run model validation
                operation.full_clean()
                operation.save()
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

@login_required
def expense_detail(request, id, item_type=None):
    user = request.user
    company = getattr(user, 'company', None) or getattr(user, 'companykyc', None)
    
    # Determine if we're looking at an event, operation, or specific expense
    if item_type == 'event':
        # Handle event and its expenses
        event = None
        
        # First try direct id lookup
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
            return HttpResponse(f"Event with ID {id} not found.", status=404)
            
        # Check if this event belongs to the user's company
        if company and event.company != company:
            return HttpResponseForbidden("You don't have permission to view this event")
            
        expenses = Expense.objects.filter(event=event)
        event_form = EventExpenseForm()
        
        # Create expense summary by status
        expense_summary = {
            'pending': expenses.filter(approved=False, declined=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'approved': expenses.filter(approved=True).aggregate(Sum('amount'))['amount__sum'] or 0,
            'declined': expenses.filter(declined=True).aggregate(Sum('amount'))['amount__sum'] or 0,
        }
        
        # Group expenses by category
        expense_categories = expenses.filter(approved=True).values('expense_category').annotate(total=Sum('amount')).order_by('-total')
      
        context = {
            'item': event,
            'item_type': 'event',
            'expenses': expenses,
            'expense_summary': expense_summary,
            'expense_categories': expense_categories,
            'is_admin': is_admin(user),
            'event_form': event_form,
        }
        return render(request, 'expenses/expense_detail.html', context)
        
    elif item_type == 'operation':
        # Handle operation and its expenses
        operation = None
        
        # First try direct id lookup
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
            return HttpResponse(f"Operation with ID {id} not found.", status=404)
            
        # Check if this operation belongs to the user's company
        if company and operation.company != company:
            return HttpResponseForbidden("You don't have permission to view this operation")
            
        expenses = Expense.objects.filter(operation=operation)
        operation_form = OperationExpenseForm()
        
        # Create expense summary by status
        expense_summary = {
            'pending': expenses.filter(approved=False, declined=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'approved': expenses.filter(approved=True).aggregate(Sum('amount'))['amount__sum'] or 0,
            'declined': expenses.filter(declined=True).aggregate(Sum('amount'))['amount__sum'] or 0,
        }
        
        # Group expenses by category
        expense_categories = expenses.filter(approved=True).values('expense_category').annotate(total=Sum('amount')).order_by('-total')

        
        context = {
            'item': operation,
            'item_type': 'operation',
            'expenses': expenses,
            'expense_summary': expense_summary,
            'expense_categories': expense_categories,
            'is_admin': is_admin(user),
            'operation_form': operation_form,
        }
        return render(request, 'expenses/expense_detail.html', context)
        
    else:
        # Handle individual expense
        expense = None
        
        # First try direct id lookup
        expense_queryset = Expense.objects.filter(id=id)
        if expense_queryset.exists():
            expense = expense_queryset.first()
        else:
            # Check if the model has a uuid field
            if hasattr(Expense, 'uuid'):
                expense_queryset = Expense.objects.filter(uuid=id)
                if expense_queryset.exists():
                    expense = expense_queryset.first()
        
        if not expense:
            return HttpResponse(f"Expense with ID {id} not found.", status=404)
        
        # Permission check
        if not is_admin(user) and expense.created_by != user:
            return HttpResponseForbidden("You don't have permission to view this expense")
        
        # Get related event or operation for this expense
        event = None
        operation = None
        
        if hasattr(expense, 'event') and expense.event:
            event = expense.event
            # Get all expenses related to this event
            related_expenses = Expense.objects.filter(event=event).exclude(id=expense.id)
        elif hasattr(expense, 'operation') and expense.operation:
            operation = expense.operation
            # Get all expenses related to this operation
            related_expenses = Expense.objects.filter(operation=operation).exclude(id=expense.id)
        else:
            related_expenses = Expense.objects.none()
        
        approval_form = None
        if is_admin(user) and not expense.approved and not expense.declined:
            approval_form = ExpenseApprovalForm(instance=expense)
        
        payment_form = None
        if expense.approved and not expense.declined:
            payment_form = PaymentForm(user=user, company=company, initial={'expense': expense})
        
        # Add expense request summary by category
        # For individual expense view
        from collections import Counter
        expense_requests = []
        if hasattr(expense, 'event') and expense.event:
            # Get all expenses in the same category for this event
            expense_categories = Expense.objects.filter(
                event=expense.event
            ).values('expense_category').annotate(
                amount=Sum('amount')
            ).order_by('-amount')
            
            expense_requests = [
                {'category': cat['expense_category'], 'amount': cat['amount']} 
                for cat in expense_categories
            ]
        elif hasattr(expense, 'operation') and expense.operation:
            # Get all expenses in the same category for this operation
            expense_categories = Expense.objects.filter(
                operation=expense.operation
            ).values('expense_category').annotate(
                amount=Sum('amount')
            ).order_by('-amount')
            
            expense_requests = [
                {'category': cat['expense_category'], 'amount': cat['amount']} 
                for cat in expense_categories
            ]
        
        # Get summary stats for this expense
        summaries = [
            {'status': 'Current Status', 'amount': expense.amount},
        ]
        
        # Get all approved expense requests related to this expense
        approved_requests = []
        if hasattr(expense, 'event') and expense.event:
            approved_requests = Expense.objects.filter(
                event=expense.event, 
                approved=True
            ).values(
                'created_by__first_name', 
                'created_by__last_name', 
                'expense_category', 
                'amount'
            )
        elif hasattr(expense, 'operation') and expense.operation:
            approved_requests = Expense.objects.filter(
                operation=expense.operation, 
                approved=True
            ).values(
                'created_by__first_name', 
                'created_by__last_name', 
                'expense_category', 
                'amount'
            )
            
        # Format approved requests for template
        formatted_approved_requests = []
        for req in approved_requests:
            formatted_approved_requests.append({
                'created_by': f"{req['created_by__first_name']} {req['created_by__last_name']}",
                'expense_type': req['expense_category'],
                'status': 'Approved',
                'amount': req['amount']
            })
        
        context = {
            'expense': expense,
            'approval_form': approval_form,
            'payment_form': payment_form,
            'is_admin': is_admin(user),
            'related_expenses': related_expenses,
            'event': event,
            'operation': operation,
            'summaries': summaries,
            'expense_requests': expense_requests,
            'approved_requests': formatted_approved_requests,
        }
        
        return render(request, 'expenses/expense_detail.html', context)
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
                
                return redirect('expense:expense_detail', id=expense.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return redirect('expense:expense_detail', id=expense.id)


@login_required
def expense_approvals(request):
    # Event requests are those linked to an Event and not yet approved/declined
    event_requests = Expense.objects.filter(event__isnull=False, approved=False, declined=False,company=request.user.companykyc)

    # Operation requests are those linked to an Operation and not yet approved/declined
    operation_requests = Expense.objects.filter(operation__isnull=False, approved=False, declined=False,company=request.user.companykyc)
    past_requests = Expense.objects.filter(company = request.user.companykyc).exclude(approved=False, declined=False).order_by('-created_at')
    print(past_requests)

    context = {
        'event_requests': event_requests,
        'operation_requests': operation_requests,
        'past_requests': past_requests,
    }
    # print(context)

    return render(request, 'expenses/approvals.html', context)




@login_required
def approve_expenses(request, expense_id):
    if request.method == 'POST':
        expense = get_object_or_404(Expense, id=expense_id)

        # Optional: prevent re-approving already processed items
        if expense.approved or expense.declined:
            messages.warning(request, "This expense has already been processed.")
            return redirect('expense:expense_approvals')

        expense.approved = True
        expense.approved_by = request.user
        expense.approved_at = timezone.now()  # Add this field in model if needed
        expense.save()

        messages.success(request, "Expense approved successfully.")
    else:
        messages.error(request, "Invalid request method.")

    return redirect('expense:expense_approvals')
@login_required
def decline_expense(request, expense_id):
    if request.method == 'POST':
        reason = request.POST.get("reason", "").strip()

        if not reason:
            messages.error(request, "Decline reason is required.")
            return redirect('expense:expense_approvals')

        expense = get_object_or_404(Expense, id=expense_id)

        # Optional: Prevent declining already processed expenses
        if expense.approved or expense.declined:
            messages.warning(request, "This expense has already been processed.")
            return redirect('expense:expense_approvals')

        expense.declined = True
        expense.declined_at = timezone.now()
        expense.decline_reason = reason
        expense.approved_by = request.user
        expense.save()

        messages.success(request, "Expense has been declined successfully.")
    else:
        messages.error(request, "Invalid request method.")

    return redirect('expense:expense_approvals')
@login_required
def make_payment(request):
    """Handle payments for approved expenses via selected method"""
    user = request.user
    company = getattr(user, 'company', None)
    if not company and hasattr(user, 'staffprofile'):
        company = getattr(user.staffprofile, 'company', None)

    if not company:
        messages.error(request, "User is not associated with any company.")
        return redirect('wallet:staff-dashboard')

    if request.method == 'POST':
        expense_id = request.POST.get('expense')
        payment_method = request.POST.get('payment_method')
        amount = request.POST.get('amount')

        # Validate essential fields
        if not all([expense_id, payment_method, amount]):
            messages.error(request, "All required fields must be filled.")
            return redirect('wallet:staff-dashboard')
        
        expense = get_object_or_404(Expense, id=expense_id)

        if not expense.approved or expense.declined:
            messages.error(request, 'Payment can only be made for approved expenses.')
            return redirect('wallet:staff-dashboard')

        # Convert and validate amount matches exactly
        try:
            input_amount = Decimal(amount)
            if input_amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid amount provided.")
            return redirect('wallet:staff-dashboard')

        # Check exact match
        if input_amount != expense.amount:
            messages.error(request, f"Amount must match the approved expense amount of KES {expense.amount}.")
            return redirect('wallet:staff-dashboard')

        # Use only the validated expense.amount
        amount = expense.amount


        if not expense.approved or expense.declined:
            messages.error(request, 'Payment can only be made for approved expenses.')
            return redirect('wallet:staff-dashboard')

        wallet = expense.wallet

        # Capture extra fields depending on method
        extra_info = {}
        if payment_method == 'mpesa_number':
            mpesa_number = request.POST.get('mpesa_number')
            if not mpesa_number or not mpesa_number.isdigit() or len(mpesa_number) != 9:
                messages.error(request, 'Invalid M-Pesa number.')
                return redirect('wallet:staff-dashboard')
            extra_info['mpesa_number'] = f'+254{mpesa_number}'

        elif payment_method == 'paybill_number':
            paybill_number = request.POST.get('paybill_number')
            account_number = request.POST.get('account_number')
            if not (paybill_number and account_number):
                messages.error(request, 'Paybill and account number are required.')
                return redirect('wallet:staff-dashboard')
            extra_info['paybill_number'] = paybill_number
            extra_info['account_number'] = account_number

        elif payment_method == 'till_number':
            till_number = request.POST.get('till_number')
            if not till_number or not till_number.isdigit():
                messages.error(request, 'Invalid Till number.')
                return redirect('wallet:staff-dashboard')
            extra_info['till_number'] = till_number

        else:
            messages.error(request, 'Invalid payment method selected.')
            return redirect('wallet:staff-dashboard')

        # Process the payment
        try:
            with transaction.atomic():
                wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

                if wallet.balance >= amount:
                    wallet.balance -= amount
                    wallet.save()

                    Transaction.objects.create(
                        company=company,
                        user=user,
                        sender=user,
                        sender_wallet=wallet,
                        amount=amount,
                        description=(
                            f"Payment for expense #{expense.id}: "
                            f"{getattr(expense, 'title', '')} via {payment_method} ({extra_info})"
                        ),
                        status="completed",
                        transaction_type="withdraw",
                    )

                    expense.paid = True
                    expense.save()

                    messages.success(request, f'Payment of KES {amount} made successfully via {payment_method}.')
                else:
                    messages.error(request, f'Insufficient funds in wallet. Available balance: KES {wallet.balance}')

        except Exception as e:
            messages.error(request, f'An error occurred during payment: {str(e)}')

    return redirect('wallet:staff-dashboard')

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
    print(trend_chart)

    # Prepare category distribution data
    category_data = expenses.values('expense_category__name') \
        .annotate(total=Sum('amount')) \
        .order_by('-total')
    pie_chart = {
        'labels': [c['expense_category__name'] or 'Uncategorized' for c in category_data],
        'amounts': [float(c['total']) for c in category_data],
    }

    context = {
        'categories': ExpenseCategory.objects.filter(is_active=True),
        'request_types': ExpenseRequestType.objects.filter(is_active=True),
        'events': Event.objects.filter(is_active=True, company=company),
        'operations': Operation.objects.filter(is_active=True, company=company),
        'trend_chart': trend_chart,
        'pie_chart': pie_chart,
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

@require_GET
@login_required
def analytics_data(request):
    user = request.user
    company = getattr(user, 'staffprofile', None) and user.staffprofile.company or getattr(user, 'companykyc', None)

    if not company:
        return JsonResponse({'error': 'No associated company'}, status=400)

    # Optional: filter by date range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    print(start_date, end_date)


    expenses = Expense.objects.filter(company=company)
    # if start_date and end_date:
    #     expenses = expenses.filter(created_at__range=[start_date, end_date])
    if start_date and end_date:
        start_date = timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
        end_date = timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d")) + timezone.timedelta(days=1)
        expenses = expenses.filter(created_at__range=[start_date, end_date])

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

    return JsonResponse({
        'trend_chart': trend_chart,
        'pie_chart': pie_chart,
    })
