from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.urls import reverse
from .models import Expense, Wallet, Event, Operation, ExpenseGroup
from .forms import ExpenseRequestForm, ExpenseApprovalForm, PaymentForm
from wallet.models import Transaction, CompanyKYC
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
    """Handle expense submission"""
    user = request.user
    company = user.staffprofile.company if hasattr(user, 'staffprofile') else None
    
    if request.method == 'POST':
        form = ExpenseRequestForm(request.POST, user=user, company=company)
        
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = user
            expense.company = company
            
            # Check if wallet has sufficient funds
            wallet = expense.wallet
            amount = expense.amount
            
            if wallet.balance >= amount:
                expense.save()
                messages.success(request, 'Expense request submitted successfully.')
                return redirect('wallet:staff-dashboard')
            else:
                messages.error(request, f'Insufficient funds in wallet. Available balance: {wallet.balance}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ExpenseRequestForm(user=user, company=company)
    
    return render(request, 'users/staff/staff.html', {'form': form})

@login_required
def expense_detail(request, expense_id):
    """Show expense details"""
    user = request.user
    expense = get_object_or_404(Expense, id=expense_id)
    
    # Check if user has access to this expense
    if not is_admin(user) and expense.created_by != user:
        return HttpResponseForbidden("You don't have permission to view this expense")
    
    approval_form = None
    if is_admin(user) and not expense.approved and not expense.declined:
        approval_form = ExpenseApprovalForm(instance=expense)
    
    payment_form = None
    if expense.approved and not expense.declined:
        payment_form = PaymentForm(user=user, initial={'expense': expense})
    
    context = {
        'expense': expense,
        'approval_form': approval_form,
        'payment_form': payment_form,
        'is_admin': is_admin(user),
    }
    
    return render(request, 'expense_detail.html', context)

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
                
                return redirect('expense_detail', expense_id=expense.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return redirect('expense_detail', expense_id=expense.id)

@login_required
def make_payment(request):
    """Handle payments for approved expenses"""
    user = request.user
    company = getattr(user, 'company', None) or getattr(user.staffprofile, 'company', None)

    if request.method == 'POST':
        form = PaymentForm(request.POST, user=user, company=company)        
        if form.is_valid():
            expense = form.cleaned_data['expense']

            if not expense.approved or expense.declined:
                messages.error(request, 'Payment can only be made for approved expenses.')
                return redirect('wallet:staff-dashboard')

            wallet = expense.wallet
            amount = expense.amount

            with transaction.atomic():
                if wallet.balance >= amount:
                    wallet.balance -= amount
                    wallet.save()

                    Transaction.objects.create(
                        company=company,
                        user=user,
                        sender=user,
                        sender_wallet=wallet,
                        amount=amount,
                        description=f"Payment for expense #{expense.id}: {expense.title if hasattr(expense, 'title') else ''}",
                        status="completed",
                        transaction_type="withdraw",  # or "request_settled" if this was part of a payment request
                    )

                    expense.paid = True
                    expense.save()

                    messages.success(request, f'Payment of {amount} made successfully.')
                else:
                    messages.error(request, f'Insufficient funds in wallet. Available balance: {wallet.balance}')
        else:
            messages.error(request, 'Please correct the errors below.')

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