from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.views.decorators.http import require_POST
from django.urls import reverse
from .models import Expense, Event, Operation, ExpenseGroup, CategoryBase, ExpenseCategory, EventCategory, OperationCategory
from .forms import ExpenseRequestForm, ExpenseApprovalForm, PaymentForm, EventExpenseForm, OperationExpenseForm
from wallet.models import Transaction, CompanyKYC, Wallet

from decimal import Decimal, InvalidOperation
from django.db.models import Q

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
    if request.method == 'POST':
        form_type = request.POST.get('request_type')
        if not form_type or form_type not in ['event', 'operation']:
            messages.error(request, "Please select a valid request type")
            return redirect('wallet:staff-dashboard')

        # try:
        #     wallet = Wallet.objects.get(user=request.user)
        # except Wallet.DoesNotExist:
        #     messages.error(request, "You don't have a wallet. Please create one first.")
        #     return redirect('wallet:staff-dashboard')

        if form_type == 'event':
            wallet = Wallet.objects.get(company = request.user.staffprofile.company, wallet_type="EVENT")    
            return _handle_event_expense(request, wallet)
        else:
            wallet = Wallet.objects.get(company = request.user.staffprofile.company, wallet_type="OPERATIONS")
            return _handle_operation_expense(request, wallet)

def _handle_event_expense(request, wallet):
    event_name = request.POST.get('event_name')
    event_category_id = request.POST.get('event_category')
    start_date = request.POST.get('event_start_date')
    end_date = request.POST.get('event_end_date')
    budget = request.POST.get('event_budget')
    description = request.POST.get('event_description')
    project_lead = request.POST.get('event_project_lead')
    location = request.POST.get('event_location')
    
    # company_id = request.POST.get('company')
    company = CompanyKYC.objects.filter(id=request.user.staffprofile.company.id).first()

    if not all([event_name, event_category_id, start_date, end_date, budget, project_lead, location]):
        messages.error(request, "Please fill in all required event fields")
        return redirect('wallet:staff-dashboard')

    try:
        budget = Decimal(budget)
        event_category = EventCategory.objects.get(id=event_category_id)

        event = Event.objects.create(
            name=event_name,
            category=event_category,
            company=company,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            description=description,
            project_lead=project_lead,
            location=location,
            created_by=request.user
        )

        expense_group = ExpenseGroup.EVENT

        expense = Expense.objects.create(
            wallet=wallet,
            amount=budget,
            expense_group=expense_group,
            event=event,
            operation=None,
            company=company,
            created_by=request.user
        )
        print(expense)

        messages.success(request, f"Event expense '{event_name}' created successfully")
        return redirect('wallet:staff-dashboard')

    except EventCategory.DoesNotExist:
        messages.error(request, "Selected event category does not exist")
    except ValueError:
        messages.error(request, "Invalid budget value")
    except Exception as e:
        messages.error(request, f"Error creating event expense: {str(e)}")
    
    return redirect('wallet:staff-dashboard')


def _handle_operation_expense(request, wallet):
    operation_name = request.POST.get('operation_name')
    operation_category_id = request.POST.get('operation_category')
    budget = request.POST.get('operation_budget')
    description = request.POST.get('operation_description')
    project_lead = request.POST.get('operation_project_lead', '')

    # company_id = request.POST.get('company')
    company = CompanyKYC.objects.filter(id=request.user.staffprofile.company.id).first()

    # company = CompanyKYC.objects.filter(id=company_id).first() if company_id else None

    if not all([operation_name, operation_category_id, budget]):
        messages.error(request, "Please fill in all required operation fields")
        return redirect('wallet:staff-dashboard')

    try:
        budget = Decimal(budget)
        operation_category = OperationCategory.objects.get(id=operation_category_id)

        operation = Operation.objects.create(
            name=operation_name,
            category=operation_category,
            company=company,
            budget=budget,
            description=description,
            project_lead=project_lead,
            created_by=request.user
        )

        expense_group =ExpenseGroup.OPERATION

        expense = Expense.objects.create(
            wallet=wallet,
            amount=budget,
            expense_group=expense_group,
            event=None,
            operation=operation,
            company=company,
            created_by=request.user
        )

        messages.success(request, f"Operation expense '{operation_name}' created successfully")
        return redirect('wallet:staff-dashboard')

    except OperationCategory.DoesNotExist:
        messages.error(request, "Selected operation category does not exist")
    except ValueError:
        messages.error(request, "Invalid budget value")
    except Exception as e:
        messages.error(request, f"Error creating operation expense: {str(e)}")
    
    return redirect('wallet:staff-dashboard')



@login_required
@require_POST
def create_event(request):
    """
    Handle event creation from modal form with hard-coded fields
    """
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    
    try:
        # Extract and sanitize form data
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        budget_str = request.POST.get('budget')
        project_lead_id = request.POST.get('project_lead')
        location = request.POST.get('location', '').strip()
        
        # Validate required fields
        if not all([name, category_id, start_date, end_date, budget_str, project_lead_id]):
            return JsonResponse({
                'success': False, 
                'message': 'All fields are required'
            })
        
        # Convert budget to Decimal
        try:
            budget = Decimal(budget_str)
            if budget <= 0:
                return JsonResponse({
                    'success': False, 
                    'message': 'Budget must be greater than zero'
                })
        except (InvalidOperation, TypeError):
            return JsonResponse({
                'success': False, 
                'message': 'Please enter a valid budget amount'
            })
        
        # Get category
        try:
            category = ExpenseCategory.objects.get(
                Q(company=company) | Q(is_global=True),
                id=category_id,
                category_type='event'
                
            )
        except ExpenseCategory.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Invalid category selected'
            })
        
        # Create and save event
        event = Event(
            name=name,
            category=category,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            project_lead_id=project_lead_id,
            location=location,
            company=company,
            created_by=user
        )
        event.save()
        
        return JsonResponse({
            'success': True,
            'id': event.id,
            'name': event.name,
            'message': 'Event created successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })


@login_required
@require_POST
def create_operation(request):
    """
    Handle operation creation from modal form with hard-coded fields
    """
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    
    try:
        # Extract and sanitize form data
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        budget_str = request.POST.get('budget')
        project_lead_id = request.POST.get('project_lead')
        
        # Validate required fields
        if not all([name, category_id, budget_str, project_lead_id]):
            return JsonResponse({
                'success': False, 
                'message': 'All fields are required'
            })
        
        # Convert budget to Decimal
        try:
            budget = Decimal(budget_str)
            if budget <= 0:
                return JsonResponse({
                    'success': False, 
                    'message': 'Budget must be greater than zero'
                })
        except (InvalidOperation, TypeError):
            return JsonResponse({
                'success': False, 
                'message': 'Please enter a valid budget amount'
            })
        
        # Get category
        try:
            category = ExpenseCategory.objects.get(
                Q(company=company) | Q(is_global=True),
                id=category_id,
                category_type='operation'
            )
        except ExpenseCategory.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Invalid category selected'
            })
        
        # Create and save operation
        operation = Operation(
            name=name,
            category=category,
            budget=budget,
            project_lead_id=project_lead_id,
            company=company,
            created_by=user
        )
        operation.save()
        
        return JsonResponse({
            'success': True,
            'id': operation.id,
            'name': operation.name,
            'message': 'Operation created successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })
@login_required
def expense_detail(request, expense_id):
    user = request.user
    expense = get_object_or_404(Expense, id=expense_id)

    # Permission check
    if not is_admin(user) and expense.created_by != user:
        return HttpResponseForbidden("You don't have permission to view this expense")
    
    company = getattr(user, 'company', None) or getattr(user.staffprofile, 'company', None)

    approval_form = None
    if is_admin(user) and not expense.approved and not expense.declined:
        approval_form = ExpenseApprovalForm(instance=expense)

    payment_form = None
    if expense.approved and not expense.declined:
        payment_form = PaymentForm(user=user, company=company, initial={'expense': expense})

    context = {
        'expense': expense,
        'approval_form': approval_form,
        'payment_form': payment_form,
        'is_admin': is_admin(user),
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
                
                return redirect('expense:expense_detail', expense_id=expense.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return redirect('expense:expense_detail', expense_id=expense.id)

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

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Invalid amount provided.")
            return redirect('wallet:staff-dashboard')

        expense = get_object_or_404(Expense, id=expense_id)

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



@login_required
def create_event_ajax(request):
    """AJAX endpoint for creating events"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': 'Invalid request'})
    
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    
    if request.method == 'POST':
        form = EventExpenseForm(request.POST, user=user, company=company)
        
        if form.is_valid():
            event = form.save()
            return JsonResponse({
                'success': True,
                'event_id': event.id,
                'event_name': event.name
            })
        else:
            errors = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors})
    
    return JsonResponse({'success': False, 'errors': 'Invalid request method'})


@login_required
def create_operation_ajax(request):
    """AJAX endpoint for creating operations"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': 'Invalid request'})
    
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    
    if request.method == 'POST':
        form = OperationExpenseForm(request.POST, user=user, company=company)
        
        if form.is_valid():
            operation = form.save()
            return JsonResponse({
                'success': True,
                'operation_id': operation.id,
                'operation_name': operation.name
            })
        else:
            errors = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors})
    
    return JsonResponse({'success': False, 'errors': 'Invalid request method'})


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