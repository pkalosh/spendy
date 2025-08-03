import json
import logging
import uuid
import re
from itertools import chain
from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from wallet.forms import KYCForm, StaffProfileForm, UserForm,RoleForm,WalletForm
from expense.forms import ExpenseRequestForm ,ExpenseApprovalForm,EventExpenseForm,OperationExpenseForm
from django.contrib import messages
from wallet.models import Wallet, Notification, Transaction,CompanyKYC, StaffProfile,Role,MpesaTransaction,MpesaCallbackLog
from expense.models import ExpenseCategory, OperationCategory, EventCategory,Expense,ExpenseRequestType
from userauths.models import User
from django.core.paginator import Paginator
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.html import escape
from django.http import JsonResponse,HttpResponseForbidden
from django.db import transaction
from django.core.paginator import Paginator
from datetime import datetime
import csv
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from .models import Wallet, Transaction, TransactionFee,Client,Brand
from .utility import NotificationService,  notify_expense_workflow
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from .mpesa_service import MpesaDaraja
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum

logger = logging.getLogger(__name__)

def is_admin(user):
    return user.is_authenticated and user.is_admin

@login_required
def settings_view(request):
    """View for system settings page"""
    company = get_object_or_404(CompanyKYC, user=request.user)
    
    # Fetch clients and their related brands for the current company
    clients = Client.objects.filter(company=company, is_active=True).prefetch_related('brands').order_by('name')

    context = {
        'expense_categories': ExpenseCategory.objects.filter(company=company, is_active=True).order_by('name'),
        'operation_categories': OperationCategory.objects.filter(company=company, is_active=True).order_by('name'),
        'event_categories': EventCategory.objects.filter(company=company, is_active=True).order_by('name'),
        'clients': clients, # Add clients to the context
    }
    return render(request, 'settings.html', context)


# --- Client Views ---
@login_required
@require_POST
def add_client(request):
    company = get_object_or_404(CompanyKYC, user=request.user)
    name = request.POST.get('name')
    if name:
        Client.objects.create(
            company=company, 
            name=name,
            contact_person=request.POST.get('contact_person'),
            contact_email=request.POST.get('contact_email'),
            contact_phone=request.POST.get('contact_phone'),
            address=request.POST.get('address'),
            city=request.POST.get('city'),
            country=request.POST.get('country'),
            website=request.POST.get('website'),
            industry=request.POST.get('industry'),
            notes=request.POST.get('notes'),
        )
        # Consider adding a success message here
    return redirect('wallet:settings_view') # Redirect back to the settings page

@login_required
@require_POST
def edit_client(request):
    client_id = request.POST.get('client_id')
    client = get_object_or_404(Client, id=client_id, company__user=request.user)
    
    client.name = request.POST.get('name')
    client.contact_person = request.POST.get('contact_person')
    client.contact_email = request.POST.get('contact_email')
    client.contact_phone = request.POST.get('contact_phone')
    client.address = request.POST.get('address')
    client.city = request.POST.get('city')
    client.country = request.POST.get('country')
    client.website = request.POST.get('website')
    client.industry = request.POST.get('industry')
    client.notes = request.POST.get('notes')
    client.save()
    # Consider adding a success message here
    return redirect('wallet:settings_view')

@login_required
@require_POST
def delete_client(request):
    client_id = request.POST.get('client_id')
    client = get_object_or_404(Client, id=client_id, company__user=request.user)
    client.delete() # This will also delete all related brands due to CASCADE
    # Consider adding a success message here
    return redirect('wallet:settings_view')

# --- Brand Views ---
@login_required
@require_POST
def add_brand(request):
    client_id = request.POST.get('client_id')
    print(client_id)
    client = get_object_or_404(Client, id=client_id, company__user=request.user)
    name = request.POST.get('name')
    logo = request.FILES.get('logo') # For file uploads
    
    if name:
        Brand.objects.create(
            client=client,
            name=name,
            logo=logo,
            description=request.POST.get('description'),
            website=request.POST.get('website'),
        )
        # Consider adding a success message here
    return redirect('wallet:settings_view')

@login_required
@require_POST
def edit_brand(request):
    brand_id = request.POST.get('brand_id')
    brand = get_object_or_404(Brand, id=brand_id, client__company__user=request.user)
    
    brand.name = request.POST.get('name')
    brand.description = request.POST.get('description')
    brand.website = request.POST.get('website')
    if 'logo' in request.FILES: # Handle logo update
        brand.logo = request.FILES['logo']
    elif 'clear_logo' in request.POST: # Optional: add a checkbox in modal to clear logo
        brand.logo = None
    brand.save()
    # Consider adding a success message here
    return redirect('wallet:settings_view')

@login_required
@require_POST
def delete_brand(request):
    brand_id = request.POST.get('brand_id')
    brand = get_object_or_404(Brand, id=brand_id, client__company__user=request.user)
    brand.delete()
    # Consider adding a success message here
    return redirect('wallet:settings_view')

@login_required
def add_expense_category(request):
    """Add a new expense category"""
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            company = get_object_or_404(CompanyKYC,user=request.user)
            ExpenseCategory.objects.create(
                name=name,
                company  = company,
                created_by=request.user
            )
            messages.success(request, 'Expense category added successfully')
        else:
            messages.error(request, 'Category name is required')
    return redirect('wallet:settings_view')

@login_required
def add_operation_category(request):
    """Add a new operation category"""
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            company = get_object_or_404(CompanyKYC,user=request.user)
            OperationCategory.objects.create(
                name=name,
                company  = company,
                created_by=request.user
            )
            messages.success(request, 'Operation category added successfully')
        else:
            messages.error(request, 'Category name is required')
    return redirect('wallet:settings_view')

@login_required
def add_event_category(request):
    """Add a new event category"""
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            company = get_object_or_404(CompanyKYC,user=request.user)
            EventCategory.objects.create(
                name=name,
                company  = company,
                created_by=request.user
            )
            messages.success(request, 'Event category added successfully')
        else:
            messages.error(request, 'Category name is required')
    return redirect('wallet:settings_view')

@login_required
def edit_category(request):
    """Edit a category (expense, operation, or event)"""
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        # Get category_type from POST data first, then fall back to GET
        category_type = request.POST.get('category_type') or request.GET.get('type')
        name = request.POST.get('name')
        
        # Debug logging (remove in production)
        print(f"Edit Category - ID: {category_id}, Type: {category_type}, Name: {name}")
        print(f"POST data: {request.POST}")
        print(f"GET data: {request.GET}")
        
        if not all([category_id, category_type, name]):
            messages.error(request, 'Missing required information')
            return redirect('wallet:settings_view')
        
        try:
            if category_type == 'expense':
                category = ExpenseCategory.objects.get(id=category_id)
            elif category_type == 'operation':
                category = OperationCategory.objects.get(id=category_id)
            elif category_type == 'event':
                category = EventCategory.objects.get(id=category_id)
            else:
                messages.error(request, 'Invalid category type')
                return redirect('wallet:settings_view')
            
            # Update the category name
            category.name = name.strip()
            category.save()
            
            messages.success(request, f'{category_type.title()} category updated successfully')
            
        except (ExpenseCategory.DoesNotExist, OperationCategory.DoesNotExist, EventCategory.DoesNotExist):
            messages.error(request, 'Category not found')
        except Exception as e:
            messages.error(request, f'Error updating category: {str(e)}')
    
    return redirect('wallet:settings_view')

@login_required
def delete_category(request):
    """Delete a category (expense, operation, or event)"""
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        # Get category_type from POST data first, then fall back to GET
        category_type = request.POST.get('category_type') or request.GET.get('type')
        
        if not all([category_id, category_type]):
            messages.error(request, 'Missing required information')
            return redirect('wallet:settings_view')
        
        try:
            if category_type == 'expense':
                category = ExpenseCategory.objects.get(id=category_id)
                
                # Check for related Expense records
                related_expenses = Expense.objects.filter(expense_category=category)
                paid_expenses_count = related_expenses.filter(paid=True).count()
                unpaid_expenses_count = related_expenses.filter(paid=False).count()
                
                if related_expenses.exists():
                    if paid_expenses_count > 0:
                        # If there are paid expenses, deactivate the category instead of deleting
                        category.is_active = False
                        category.save()
                        messages.warning(request, 
                            f'Expense category "{category.name}" has {paid_expenses_count} paid expense(s). '
                            f'Category has been deactivated instead of deleted.')
                    else:
                        # If all expenses are unpaid, we can delete the category and related expenses
                        related_expenses.delete()
                        category.delete()
                        messages.success(request, 
                            f'Expense category "{category.name}" and {unpaid_expenses_count} '
                            f'unpaid expense(s) deleted successfully')
                else:
                    # No related expenses, safe to delete
                    category.delete()
                    messages.success(request, f'Expense category "{category.name}" deleted successfully')
                    
            elif category_type == 'operation':
                category = OperationCategory.objects.get(id=category_id)
                
                # Check for related Operation records
                related_operations = Operation.objects.filter(category=category)
                paid_operations_count = related_operations.filter(paid=True).count()
                unpaid_operations_count = related_operations.filter(paid=False).count()
                
                if related_operations.exists():
                    if paid_operations_count > 0:
                        # If there are paid operations, deactivate the category instead of deleting
                        category.is_active = False
                        category.save()
                        messages.warning(request, 
                            f'Operation category "{category.name}" has {paid_operations_count} paid operation(s). '
                            f'Category has been deactivated instead of deleted.')
                    else:
                        # If all operations are unpaid, we can delete the category and related operations
                        related_operations.delete()
                        category.delete()
                        messages.success(request, 
                            f'Operation category "{category.name}" and {unpaid_operations_count} '
                            f'unpaid operation(s) deleted successfully')
                else:
                    # No related operations, safe to delete
                    category.delete()
                    messages.success(request, f'Operation category "{category.name}" deleted successfully')
                    
            elif category_type == 'event':
                category = EventCategory.objects.get(id=category_id)
                
                # Check for related Event records
                related_events = Event.objects.filter(category=category)
                paid_events_count = related_events.filter(paid=True).count()
                unpaid_events_count = related_events.filter(paid=False).count()
                
                if related_events.exists():
                    if paid_events_count > 0:
                        # If there are paid events, deactivate the category instead of deleting
                        category.is_active = False
                        category.save()
                        messages.warning(request, 
                            f'Event category "{category.name}" has {paid_events_count} paid event(s). '
                            f'Category has been deactivated instead of deleted.')
                    else:
                        # If all events are unpaid, we can delete the category and related events
                        related_events.delete()
                        category.delete()
                        messages.success(request, 
                            f'Event category "{category.name}" and {unpaid_events_count} '
                            f'unpaid event(s) deleted successfully')
                else:
                    # No related events, safe to delete
                    category.delete()
                    messages.success(request, f'Event category "{category.name}" deleted successfully')
            else:
                messages.error(request, 'Invalid category type')
                return redirect('wallet:settings_view')
                
        except (ExpenseCategory.DoesNotExist, OperationCategory.DoesNotExist, EventCategory.DoesNotExist):
            messages.error(request, 'Category not found')
        except Exception as e:
            messages.error(request, f'Error deleting category: {str(e)}')
    
    return redirect('wallet:settings_view')

@login_required
@user_passes_test(is_admin)
def list_staff_profiles(request):
    staff_list = StaffProfile.objects.filter(company=request.user.companykyc).all()
    paginator = Paginator(staff_list, 10)  # 10 per page
    page_number = request.GET.get('page')
    staffs = paginator.get_page(page_number)
    return render(request, 'users/staff/list.html', {'staffs': staffs})



@login_required
def get_staff_profile(request, pk):

    staff = get_object_or_404(StaffProfile, pk=pk)
    
    # Debug - verify the staffprofile is accessible
    print(f"Current user: {request.user.username}")
    print(f"Has staffprofile: {hasattr(request.user, 'staffprofile')}")
    if hasattr(request.user, 'staffprofile'):
        print(f"StaffProfile ID: {request.user.staffprofile.id}")
    
    context = {
        'staff': staff,
    }
    return render(request, 'users/staff/detail.html', context)


from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string

random_password = get_random_string(length=12)

@login_required
@user_passes_test(is_admin)
def create_staff_profile(request):
    company  = request.user.companykyc
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        profile_form = StaffProfileForm(request.POST, request.FILES)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save(commit=False)

            # Generate and set random password
            
            user.set_password(user_form.cleaned_data['password'])
            # Assign appropriate user flags for staff
            user.is_staff = True
            user.company_name = company.company_name
            user.is_org_staff = True
            user.is_verified = True
            user.save()

            staff = profile_form.save(commit=False)
            staff.user = user
            staff.company  = company
            staff.save()
            profile_form.save_m2m()

            # Optional: log password, send via email, or display once
            print(f"Generated password for {user.email}: {random_password}")

            return redirect('wallet:staff-list')
    else:
        user_form = UserForm()
        profile_form = StaffProfileForm()
    return render(request, 'users/staff/create.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })
@login_required
def update_staff_profile(request, pk):
    staff = get_object_or_404(StaffProfile, pk=pk)
    user = staff.user
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        profile_form = StaffProfileForm(request.POST, request.FILES, instance=staff)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('wallet:staff-list')
    else:
        user_form = UserForm(instance=user)
        profile_form = StaffProfileForm(instance=staff)
    return render(request, 'users/staff/update.html', {'user_form': user_form, 'profile_form': profile_form, 'staff': staff})

@login_required
@user_passes_test(is_admin)
def delete_staff_profile(request, pk):
    staff = get_object_or_404(StaffProfile, pk=pk)
    if request.method == 'POST':
        staff.user.delete()  # Deletes the user and cascades to staff
        return redirect('wallet:staff-list')
    return render(request, 'users/staff/delete.html', {'staff': staff})




@login_required
def edit_wallet(request, wallet_id):
    """
    Handle wallet editing without using Django forms.
    Only wallet_name and wallet_type are editable.
    """
    wallet = get_object_or_404(Wallet, id=wallet_id)

    # Prevent editing of PRIMARY wallets
    if wallet.wallet_type == 'PRIMARY':
        messages.error(request, "PRIMARY wallets cannot be edited.")
        return redirect('wallet:wallet')

    # Permission check
    if wallet.user != request.user:
        messages.error(request, "You don't have permission to edit this wallet.")
        return redirect('wallet:wallet')

    if request.method == 'POST':
        wallet_name = request.POST.get('wallet_name', '').strip()
        wallet_type = request.POST.get('wallet_type', '').strip().upper()

        # Validate allowed wallet types
        ALLOWED_TYPES = ['EVENT', 'OPERATIONS', 'EMERGENCY']
        if wallet_type not in ALLOWED_TYPES:
            messages.error(request, f"Invalid wallet type selected: {wallet_type}")
            return redirect('wallet:wallet')

        # Ensure name is not empty
        if not wallet_name:
            messages.error(request, "Wallet name cannot be empty.")
            return redirect('wallet:wallet')

        # Save changes
        wallet.wallet_name = wallet_name
        wallet.wallet_type = wallet_type
        wallet.save()

        messages.success(request, f'Wallet "{wallet_name}" has been updated successfully.')

        return redirect('wallet:wallet')
    else:
        messages.error(request, "Invalid request method.")
        return redirect('wallet:wallet')

@login_required
@require_http_methods(["POST"])
def delete_wallet(request, wallet_id):
    """
    Delete wallet view with balance transfer to PRIMARY wallet.
    PRIMARY wallets cannot be deleted.
    """
    wallet = get_object_or_404(Wallet, id=wallet_id)

    # Prevent deletion of PRIMARY wallets
    if wallet.wallet_type == 'PRIMARY':
        messages.error(request, "PRIMARY wallets cannot be deleted.")
        return redirect('wallet:wallet')

    # Optional: Add permission check
    if hasattr(wallet, 'user') and wallet.user != request.user:
        messages.error(request, "You don't have permission to delete this wallet.")
        return redirect('wallet:wallet')

    try:
        transaction_count = Transaction.objects.filter(
            Q(sender_wallet=wallet) | Q(receiver_wallet=wallet)
        ).count()

        expense_count = 0  # Update this if using Expense model

        wallet_name = wallet.wallet_name
        balance_transfer_note = ""

        with transaction.atomic():
            if wallet.balance > 0:
                # Look for another PRIMARY wallet
                primary_wallets = Wallet.objects.filter(user=request.user, wallet_type='PRIMARY')
                
                if not primary_wallets.exists():
                    messages.error(request, "Cannot delete wallet with balance. No PRIMARY wallet found to transfer funds.")
                    return redirect('wallet:wallet')
                
                # Prefer active wallet if multiple PRIMARY wallets exist
                primary_wallet = primary_wallets.filter(is_active=True).first() or primary_wallets.first()
                
                # Perform balance transfer
                primary_wallet.balance += wallet.balance
                balance_transfer_note = f"Transferred {wallet.currency} {wallet.balance} to PRIMARY wallet '{primary_wallet.wallet_name}'."
                primary_wallet.save()

                # Log a transaction
                Transaction.objects.create(
                    user=request.user,
                    sender_wallet=wallet,
                    receiver_wallet=primary_wallet,
                    amount=wallet.balance,
                    company=wallet.company,
                    status="completed",
                    transaction_type="Transfer",
                    description=f"Auto-transfer during deletion of wallet '{wallet.wallet_name}'."
                )

                wallet.balance = 0
                wallet.is_active = False
                wallet.save()

            if transaction_count > 0 or expense_count > 0:
                error_msg = []
                if transaction_count > 0:
                    error_msg.append(f"{transaction_count} transaction(s)")
                if expense_count > 0:
                    error_msg.append(f"{expense_count} expense(s)")

                messages.error(
                    request,
                    f"Cannot delete wallet '{wallet.wallet_name}'. It still has {', '.join(error_msg)}."
                )
                return redirect('wallet:wallet')

            wallet.delete()
            messages.success(request, f'Wallet "{wallet_name}" has been deleted successfully. {balance_transfer_note}')

    except Exception as e:
        messages.error(request, f'Error deleting wallet: {str(e)}')

    return redirect('wallet:wallet')



# Helper function to get wallet dependencies (optional)
def get_wallet_dependencies(wallet):
    """
    Get all dependencies for a wallet
    Returns a dictionary with counts and details
    """
    dependencies = {
        'transactions': [],
        'expenses': [],
        'can_delete': True,
        'reasons': []
    }
    
    try:
        # Get related transactions
        transactions = Transaction.objects.filter(wallet=wallet)
        dependencies['transactions'] = list(transactions.values(
            'id', 'amount', 'date', 'description'
        ))
        
        # Get related expenses (adjust based on your model)
        # expenses = Expense.objects.filter(wallet=wallet)
        # dependencies['expenses'] = list(expenses.values(
        #     'id', 'amount', 'date', 'description'
        # ))
        
        # Check balance
        if wallet.balance > 0:
            dependencies['reasons'].append(f"Wallet has balance: {wallet.currency} {wallet.balance}")
            dependencies['can_delete'] = False
        
        # Check transactions
        if len(dependencies['transactions']) > 0:
            dependencies['reasons'].append(f"Wallet has {len(dependencies['transactions'])} transaction(s)")
            dependencies['can_delete'] = False
        
        # Check expenses
        if len(dependencies['expenses']) > 0:
            dependencies['reasons'].append(f"Wallet has {len(dependencies['expenses'])} expense(s)")
            dependencies['can_delete'] = False
        
    except Exception as e:
        dependencies['can_delete'] = False
        dependencies['reasons'].append(f"Error checking dependencies: {str(e)}")
    
    return dependencies


@login_required
@user_passes_test(is_admin)
def create_wallet(request):
    if request.method == 'POST':
        wallet_name = request.POST.get('wallet_name', '').strip()
        balance = request.POST.get('balance', '0').strip()
        wallet_type = request.POST.get('wallet_type')
        
        # Sanitize input
        wallet_name = escape(wallet_name)
        
        try:
            balance = float(balance)
            if balance < 0:
                balance = 0
        except ValueError:
            balance = 0
        
        # Validation checks
        if not wallet_name:
            messages.error(request, "Wallet name is required.")
            return redirect('wallet:wallet')
        
        # Deny PRIMARY wallet type creation
        if wallet_type == 'PRIMARY':
            messages.error(request, "PRIMARY wallet type cannot be created.")
            return redirect('wallet:wallet')
        
        # Check if similar wallet_type already exists for the company
        existing_wallet = Wallet.objects.filter(
            wallet_type=wallet_type,
            company=request.user.companykyc
        ).first()
        
        if existing_wallet:
            messages.error(request, f"A wallet of type '{wallet_type}' already exists for your company.")
            return redirect('wallet:wallet')
        
        # Create the wallet if all validations pass
        wallet = Wallet(
            wallet_name=wallet_name,
            balance=balance,
            user=request.user,
            wallet_type=wallet_type,
            company=request.user.companykyc
        )
        wallet.save()
        messages.success(request, f"Wallet '{wallet.wallet_name}' created successfully!")
        return redirect('wallet:wallet')
    
    return redirect('wallet:wallet')

from django.db import transaction as db_transaction

@login_required
@user_passes_test(is_admin)
def wallet_transfer(request):
    if request.method == 'POST':
        from_wallet_id = request.POST.get('from_wallet_id')
        to_wallet_id = request.POST.get('to_wallet_id')
        amount_str = request.POST.get('amount')
        description = request.POST.get('description', '').strip()  # Optional description
        
        if not all([from_wallet_id, to_wallet_id, amount_str]):
            messages.error(request, "All fields are required.")
            return redirect('wallet:wallet')
        
        if from_wallet_id == to_wallet_id:
            messages.error(request, "Source and destination wallets must be different.")
            return redirect('wallet:wallet')
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except:
            messages.error(request, "Amount must be a positive number.")
            return redirect('wallet:wallet')
        
        # Fetch wallets by ID
        from_wallet = get_object_or_404(Wallet, id=from_wallet_id, company=request.user.companykyc)
        to_wallet = get_object_or_404(Wallet, id=to_wallet_id, company=request.user.companykyc)
        
        if from_wallet.balance < amount:
            messages.error(request, "Insufficient balance in the source wallet.")
            return redirect('wallet:wallet')
        
        # Use database transaction for atomicity
        try:
            with db_transaction.atomic():
                # Perform wallet balance updates
                from_wallet.balance -= amount
                to_wallet.balance += amount
                from_wallet.save()
                to_wallet.save()
                
                # Create transaction record
                transaction_record = Transaction.objects.create(
                    company=request.user.companykyc,
                    user=request.user,  # Admin who performed the transfer
                    amount=amount,
                    description=description or f"Transfer from {from_wallet.wallet_name} to {to_wallet.wallet_name}",
                    sender=request.user,  # Admin as sender
                    receiver=request.user,  # Same company transfer, so same user context
                    sender_wallet=from_wallet,
                    receiver_wallet=to_wallet,
                    status="completed",  # Internal transfer is immediately completed
                    transaction_type="transfer"
                )
                
                messages.success(
                    request,
                    f"Transferred KES {amount} from {from_wallet.wallet_name.title()} to {to_wallet.wallet_name.title()}. Transaction ID: {transaction_record.transaction_id}"
                )
                
        except Exception as e:
            messages.error(request, f"Transfer failed: {str(e)}")
            return redirect('wallet:wallet')
        
        return redirect('wallet:wallet')
    
    messages.error(request, "Invalid request method.")
    return redirect('wallet:wallet')


@login_required
@user_passes_test(is_admin)
def fund_wallet(request):
    if request.method == 'POST':
        # Get form data matching your template field names
        amount_str = request.POST.get('amount')
        wallet_id = request.POST.get('wallet_id')
        payment_method = request.POST.get('payment_method')
        
        # Get payment method specific fields
        mpesa_number = request.POST.get('mpesa_number')  # For direct M-Pesa payment
        paybill_number = request.POST.get('paybill_number')  # For paybill payment
        till_number = request.POST.get('till_number')  # For till payment
        account_reference = request.POST.get('account_reference')  # For paybill
        till_reference = request.POST.get('till_reference')  # For till
        
        # Basic validation
        if not all([amount_str, wallet_id, payment_method]):
            messages.error(request, "All fields are required.")
            return redirect('wallet:wallet')
        
        # Validate amount
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            messages.error(request, "Amount must be a positive number.")
            return redirect('wallet:wallet')
        
        # Get wallet
        try:
            wallet = get_object_or_404(Wallet, id=int(wallet_id), company=request.user.companykyc)
        except ValueError:
            messages.error(request, "Invalid wallet ID.")
            return redirect('wallet:wallet')
        
        # Validate payment method specific fields
        business_id = None
        payment_details = {}
        
        if payment_method == 'mpesa_number':
            if not mpesa_number:
                messages.error(request, "M-Pesa number is required for direct payment.")
                return redirect('wallet:wallet')
            
            # Validate phone number format (should start with 254)
            if not mpesa_number.startswith('254') or len(mpesa_number) != 12:
                messages.error(request, "Please enter a valid M-Pesa number (254XXXXXXXXX).")
                return redirect('wallet:wallet')
            
            business_id = mpesa_number
            actual_payment_method = 'stk'  # STK push for direct M-Pesa
            payment_details = {'mpesa_number': mpesa_number}
            
        elif payment_method == 'paybill_number':
            if not paybill_number or not account_reference:
                messages.error(request, "Paybill details are missing.")
                return redirect('wallet:wallet')
            
            business_id = paybill_number
            actual_payment_method = 'b2b'  # B2B for paybill
            payment_details = {
                'paybill_number': paybill_number,
                'account_reference': account_reference
            }
            
        elif payment_method == 'till_number':
            if not till_number or not till_reference:
                messages.error(request, "Till number details are missing.")
                return redirect('wallet:wallet')
            
            business_id = till_number
            actual_payment_method = 'b2b'  # B2B for till
            payment_details = {
                'till_number': till_number,
                'till_reference': till_reference
            }
            
        else:
            messages.error(request, "Invalid payment method selected.")
            return redirect('wallet:wallet')
        
        # Create initial transaction record
        transaction = Transaction.objects.create(
            sender_wallet=wallet,
            user=request.user,
            company=request.user.companykyc,
            transaction_type='FUNDING',
            amount=amount,
            status='PENDING',
            payment_method=payment_method,
            sender=request.user,
            description=f"Wallet funding via {payment_method}",
            payment_details={
                'payment_details': payment_details,
                'business_id': business_id,
                'actual_payment_method': actual_payment_method,
                'initiated_at': timezone.now().isoformat()
            }
        )
        
        # Initialize M-Pesa client
        mpesa = MpesaDaraja()
        
        try:
            if actual_payment_method == 'stk':
                # STK Push - Customer pays to business (M-Pesa direct payment)
                response = initiate_stk_push(mpesa, business_id, amount, wallet, transaction)
                success_message = "Payment request sent to your phone. Please check your M-Pesa and enter your PIN to complete the transaction."
                
            elif actual_payment_method == 'b2b':
                # B2B - Business to business payment (Paybill/Till)
                if payment_method == 'paybill_number':
                    success_message = f"Payment instructions provided. Please use Paybill {paybill_number} with account number {account_reference} to complete your payment of KES {amount}."
                else:  # till_number
                    success_message = f"Payment instructions provided. Please use Till {till_number} with reference {till_reference} to complete your payment of KES {amount}."
                
                # For manual payments (paybill/till), you might want to create a pending transaction
                # that gets confirmed via callback when the user actually pays
                response = initiate_b2b_payment(mpesa, business_id, amount, wallet, transaction)
            
            # Handle response and update transaction
            if response and response.get('ResponseCode') == '0':
                # Update transaction with success details
                transaction.status = 'PROCESSING'
                transaction.external_reference = response.get('MerchantRequestID') or response.get('ConversationID')
                transaction.checkout_request_id = response.get('CheckoutRequestID')
                transaction.payment_details.update({
                    'mpesa_response': response,
                    'response_code': response.get('ResponseCode'),
                    'response_description': response.get('ResponseDescription'),
                    'updated_at': timezone.now().isoformat()
                })
                transaction.save()
                
                messages.success(request, success_message)
                logger.info(f"Payment initiated for wallet {wallet_id}, Transaction ID: {transaction.id}, Response: {response}")
                
            else:
                # Update transaction with failure details
                error_msg = response.get('errorMessage', 'Payment initiation failed') if response else 'No response from payment gateway'
                transaction.status = 'FAILED'
                transaction.failure_reason = error_msg
                transaction.payment_details.update({
                    'mpesa_response': response,
                    'error_message': error_msg,
                    'failed_at': timezone.now().isoformat()
                })
                transaction.save()
                
                messages.error(request, f"Payment failed: {error_msg}")
                logger.error(f"Payment failed for wallet {wallet_id}, Transaction ID: {transaction.id}, Response: {response}")
                
        except Exception as e:
            # Update transaction with exception details
            transaction.status = 'FAILED'
            transaction.failure_reason = f"Exception: {str(e)}"
            transaction.payment_details.update({
                'exception': str(e),
                'exception_type': type(e).__name__,
                'failed_at': timezone.now().isoformat()
            })
            transaction.save()
            
            logger.error(f"Error processing payment: {str(e)}, Transaction ID: {transaction.id}")
            messages.error(request, f"Payment processing error: {str(e)}")
        
        return redirect('wallet:wallet')
    
    else:
        messages.error(request, "Invalid request method.")
        return redirect('wallet:wallet')

def initiate_stk_push(mpesa, phone_number, amount, wallet, transaction=None):
    """
    Initiate STK Push for wallet funding
    Customer pays money to fund their wallet
    """
    # Format phone number (ensure it starts with 254)
    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif phone_number.startswith('+254'):
        phone_number = phone_number[1:]
    elif not phone_number.startswith('254'):
        phone_number = '254' + phone_number
    
    account_reference = f"{wallet.company.company_name}-{wallet.wallet_number}"
    transaction_desc = f"Wallet funding for {wallet.company.company_name}"
    
    # Add transaction reference if provided
    if transaction:
        account_reference = f"TXN-{transaction.id}-{account_reference}"
        transaction_desc = f"{transaction_desc} (Ref: {transaction.id})"
    
    response = mpesa.stk_push(
        phone_number=phone_number,
        amount=int(amount),
        account_reference=account_reference,
        transaction_desc=transaction_desc
    )
    
    # Log STK push initiation
    if transaction:
        transaction.payment_details.update({
            'stk_push_details': {
                'phone_number': phone_number,
                'account_reference': account_reference,
                'transaction_desc': transaction_desc,
                'initiated_at': timezone.now().isoformat()
            }
        })
        transaction.mpesa_checkout_request_id = response.get('CheckoutRequestID')
        transaction.merchant_request_id = response.get('MerchantRequestID')
        transaction.save()
    
    return response

def initiate_b2c_payment(mpesa, phone_number, amount, wallet, transaction=None):
    """
    Initiate B2C payment
    Business sends money to customer (e.g., refunds, bonuses)
    """
    # Format phone number
    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif phone_number.startswith('+254'):
        phone_number = phone_number[1:]
    elif not phone_number.startswith('254'):
        phone_number = '254' + phone_number
    
    remarks = f"Wallet credit for {wallet.company.company_name}"
    occasion = f"Wallet funding - {wallet.id}"
    
    if transaction:
        remarks = f"{remarks} (Ref: {transaction.id})"
        occasion = f"{occasion} - TXN:{transaction.id}"
    
    response = mpesa.b2c_payment(
        amount=float(amount),
        phone_number=phone_number,
        remarks=remarks,
        command_id='BusinessPayment',  # or 'SalaryPayment', 'PromotionPayment'
        occasion=occasion
    )
    
    # Log B2C payment initiation
    if transaction:
        transaction.payment_details.update({
            'b2c_payment_details': {
                'phone_number': phone_number,
                'remarks': remarks,
                'occasion': occasion,
                'initiated_at': timezone.now().isoformat()
            }
        })
        transaction.conversation_id = response.get('ConversationID')
        print(f"conversation_id: {transaction.conversation_id}")  # Print the value of transaction.mpesa_checkout_request_id)
        transaction.originator_conversation_id = response.get('OriginatorConversationID')
        transaction.save()
    
    return response

def initiate_b2b_payment(mpesa, business_id, amount, wallet, transaction=None):
    """
    Initiate B2B payment
    Business to business payment
    """
    account_reference = f"{wallet.company.company_name}-{wallet.wallet_number}"
    remarks = f"Wallet funding for {wallet.company.company_name}"
    
    if transaction:
        account_reference = account_reference
        remarks = f"{remarks} (Ref: {transaction.id})"
    
    response = mpesa.b2b_payment(
        amount=float(amount),
        receiver_shortcode=business_id,
        account_reference=account_reference,
        remarks=remarks,
        command_id='BusinessPayBill'  # or 'BusinessBuyGoods' for till numbers
    )
    
    # Log B2B payment initiation
    if transaction:
        transaction.payment_details.update({
            'b2b_payment_details': {
                'receiver_shortcode': business_id,
                'account_reference': account_reference,
                'remarks': remarks,
                'initiated_at': timezone.now().isoformat()
            }
        })
        transaction.conversation_id = response.get('ConversationID')
        print(f"conversation_id: {transaction.conversation_id}")  # Print the value of transaction.mpesa_checkout_request_id)
        transaction.originator_conversation_id = response.get('OriginatorConversationID')
        transaction.save()
    
    return response


@login_required
def wallet(request):
    if request.user.is_authenticated:
        try:
            kyc = CompanyKYC.objects.get(user=request.user)
            
            # Check if all required fields are filled
            required_fields = [
                kyc.company_name,
                kyc.logo,
                kyc.kra_pin,
                kyc.registration_certificate,
                kyc.country,
                kyc.county,
                kyc.city,
                kyc.address,
                kyc.mobile
            ]
            
            if not all(required_fields) or not kyc.kyc_submitted:
                messages.warning(request, "Your KYC is incomplete. Please fill all required fields.")
                return redirect("wallet:kyc-reg")

            if not kyc.kyc_confirmed:
                messages.warning(request, "Your KYC is Under Review.")
                return redirect("wallet:kyc-reg")

            # Get wallets
            wallets = Wallet.objects.filter(user=request.user, is_active=True, company=kyc)
            primary_wallet = Wallet.objects.get(user=request.user, wallet_type="PRIMARY", company=kyc)
            
            # Get all transactions for the company
            all_transactions = Transaction.objects.filter(company=kyc).order_by('-date')
            
            # Get recent transactions for initial display (limit 20 for performance)
            recent_txns = all_transactions[:20]
            
            # Get all unique users for filter dropdown
            all_users = Transaction.objects.filter(company=kyc).values_list(
                'receiver', 'receiver_wallet'
            ).distinct()
            
            # Format users for dropdown
            unique_users = []
            for name, wallet in all_users:
                if name:
                    unique_users.append({'id': wallet, 'name': name})
                else:
                    unique_users.append({'id': wallet, 'name': wallet})

        except CompanyKYC.DoesNotExist:
            messages.warning(request, "You need to submit your KYC")
            return redirect("wallet:kyc-reg")
        except Wallet.DoesNotExist:
            messages.error(request, "Wallet not found")
            return redirect("userauths:sign-up")
    else:
        messages.warning(request, "You need to login to access the dashboard")
        return redirect("userauths:sign-in")

    context = {
        "kyc": kyc,
        "wallets": wallets,
        "primary_wallet": primary_wallet,
        "transactions": recent_txns,
        "all_transactions": all_transactions,  # For JavaScript processing
        "all_users": unique_users,
    }
    return render(request, "account/account.html", context)


@login_required
def get_transaction_details(request, transaction_id):
    """API endpoint to get detailed transaction information"""
    try:
        kyc = CompanyKYC.objects.get(user=request.user)
        transaction = Transaction.objects.get(id=transaction_id, company=kyc)
        
        # Generate reference code
        reference_code = f"SPNDY{transaction.created_at.strftime('%y%m%d')}{transaction.id:03d}"
        
        transaction_data = {
            'id': transaction.id,
            'reference': reference_code,
            'recipient_name': transaction.recipient_name or transaction.recipient_wallet,
            'recipient_wallet': transaction.recipient_wallet,
            'from_wallet_name': transaction.from_wallet.wallet_name if transaction.from_wallet else 'Primary Wallet',
            'from_wallet_id': transaction.from_wallet.wallet_id if transaction.from_wallet else '',
            'date': transaction.created_at.strftime('%d %b %Y'),
            'time': transaction.created_at.strftime('%I:%M %p'),
            'amount': float(transaction.amount),
            'status': transaction.status,
            'transaction_type': transaction.transaction_type,
            'category': transaction.category or '',
            'description': transaction.description or '',
        }
        
        return JsonResponse(transaction_data)
    
    except (Transaction.DoesNotExist, CompanyKYC.DoesNotExist):
        return JsonResponse({'error': 'Transaction not found'}, status=404)


@login_required
def filter_transactions(request):
    """API endpoint to filter transactions"""
    if request.method == 'GET':
        try:
            kyc = CompanyKYC.objects.get(user=request.user)
            
            # Get filter parameters
            user_filter = request.GET.get('user', '')
            date_from = request.GET.get('date_from', '')
            date_to = request.GET.get('date_to', '')
            status_filter = request.GET.get('status', '')
            page = int(request.GET.get('page', 1))
            
            # Start with all transactions
            transactions = Transaction.objects.filter(company=kyc)
            
            # Apply filters
            if user_filter:
                transactions = transactions.filter(
                    Q(recipient_name__icontains=user_filter) |
                    Q(recipient_wallet__icontains=user_filter)
                )
            
            if date_from:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                transactions = transactions.filter(created_at__date__gte=date_from_obj)
            
            if date_to:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                transactions = transactions.filter(created_at__date__lte=date_to_obj)
            
            if status_filter:
                transactions = transactions.filter(status=status_filter)
            
            # Order by date
            transactions = transactions.order_by('-created_at')
            
            # Paginate
            paginator = Paginator(transactions, 10)  # 10 transactions per page
            page_obj = paginator.get_page(page)
            
            # Prepare response data
            transaction_list = []
            for transaction in page_obj:
                reference_code = f"SPNDY{transaction.created_at.strftime('%y%m%d')}{transaction.id:03d}"
                
                transaction_list.append({
                    'id': transaction.id,
                    'recipient_name': transaction.recipient_name or '',
                    'recipient_wallet': transaction.recipient_wallet,
                    'from_wallet_name': transaction.from_wallet.wallet_name if transaction.from_wallet else 'Primary Wallet',
                    'from_wallet_id': transaction.from_wallet.wallet_id if transaction.from_wallet else '',
                    'date': transaction.created_at.strftime('%d %b %Y'),
                    'time': transaction.created_at.strftime('%I:%M %p'),
                    'datetime': transaction.created_at.strftime('%Y-%m-%d %H:%M'),
                    'reference': reference_code,
                    'amount': float(transaction.amount),
                    'status': transaction.status,
                    'transaction_type': transaction.transaction_type or 'wallet_transfer',
                    'category': transaction.category or '',
                    'description': transaction.description or '',
                })
            
            return JsonResponse({
                'transactions': transaction_list,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
            })
            
        except CompanyKYC.DoesNotExist:
            return JsonResponse({'error': 'KYC not found'}, status=404)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)
@login_required
def kyc_registration(request):
    user = request.user
    
    # Only admin users should access the KYC registration
    if not user.is_admin:
        messages.error(request, "Only admin users can submit KYC information.")
        return redirect("wallet:staff-dashboard")  # Redirect non-admin users back to wallet
    
    all_fields = False  # Default to False
    
    try:
        kyc = CompanyKYC.objects.get(user=user)
        required_fields = [
            kyc.company_name,
            kyc.logo,
            kyc.kra_pin,
            kyc.registration_certificate,
            kyc.country,
            kyc.county,
            kyc.city,
            kyc.address,
            kyc.mobile
        ]
        if all(required_fields) and kyc.kyc_submitted:
            all_fields = True
    except CompanyKYC.DoesNotExist:
        kyc = None
        all_fields = False
    wallet = Wallet.objects.filter(company=kyc,wallet_type="PRIMARY",is_active=True).first()

    if request.method == "POST":
        form = KYCForm(request.POST, request.FILES, instance=kyc)
        if form.is_valid():
            new_form = form.save(commit=False)
            new_form.user = user
            new_form.status = "pending"
            new_form.kyc_submitted = True  # Mark as submitted
            new_form.save()
            messages.success(request, "KYC Form submitted successfully, In review now.")
            return redirect("wallet:wallet")
    else:
        form = KYCForm(instance=kyc)
        
    context = {
        "account": wallet,
        "form": form,
        "kyc": kyc,
        "all_fields": all_fields
    }
    
    return render(request, "account/kyc-form.html", context)



@login_required
def transactions(request):
    """
    Display transactions with filtering, pagination, and export capabilities.
    """
    # Get all transactions for the user's company
    company = get_object_or_404(CompanyKYC, user=request.user)
    txn_queryset = Transaction.objects.filter(company=company).select_related(
        'user', 'receiver', 'sender_wallet', 'receiver_wallet'
    ).order_by('-date')
    
    # Get filter parameters from request
    user_filter = request.GET.get('user', '')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Apply filters
    if user_filter:
        txn_queryset = txn_queryset.filter(
            Q(user__id=user_filter) | Q(receiver__id=user_filter)
        )
    
    if status_filter:
        txn_queryset = txn_queryset.filter(status=status_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            txn_queryset = txn_queryset.filter(date__date__gte=date_from_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            txn_queryset = txn_queryset.filter(date__date__lte=date_to_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter

    # Handle Exporting Data before pagination
    export_format = request.GET.get('export')
    if export_format:
        if export_format == 'csv':
            return export_to_csv(txn_queryset)
        elif export_format == 'excel':
            return export_to_excel(txn_queryset)
        elif export_format == 'pdf':
            return export_to_pdf(txn_queryset)
    
    # Get all users associated with transactions for the filter dropdown
    transaction_user_ids = set()
    all_company_transactions = Transaction.objects.filter(company=company)
    for txn in all_company_transactions:
        transaction_user_ids.add(txn.user.id)
        if txn.receiver:
            transaction_user_ids.add(txn.receiver.id)
    
    users = User.objects.filter(id__in=transaction_user_ids).order_by('first_name', 'last_name', 'email')
    
    # Count transactions by status for dashboard stats before pagination
    status_counts = {
        'total': txn_queryset.count(),
        'completed': txn_queryset.filter(status='completed').count(),
        'pending': txn_queryset.filter(status='pending').count(),
        'failed': txn_queryset.filter(status='failed').count(),
        'cancelled': txn_queryset.filter(status='cancelled').count(),
    }
    
    # Pagination
    paginator = Paginator(txn_queryset, 10)  # Show 20 transactions per page
    page_number = request.GET.get('page', 1)
    transactions_page = paginator.get_page(page_number)
    
    # Create query parameters for pagination links to preserve filters
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    base_query_string = query_params.urlencode()
    
    context = {
        "transactions": transactions_page,
        "users": users,
        "status_counts": status_counts,
        "base_query_string": base_query_string,
        # Preserve filter values for the form
        "current_filters": {
            "user": user_filter,
            "status": status_filter,
            "date_from": date_from,
            "date_to": date_to,
        }
    }
    
    return render(request, "transaction/transactions.html", context)


# --- Export Functions ---

def export_to_csv(queryset):
    """
    Exports a queryset of transactions to a CSV file.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Transaction ID', 'Initiated By', 'Recipient', 'Amount', 'Status', 'Type', 'Date', 'Description'])
    
    for txn in queryset:
        writer.writerow([
            txn.transaction_id,
            txn.user.get_full_name() or txn.user.username,
            txn.receiver.get_full_name() if txn.receiver else "-",
            f"{txn.sender_wallet.currency if txn.sender_wallet else 'KES'} {txn.amount}",
            txn.status.title(),
            txn.transaction_type.replace('_', ' ').title(),
            txn.date.strftime('%Y-%m-%d %H:%M:%S'),
            txn.description or "-"
        ])
        
    return response


def export_to_excel(queryset):
    """
    Exports a queryset of transactions to an Excel file.
    """
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="transactions.xlsx"'
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Transactions"
    
    columns = ['Transaction ID', 'Initiated By', 'Recipient', 'Amount', 'Status', 'Type', 'Date', 'Description']
    ws.append(columns)
    
    for txn in queryset:
        ws.append([
            txn.transaction_id,
            txn.user.get_full_name() or txn.user.username,
            txn.receiver.get_full_name() if txn.receiver else "-",
            f"{txn.sender_wallet.currency if txn.sender_wallet else 'KES'} {txn.amount}",
            txn.status.title(),
            txn.transaction_type.replace('_', ' ').title(),
            txn.date.strftime('%Y-%m-%d %H:%M:%S'),
            txn.description or "-"
        ])
        
    wb.save(response)
    return response

def export_to_pdf(queryset):
    """
    Exports a queryset of transactions to a PDF file.
    """
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="transactions.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(letter))
    elements = []
    
    data = [['ID', 'Initiated By', 'Recipient', 'Amount', 'Status', 'Type', 'Date']]
    for txn in queryset:
        data.append([
            txn.transaction_id,
            (txn.user.get_full_name() or txn.user.username)[:20],
            (txn.receiver.get_full_name() or "-")[:20] if txn.receiver else "-",
            f"{txn.amount}",
            txn.status.title(),
            txn.transaction_type.replace('_', ' ').title(),
            txn.date.strftime('%Y-%m-%d %H:%M')
        ])

    table = Table(data)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    table.setStyle(style)

    elements.append(table)
    doc.build(elements)
    
    return response

@login_required
def transaction_export(request):
    """
    Export transactions to CSV (optional feature)
    """
    import csv
    from django.http import HttpResponse
    
    user = request.user
    company = get_object_or_404(CompanyKYC, user=request.user)
    
    # Apply same filters as the main view
    txn_queryset = Transaction.objects.filter(company=company).select_related(
        'user', 'receiver', 'sender_wallet', 'receiver_wallet'
    ).order_by('-date')
    
    # Apply filters from GET parameters (same logic as main view)
    user_filter = request.GET.get('user', '')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if user_filter:
        txn_queryset = txn_queryset.filter(
            Q(user__id=user_filter) | Q(receiver__id=user_filter)
        )
    
    if status_filter:
        txn_queryset = txn_queryset.filter(status=status_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            txn_queryset = txn_queryset.filter(date__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            txn_queryset = txn_queryset.filter(date__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Create HTTP response with CSV content type
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    
    writer = csv.writer(response)
    
    # Write CSV header
    writer.writerow([
        'Reference Code',
        'Initiated By',
        'Recipient',
        'Amount',
        'Currency',
        'Type',
        'Status',
        'Date & Time',
        'Description',
        'Sender Wallet',
        'Receiver Wallet'
    ])
    
    # Write transaction data
    for txn in txn_queryset:
        # Format transaction type
        txn_type = txn.transaction_type
        if txn_type == 'send_money':
            txn_type = 'Send Money'
        elif txn_type == 'till':
            txn_type = 'Till Payment'
        elif txn_type == 'paybill':
            txn_type = 'Paybill'
        else:
            txn_type = txn_type.title()
        
        writer.writerow([
            txn.transaction_id,
            txn.user.get_full_name() or txn.user.username,
            txn.receiver.get_full_name() if txn.receiver else '-',
            f"{txn.amount:.2f}",
            txn.sender_wallet.currency if txn.sender_wallet else 'KES',
            txn_type,
            txn.status.title(),
            txn.date.strftime('%Y-%m-%d %H:%M:%S'),
            txn.description or '',
            txn.sender_wallet.wallet_id if txn.sender_wallet else '',
            txn.receiver_wallet.wallet_id if txn.receiver_wallet else ''
        ])
    
    return response


@login_required
def expenses(request):
    user = request.user
    company = get_object_or_404(CompanyKYC, user=user)
    events = Event.objects.filter(company=company, is_active=True)
    operations = Operation.objects.filter(company=company, is_active=True)
    event_form = EventExpenseForm()
    operation_form = OperationExpenseForm()
    all_items =  list(events) + list(operations)
    context = {
        'all_items': all_items ,
        'event_form': event_form,
        'operation_form': operation_form,
        'event_categories': EventCategory.objects.filter(company=company,is_active=True),
        'operation_categories': OperationCategory.objects.filter(company=company,is_active=True),
    }
    return render(request, "expenses/expense.html", context)

def create_expenses(request):
    user = request.user
    txn = Transaction.objects.all()

    context = {
        "transactions": txn,
    }
    return render(request, "expenses/expense.html", context)

def list_roles(request):
    user = request.user
    txn = Role.objects.all()

    context = {
        "transactions": txn,
    }
    return render(request, "transaction/roles.html", context)

def create_roles(request):
    user = request.user
    form = RoleForm()

    context = {
        "form": form,
    }
    return render(request, "transaction/create_role.html", context)

@login_required
def dashboard(request):
    # Redirect if user is not an admin
    if not request.user.is_admin:
        messages.warning(request, "Only admin users can access the dashboard.")
        return redirect("wallet:staff-dashboard")

    form = KYCForm()
    wallet_form = WalletForm()

    try:
        kyc = CompanyKYC.objects.get(user=request.user)
    except CompanyKYC.DoesNotExist:
        messages.warning(request, "You need to submit your KYC")
        return redirect("wallet:kyc-reg")

    # Check required KYC fields
    required_fields = [
        kyc.company_name,
        kyc.logo,
        kyc.kra_pin,
        kyc.registration_certificate,
        kyc.country,
        kyc.county,
        kyc.city,
        kyc.address,
        kyc.mobile
    ]
    if not all(required_fields) or not kyc.kyc_submitted:
        messages.warning(request, "Your KYC is incomplete. Please fill all required fields.")
        return redirect("wallet:kyc-reg")

    if not kyc.kyc_confirmed and kyc.status != "approved":
        messages.warning(request, "Your KYC is under review.")
        return redirect("wallet:kyc-reg")

    # Fetch transactions and wallets
    # transactions = Transaction.objects.filter(company=kyc).order_by("-id")
    transactions_queryset = Transaction.objects.filter(company=kyc).order_by("-id")

    paginator = Paginator(transactions_queryset, 10)  # Show 10 per page
    page_number = request.GET.get("page")
    transactions = paginator.get_page(page_number)

    primary_wallets = Wallet.objects.filter(company=kyc, wallet_type="PRIMARY").order_by("-id")
    wallets = Wallet.objects.filter(company=kyc).exclude(wallet_type="PRIMARY").order_by("-id")

    # Combine wallets for utilization tracking
    all_wallets = list(primary_wallets) + list(wallets)

    for wallet in all_wallets:
        approved_paid_tx = Transaction.objects.filter(
            company=kyc,
            sender_wallet=wallet,
            status = "completed"
        )

        total_utilized = approved_paid_tx.aggregate(total=Sum('amount'))['total'] or 0

        if wallet.balance and wallet.balance > 0:
            utilization = round((total_utilized / wallet.balance) * 100, 2)
        else:
            utilization = None

        # Attach data to each wallet instance
        wallet.utilization = utilization
        wallet.total_utilized = total_utilized

    context = {
        "kyc": kyc,
        "total_requests": Expense.objects.filter(company=kyc).count(),
        "pending_requests": Expense.objects.filter(company=kyc, approved=False, declined=False, paid=False).count(),
        "completed_requests": Expense.objects.filter(company=kyc, approved=True, declined=False, paid=True).count(),
        "declined_requests": Expense.objects.filter(company=kyc, declined=True).count(),
        "wallets": wallets,
        "primary_wallets": primary_wallets,
        "form": form,
        "wallet_form": wallet_form,
        "transactions": transactions,
    }

    return render(request, "account/dashboard.html", context)


@login_required
def notifications(request):
    alerts = Notification.objects.filter(user=request.user)
    pending = alerts.filter(is_read=False).count()
    alert_type = request.GET.get('type')
    if alert_type:
        alerts = alerts.filter(notification_type=alert_type)

    paginator = Paginator(alerts.order_by('-date'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'notifications.html', {'alerts': page_obj, 'pending': pending})


@login_required
def staff_notifications(request):
    alerts = Notification.objects.filter(user=request.user)
    pending = alerts.filter(is_read=False).count()
    alert_type = request.GET.get('type')
    if alert_type:
        alerts = alerts.filter(notification_type=alert_type)

    paginator = Paginator(alerts.order_by('-date'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'staffnotification.html', {'alerts': page_obj, 'pending': pending})


@login_required
@require_POST
def mark_alert_as_read(request):
    alert_id = request.POST.get("alert_id")
    try:
        alert = Notification.objects.get(id=alert_id, user=request.user)
        alert.is_read = True
        alert.save()
        return JsonResponse({"success": True})
    except Notification.DoesNotExist:
        return HttpResponseForbidden("Alert not found or permission denied.")




from django.http import HttpResponse, JsonResponse
from expense.models import Expense, ExpenseGroup,Event,Operation
from expense.forms import ExpenseRequestForm, PaymentForm
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation
from django.db.models import Q
@login_required
def staff_dashboard(request):
    """
    Staff dashboard view showing user transactions and company wallets.
    Requires authentication and proper staff profile.
    """
    context = {}
    user = request.user
    
    try:
        # Get staff profile
        company = StaffProfile.objects.get(user=request.user)
        
        # Get transactions and wallets
        transactions = Transaction.objects.filter(sender=request.user).order_by("-id")
        wallets = Wallet.objects.filter(company=company.company).order_by("-id").exclude(wallet_type="PRIMARY")
        
        # Add to context
        context["transactions"] = transactions
        context["wallets"] = wallets
        
        expenses = Expense.objects.filter(company=company.company, created_by=request.user).order_by('-created_at')
        pending_expenses = expenses.filter(approved=False, declined=False)
        approved_expenses = expenses.filter(approved=True, paid=False)
        declined_expenses = expenses.filter(declined=True)
        print(f"approved_expenses: {approved_expenses}")  # Print the value of approved_expenses)

        payment_form = PaymentForm(user=user, company=company.company)
        expense_form = ExpenseRequestForm(company=company.company)

        

        
        # user1 = get_object_or_404(User, id=user.id)
        wallet = get_pending_approved_expense_sum(user)
        
        context["pending_expenses"] = pending_expenses
        context["approved_expenses"] = approved_expenses
        context["declined_expenses"] = declined_expenses
        context["expense_form"] = expense_form

        context["wallet"] = wallet
        context['request_type']  = ExpenseRequestType.objects.filter(
            Q(company=company.company)
        )
        context["events"] = Event.objects.filter(
            company=company.company, 
            approved=False,
            paid=False
        ).order_by("-created_at")
        context["operations"] = Operation.objects.filter(
            company=company.company, 
            approved=False,
            paid=False
        )
        
        context['event_categories']  = EventCategory.objects.filter(
            Q(company=company.company)
        )
        context['operation_categories']  = OperationCategory.objects.filter(
            Q(company=company.company)
        )
        context['expense_categories']  = ExpenseCategory.objects.filter(
            Q(company=company.company)
        )
        context['payment_form'] = payment_form

        return render(request, "users/staff/staff.html", context)
        
    except StaffProfile.DoesNotExist as e:
        if request.user.is_admin:
            return redirect("wallet:staff-dashboard")
        # Log the error
        print(f"Staff profile error: {e}")
        # Add error message to be displayed on the page
        messages.error(request, "Staff profile not found. Please contact administrator.")
        # Return to a simple error template or the login page
        return render(request, "error_template.html", {"error": "Staff profile not found"}, status=404)


@login_required
def expense_requests(request):
    """
    Staff requests view showing pending and declined expenses, events, and operations.
    Focuses on request-related features.
    Requires authentication and proper staff profile.
    """
    context = {}
    user = request.user
    try:
        # Get staff profile
        company = StaffProfile.objects.get(user=request.user)
        
        # Get expense information
        expenses = Expense.objects.filter(company=company.company, created_by=request.user).order_by('-created_at')
        pending_expenses = expenses.filter(approved=False, declined=False)
        declined_expenses = expenses.filter(declined=True)
        approved_expenses = expenses.filter(approved=True, paid=False)
        
        # Set up expense request form
        expense_form = ExpenseRequestForm(company=company.company)
        
        # Add to context
        context["pending_expenses"] = pending_expenses
        context["declined_expenses"] = declined_expenses
        context["expense_form"] = expense_form
        context["approved_expenses"] = approved_expenses
        
        # Get request types and categories
        context['request_types'] = ExpenseRequestType.objects.filter(Q(company=company.company))
        context['expense_categories'] = ExpenseCategory.objects.filter(Q(company=company.company))
        
        # Get events information
        context["events"] = Event.objects.filter(
            company=company.company,
            approved=False,
            paid=False
        ).order_by("-created_at")
        context['event_categories'] = EventCategory.objects.filter(Q(company=company.company))
        
        # Get operations information
        context["operations"] = Operation.objects.filter(
            company=company.company,
            approved=False,
            paid=False
        )
        context['operation_categories'] = OperationCategory.objects.filter(Q(company=company.company))
        
        return render(request, "users/staff/request.html", context)
    
    except StaffProfile.DoesNotExist as e:
        # Log the error
        print(f"Staff profile error: {e}")
        # Add error message to be displayed on the page
        messages.error(request, "Staff profile not found. Please contact administrator.")
        # Return to a simple error template or the login page
        return render(request, "error_template.html", {"error": "Staff profile not found"}, status=404)


def get_pending_approved_expense_sum(user):
    """
    Returns the sum of all approved but unpaid expenses created by the user
    and belonging to the user's company.
    """
    try:
        company = user.staffprofile.company
    except AttributeError:
        # If the user has no staff profile or company
        return Decimal('0.00')

    result = Expense.objects.filter(
        approved=True,
        paid=False,
        created_by=user,
        company=company
    ).aggregate(total=Sum('amount'))

    return result['total'] or Decimal('0.00')




#Mpesa c2b, b2b, b2c callbacks

@csrf_exempt
@require_http_methods(["POST"])
def stk_push_callback(request):
    """
    Enhanced STK Push callback handler
    Handles responses from M-Pesa STK Push requests and updates both MpesaTransaction and Transport models
    """
    try:
        callback_data = json.loads(request.body)
        logger.info(f"Wallet funding STK Push callback received: {callback_data}")
        
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        merchant_request_id = stk_callback.get('MerchantRequestID')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')

        # Find the MpesaTransaction in database
        mpesa_transaction = None
        try:
            mpesa_transaction = MpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id,
                merchant_request_id=merchant_request_id
            )
        except MpesaTransaction.DoesNotExist:
            logger.error(f"MpesaTransaction not found for CheckoutRequestID: {checkout_request_id}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'MpesaTransaction not found'})

        # Find related Transaction record for wallet funding
        funding_transaction = None
        try:
            funding_transaction = Transaction.objects.get(
                merchant_request_id=merchant_request_id,
                mpesa_checkout_request_id=checkout_request_id)
        except Transaction.DoesNotExist:
            # Try to find by checkout request ID only
            try:
                funding_transaction = Transaction.objects.filter(
                    mpesa_checkout_request_id=checkout_request_id,
                    transaction_type='FUNDING'
                ).first()
            except Exception:
                logger.error(f"No wallet funding Transaction record found for CheckoutRequestID: {checkout_request_id}")

        with transaction.atomic():
            # Update MpesaTransaction based on result code
            if result_code == 0:  # Success
                # Extract callback metadata
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                metadata_dict = {}
                for item in callback_metadata:
                    name = item.get('Name')
                    value = item.get('Value')
                    if name and value is not None:
                        metadata_dict[name] = value

                # Update MpesaTransaction with success details
                mpesa_transaction.status = 'COMPLETED'
                mpesa_transaction.mpesa_receipt_number = metadata_dict.get('MpesaReceiptNumber')
                mpesa_transaction.transaction_date = timezone.now()
                mpesa_transaction.phone_number = metadata_dict.get('PhoneNumber')
                mpesa_transaction.amount = metadata_dict.get('Amount', mpesa_transaction.amount)
                mpesa_transaction.result_code = result_code
                mpesa_transaction.result_desc = result_desc
                mpesa_transaction.callback_data = callback_data
                mpesa_transaction.save()

                logger.info(f"Wallet funding STK Push completed successfully: {mpesa_transaction.mpesa_receipt_number}")
                print(f"Wallet funding STK Push completed successfully: {mpesa_transaction.mpesa_receipt_number}")

                # Update wallet funding Transaction record if found
                if funding_transaction:
                    funding_transaction.status = "COMPLETED"
                    funding_transaction.completed_at = timezone.now()
                    funding_transaction.payment_completed = True
                    funding_transaction.paid_at = timezone.now()
                    
                    # Update payment_details with callback details
                    current_payment_details = funding_transaction.payment_details or {}
                    current_payment_details.update({
                        'callback_data': callback_data,
                        'mpesa_receipt_number': metadata_dict.get('MpesaReceiptNumber'),
                        'phone_number': metadata_dict.get('PhoneNumber'),
                        'amount_paid': str(metadata_dict.get('Amount')),
                        'transaction_cost': str(metadata_dict.get('TransactionCost', 0)),
                        'payment_date': timezone.now().isoformat(),
                        'result_code': result_code,
                        'result_desc': result_desc,
                        'payment_status': 'COMPLETED'
                    })
                    funding_transaction.payment_details = current_payment_details
                    
                    # Check amount mismatch
                    callback_amount = metadata_dict.get('Amount')
                    if callback_amount and Decimal(str(callback_amount)) != funding_transaction.amount:
                        logger.warning(f"Amount mismatch - Expected: {funding_transaction.amount}, Received: {callback_amount}")
                        funding_transaction.payment_details.update({
                            'amount_mismatch': True,
                            'actual_amount_paid': str(callback_amount),
                            'expected_amount': str(funding_transaction.amount)
                        })

                    # Get the company from the transaction and update primary wallet
                    company = funding_transaction.company
                    try:
                        primary_wallet = Wallet.objects.get(company=company, wallet_type="PRIMARY")
                        old_balance = primary_wallet.balance
                        # Use the actual amount paid from callback
                        amount_to_credit = Decimal(str(callback_amount)) if callback_amount else funding_transaction.amount
                        primary_wallet.balance += amount_to_credit
                        primary_wallet.save()
                        
                        # Log the wallet update in transaction payment_details
                        funding_transaction.payment_details.update({
                            'wallet_update': {
                                'primary_wallet_id': primary_wallet.id,
                                'primary_wallet_number': primary_wallet.wallet_number,
                                'old_balance': str(old_balance),
                                'new_balance': str(primary_wallet.balance),
                                'amount_credited': str(amount_to_credit),
                                'updated_at': timezone.now().isoformat()
                            }
                        })
                        
                        logger.info(f"Primary wallet {primary_wallet.id} balance updated from {old_balance} to {primary_wallet.balance} for transaction {funding_transaction.transaction_id}")
                        
                    except Wallet.DoesNotExist:
                        logger.error(f"No primary wallet found for company {company.id}. Transaction {funding_transaction.transaction_id} completed but balance not updated.")
                        funding_transaction.payment_details.update({
                            'wallet_error': 'No primary wallet found for company',
                            'company_id': company.id
                        })
                        
                    except Wallet.MultipleObjectsReturned:
                        logger.error(f"Multiple primary wallets found for company {company.id}. Transaction {funding_transaction.transaction_id} completed but balance not updated.")
                        funding_transaction.payment_details.update({
                            'wallet_error': 'Multiple primary wallets found for company',
                            'company_id': company.id
                        })
                    
                    funding_transaction.save()
                    logger.info(f"Wallet funding transaction {funding_transaction.transaction_id} updated with payment completion")

            else:  # Payment Failed
                mpesa_transaction.status = 'FAILED'
                mpesa_transaction.result_code = result_code
                mpesa_transaction.result_desc = result_desc
                mpesa_transaction.callback_data = callback_data
                mpesa_transaction.transaction_date = timezone.now()
                mpesa_transaction.save()
                
                logger.warning(f"Wallet funding STK Push failed: {result_desc}")

                # Update wallet funding Transaction record if found
                if funding_transaction:
                    funding_transaction.status = "FAILED"
                    funding_transaction.failure_reason = result_desc
                    funding_transaction.completed_at = timezone.now()
                    
                    # Update payment_details with failure info
                    current_payment_details = funding_transaction.payment_details or {}
                    current_payment_details.update({
                        'callback_data': callback_data,
                        'failure_reason': result_desc,
                        'failure_code': result_code,
                        'failure_date': timezone.now().isoformat(),
                        'payment_status': 'FAILED'
                    })
                    funding_transaction.payment_details = current_payment_details
                    funding_transaction.save()
                    
                    logger.warning(f"Wallet funding transaction {funding_transaction.transaction_id} updated with payment failure")

        # Log summary for monitoring
        status_summary = {
            'checkout_request_id': checkout_request_id,
            'result_code': result_code,
            'status': 'SUCCESS' if result_code == 0 else 'FAILED',
            'mpesa_transaction_updated': True,
            'funding_transaction_updated': funding_transaction is not None,
            'transaction_type': 'wallet_funding'
        }
        
        if result_code == 0:
            status_summary['mpesa_receipt'] = mpesa_transaction.mpesa_receipt_number
            status_summary['amount'] = str(mpesa_transaction.amount)
            if funding_transaction:
                status_summary['funding_transaction_id'] = funding_transaction.transaction_id
                if funding_transaction.payment_details and 'wallet_update' in funding_transaction.payment_details:
                    status_summary['primary_wallet_updated'] = True
                    status_summary['primary_wallet_id'] = funding_transaction.payment_details['wallet_update']['primary_wallet_id']
        
        logger.info(f"Wallet funding STK Push callback processing summary: {status_summary}")

        # Return success response to M-Pesa
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Callback processed successfully'
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON in wallet funding STK Push callback")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"Error processing wallet funding STK Push callback: {str(e)}", exc_info=True)
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})
@csrf_exempt 
@require_http_methods(["POST"])
def stk_push_timeout_callback(request):
    """
    STK Push timeout callback handler
    Handles timeout responses from M-Pesa STK Push requests
    """
    try:
        callback_data = json.loads(request.body)
        logger.info(f"STK Push timeout callback received: {callback_data}")
        
        # Extract timeout data
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        merchant_request_id = stk_callback.get('MerchantRequestID')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_desc = stk_callback.get('ResultDesc', 'Payment request timed out')

        # Find and update MpesaTransaction
        try:
            mpesa_transaction = MpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id,
                merchant_request_id=merchant_request_id
            )
            
            with transaction.atomic():
                mpesa_transaction.status = 'TIMEOUT'
                mpesa_transaction.result_code = 1
                mpesa_transaction.result_desc = result_desc
                mpesa_transaction.callback_data = callback_data
                mpesa_transaction.transaction_date = timezone.now()
                mpesa_transaction.save()

                # Update related Transaction record
                try:
                    transport_record = Transaction.objects.get(
                        mpesa_checkout_request_id=checkout_request_id,
                        merchant_request_id=merchant_request_id
                    )
                    transport_record.status = "timeout"
                    transport_record.failure_reason = result_desc
                    transport_record.completed_at = timezone.now()
                    transport_record.payment_completed = False
                    
                    # Update payment details with timeout info
                    payment_details = transport_record.payment_details or {}
                    payment_details.update({
                        'timeout_reason': result_desc,
                        'timeout_date': timezone.now().isoformat(),
                        'payment_status': 'TIMEOUT'
                    })
                    transport_record.payment_details = payment_details
                    transport_record.save()
                    
                    logger.warning(f"Transaction record {transport_record.transaction_id} updated with timeout")
                    
                except Transaction.DoesNotExist:
                    logger.info(f"No Transaction record found for timeout: {checkout_request_id}")

            logger.warning(f"STK Push timeout processed: {checkout_request_id}")
            
        except MpesaTransaction.DoesNotExist:
            logger.error(f"MpesaTransaction not found for timeout: {checkout_request_id}")

        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Timeout callback processed successfully'
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON in STK Push timeout callback")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"Error processing STK Push timeout: {str(e)}", exc_info=True)
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})

@csrf_exempt
@require_http_methods(["POST"])
def c2b_validation(request):
    """
    C2B Validation callback
    Validates incoming C2B payments before processing
    """
    try:
        validation_data = json.loads(request.body)
        logger.info(f"C2B Validation received: {validation_data}")
        
        # Extract validation data
        trans_type = validation_data.get('TransType')
        trans_id = validation_data.get('TransID')
        trans_time = validation_data.get('TransTime')
        trans_amount = validation_data.get('TransAmount')
        business_short_code = validation_data.get('BusinessShortCode')
        bill_ref_number = validation_data.get('BillRefNumber')
        invoice_number = validation_data.get('InvoiceNumber')
        org_account_balance = validation_data.get('OrgAccountBalance')
        third_party_trans_id = validation_data.get('ThirdPartyTransID')
        msisdn = validation_data.get('MSISDN')
        first_name = validation_data.get('FirstName')
        middle_name = validation_data.get('MiddleName')
        last_name = validation_data.get('LastName')
        
        # Add your validation logic here
        # For example, check if the account reference is valid
        # or if the amount meets minimum requirements
        
        # Example validation logic
        if not bill_ref_number or len(bill_ref_number) < 3:
            logger.warning(f"Invalid account reference: {bill_ref_number}")
            return JsonResponse({
                'ResultCode': 'C2B00012',
                'ResultDesc': 'Invalid Account Reference'
            })
        
        if trans_amount < 1:
            logger.warning(f"Amount too low: {trans_amount}")
            return JsonResponse({
                'ResultCode': 'C2B00011',
                'ResultDesc': 'Invalid Amount'
            })
        
        # If validation passes
        logger.info(f"C2B validation passed for transaction: {trans_id}")
        return JsonResponse({
            'ResultCode': '0',
            'ResultDesc': 'Accepted'
        })
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in C2B validation")
        return JsonResponse({'ResultCode': 'C2B00013', 'ResultDesc': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"Error in C2B validation: {str(e)}")
        return JsonResponse({'ResultCode': 'C2B00014', 'ResultDesc': 'Internal server error'})



@csrf_exempt
@require_http_methods(["POST"])
def c2b_confirmation(request):
    """
    C2B Confirmation callback
    Processes confirmed C2B payments, creates MpesaTransaction,
    updates Wallet balance, and creates a core Transaction record.
    """
    try:
        confirmation_data = json.loads(request.body)
        logger.info(f"C2B Confirmation received: {confirmation_data}")
        
        # Extract confirmation data
        trans_type = confirmation_data.get('TransType')
        mpesa_trans_id = confirmation_data.get('TransID') # M-Pesa Transaction ID (e.g., receipt number)
        trans_time_str = confirmation_data.get('TransTime') # YYYYMMDDHHMMSS format
        trans_amount = Decimal(confirmation_data.get('TransAmount', '0.00')) # Ensure Decimal
        business_short_code = confirmation_data.get('BusinessShortCode') # Your Paybill/Till
        bill_ref_number = confirmation_data.get('BillRefNumber') # WALLET_XXX
        msisdn = confirmation_data.get('MSISDN')
        first_name = confirmation_data.get('FirstName', '')
        middle_name = confirmation_data.get('MiddleName', '')
        last_name = confirmation_data.get('LastName', '')

        # Parse TransTime
        try:
            transaction_datetime = timezone.datetime.strptime(trans_time_str, '%Y%m%d%H%M%S')
        except (ValueError, TypeError):
            logger.error(f"Invalid TransTime format or missing: {trans_time_str}. Using current time.")
            transaction_datetime = timezone.now()

        # --- 1. Find the target Wallet ---
        target_wallet = None
        if bill_ref_number and bill_ref_number.startswith('WALLET_'):
            try:
                wallet_id_str = bill_ref_number.split('_')[1]
                wallet_id = int(wallet_id_str)
                target_wallet = Wallet.objects.get(id=wallet_id)
            except (ValueError, IndexError):
                logger.warning(f"C2B Confirmation: Invalid wallet reference format: {bill_ref_number}. Transaction {mpesa_trans_id}.")
            except Wallet.DoesNotExist:
                logger.warning(f"C2B Confirmation: Wallet with ID {wallet_id_str} not found for BillRefNumber: {bill_ref_number}. Transaction {mpesa_trans_id}.")
        else:
            logger.warning(f"C2B Confirmation: BillRefNumber is not in WALLET_XXX format or missing: {bill_ref_number}. Cannot link to wallet for {mpesa_trans_id}.")

        # --- 2. Create or Update MpesaTransaction Record (Detailed M-Pesa Log) ---
        # Use mpesa_receipt_number (which is TransID from callback) for idempotency
        mpesa_txn_record, mpesa_txn_created = MpesaTransaction.objects.get_or_create(
            mpesa_receipt_number=mpesa_trans_id, 
            defaults={
                'transaction_type': 'C2B',
                'status': 'COMPLETED', 
                'transaction_id': mpesa_trans_id, # Store in general transaction_id field as well
                'amount': trans_amount,
                'party_a': msisdn,
                'party_b': business_short_code,
                'phone_number': msisdn,
                'account_reference': bill_ref_number,
                'transaction_desc': f"M-Pesa C2B Payment from {first_name} {last_name} to {bill_ref_number}",
                'transaction_date': transaction_datetime, 
                'created_at': transaction_datetime, 
                'completed_at': timezone.now(), 
                'callback_data': confirmation_data,
                'first_name': first_name, 
                'middle_name': middle_name,
                'last_name': last_name,
                # Link to CompanyKYC if wallet has one
                'company': target_wallet.company if target_wallet and hasattr(target_wallet, 'company') else None,
                # Link to User if wallet has one
                'user': target_wallet.user if target_wallet and hasattr(target_wallet, 'user') else None,
            }
        )
        
        if not mpesa_txn_created:
            # If transaction already exists, ensure its status is COMPLETED and update callback data
            if mpesa_txn_record.status != 'COMPLETED':
                mpesa_txn_record.status = 'COMPLETED'
                mpesa_txn_record.completed_at = timezone.now()
            mpesa_txn_record.callback_data = confirmation_data
            mpesa_txn_record.save()
            logger.info(f"C2B MpesaTransaction {mpesa_trans_id} already exists, status ensured to COMPLETED.")
        else:
            logger.info(f"New C2B MpesaTransaction {mpesa_trans_id} recorded.")

            # --- 3. Create a core Transaction Record (if not already created) ---
            # We want to create a Transaction record ONLY if this M-Pesa transaction is new to our system.
            # Use mpesa_trans_id as transaction_code for uniqueness if possible
            try:
                core_transaction = Transaction.objects.get(transaction_code=mpesa_trans_id)
                logger.info(f"Core Transaction with code {mpesa_trans_id} already exists. Skipping creation.")
            except Transaction.DoesNotExist:
                logger.info(f"Creating new core Transaction for {mpesa_trans_id}.")
                try:
                    core_transaction = Transaction.objects.create(
                        company=target_wallet.company if target_wallet else None,
                        user=target_wallet.user if target_wallet else None,
                        amount=trans_amount,
                        description=f"M-Pesa Deposit to Wallet {bill_ref_number}",
                        receiver_wallet=target_wallet,
                        sender_wallet=None, # External M-Pesa, no internal sender wallet
                        status='completed', # Directly completed
                        transaction_type='deposit', # Or 'received' as per your choices
                        transaction_code=mpesa_trans_id, # Link to M-Pesa ID
                        date=transaction_datetime, # Use the M-Pesa transaction time
                    )
                    logger.info(f"Core Transaction {core_transaction.transaction_id} created for M-Pesa {mpesa_trans_id}.")
                except Exception as e:
                    logger.error(f"Failed to create core Transaction record for {mpesa_trans_id}: {e}", exc_info=True)


            # --- 4. Fund the Wallet (if successfully created and linked) ---
            # This should happen only if the M-Pesa transaction record was new AND a wallet was found
            if target_wallet and mpesa_txn_created: # Only fund if this is a new, processed callback
                target_wallet.balance += trans_amount
                target_wallet.save()
                logger.info(f"Wallet {target_wallet.id} funded with KES {trans_amount} from transaction {mpesa_trans_id}.")
            elif not target_wallet:
                logger.warning(f"Wallet not found for {mpesa_trans_id}. Payment received but wallet balance not updated.")
            elif not mpesa_txn_created:
                 logger.info(f"Wallet for {mpesa_trans_id} not funded as MpesaTransaction already existed (handled by previous logic).")

            # --- Business Logic: Send Notifications (Example) ---
            # if target_wallet:
            #     # Consider sending notifications here or after the save
            #     # (e.g., via Celery task for async processing)
            #     pass
        
        return JsonResponse({
            'ResultCode': '0',
            'ResultDesc': 'Confirmation processed successfully'
        })
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in C2B confirmation", exc_info=True)
        return JsonResponse({'ResultCode': '1', 'ResultDesc': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing C2B confirmation: {str(e)}", exc_info=True)
        # Always return a failure code if your system had an internal error, Safaricom may retry
        return JsonResponse({'ResultCode': '1', 'ResultDesc': f"Internal server error: {str(e)}"}, status=500)


UUID_PATTERN = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}',
    re.IGNORECASE
)


@csrf_exempt
@require_http_methods(["POST"])
def b2c_result_callback(request):
    """
    Enhanced B2C Result callback handler with improved transaction linking
    """
    try:
        result_data = json.loads(request.body)
        logger.info(f"B2C Result callback received: {result_data}")
        
        result = result_data.get('Result', {})
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        originator_conversation_id = result.get('OriginatorConversationID')
        conversation_id = result.get('ConversationID')
        transaction_id = result.get('TransactionID')

        # Find the MpesaTransaction
        mpesa_transaction = None
        try:
            mpesa_transaction = MpesaTransaction.objects.get(
                originator_conversation_id=originator_conversation_id,
                conversation_id=conversation_id
            )
        except MpesaTransaction.DoesNotExist:
            logger.error(f"B2C MpesaTransaction not found for OriginatorConversationID: {originator_conversation_id} and ConversationID: {conversation_id}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'MpesaTransaction not found'})

        # Find the related Transaction record using conversation IDs
        transaction_record = None
        try:
            transaction_record = Transaction.objects.get(
                originator_conversation_id=originator_conversation_id,
                conversation_id=conversation_id
            )
            logger.debug(f"Transaction record found: {transaction_record}")
        except Transaction.DoesNotExist:
            logger.error(f"Transaction not found for conversations: {originator_conversation_id}, {conversation_id}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Transaction not found'})
        except Exception as e:
            logger.error(f"Error fetching transaction record: {e}", exc_info=True)
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Error fetching transaction'})

        with transaction.atomic():
            # Update MpesaTransaction status
            if result_code == 0:  # Success
                mpesa_transaction.status = 'COMPLETED'
                mpesa_transaction.transaction_id = transaction_id
                
                # Extract result parameters for B2C
                result_parameters = result.get('ResultParameters', {}).get('ResultParameter', [])
                amount_paid = None
                
                for param in result_parameters:
                    key = param.get('Key')
                    value = param.get('Value')
                    
                    if key == 'TransactionAmount':
                        amount_paid = Decimal(str(value))
                        mpesa_transaction.amount = amount_paid

                logger.info(f"B2C payment completed successfully for transaction ID: {transaction_id}")
                
                # Update Transaction record
                transaction_record.status = "completed"
                transaction_record.completed_at = timezone.now()
                transaction_record.payment_completed = True
                transaction_record.paid_at = timezone.now()
                transaction_record.save()
                logger.debug(f"Transaction record {transaction_record.pk} updated to completed.")

                # Update fee transaction using parent_transaction relationship
                try:
                    fee_transaction = TransactionFee.objects.get(
                        parent_transaction=transaction_record,
                        transaction_type="fee"
                    )
                    fee_transaction.status = "completed"
                    fee_transaction.completed_at = timezone.now()
                    fee_transaction.save()
                    logger.debug(f"Fee transaction {fee_transaction.pk} updated to completed.")
                except TransactionFee.DoesNotExist:
                    logger.info(f"No fee transaction found for parent transaction {transaction_record.pk}.")
                except Exception as e:
                    logger.error(f"Error updating fee transaction for {transaction_record.pk}: {e}", exc_info=True)

                # Deduct amount and fee from wallet
                if transaction_record.sender_wallet:
                    try:
                        wallet = Wallet.objects.select_for_update().get(pk=transaction_record.sender_wallet.pk)
                        total_deduction = transaction_record.amount + (transaction_record.transfer_fee or Decimal('0'))
                        
                        if wallet.balance >= total_deduction:
                            wallet.balance -= total_deduction
                            wallet.save()
                            logger.info(f"Wallet {wallet.pk} balance updated. New balance: {wallet.balance}")
                        else:
                            logger.error(f"Insufficient funds in wallet {wallet.pk} for transaction {transaction_record.pk}. Wallet balance: {wallet.balance}, Deduction needed: {total_deduction}")
                            transaction_record.status = "failed_insufficient_funds"
                            transaction_record.failure_reason = "Insufficient funds in wallet"
                            transaction_record.save()
                            mpesa_transaction.status = 'FAILED_INSUFFICIENT_FUNDS'
                            mpesa_transaction.result_desc = "Insufficient funds in wallet"
                    except Wallet.DoesNotExist:
                        logger.error(f"Sender wallet {transaction_record.sender_wallet.pk} not found for transaction {transaction_record.pk}.")
                    except Exception as e:
                        logger.error(f"Error updating wallet balance for transaction {transaction_record.pk}: {e}", exc_info=True)

                # Mark expense as paid using the direct foreign key relationship
                try:
                    if transaction_record.expense:
                        expense = transaction_record.expense
                        expense.paid = True
                        expense.paid_at = timezone.now()
                        expense.payment_completed = True
                        expense.save()
                        logger.info(f"Expense {expense.pk} marked as paid.")
                    else:
                        logger.warning(f"No expense linked to transaction {transaction_record.pk}")
                        
                except Exception as e:
                    logger.error(f"Unexpected error updating expense for transaction {transaction_record.pk}: {e}", exc_info=True)
                    transaction_record.failure_reason = f"Unexpected error updating expense: {e}"
                    transaction_record.status = "failed_expense_link"
                    transaction_record.save()

            else:
                # Payment failed 
                mpesa_transaction.status = 'FAILED'
                logger.warning(f"B2C payment failed for OriginatorConversationID: {originator_conversation_id}. Reason: {result_desc}")
                
                transaction_record.status = "failed"
                transaction_record.failure_reason = result_desc
                transaction_record.completed_at = timezone.now()
                transaction_record.save()
                logger.debug(f"Transaction record {transaction_record.pk} updated to failed.")

                # Update fee transaction
                try:
                    fee_transaction = TransactionFee.objects.get(
                        parent_transaction=transaction_record,
                        transaction_type="fee"
                    )
                    fee_transaction.status = "failed"
                    fee_transaction.failure_reason = result_desc
                    fee_transaction.completed_at = timezone.now()
                    fee_transaction.save()
                    logger.debug(f"Fee transaction {fee_transaction.pk} updated to failed.")
                except TransactionFee.DoesNotExist:
                    logger.info(f"No fee transaction found for failed parent transaction {transaction_record.pk}.")
                except Exception as e:
                    logger.error(f"Error updating fee transaction for failed transaction {transaction_record.pk}: {e}", exc_info=True)

                # Reset expense if payment failed using the direct foreign key relationship
                try:
                    if transaction_record.expense:
                        expense = transaction_record.expense
                        expense.payment_initiated = False
                        expense.payment_reference = None
                        expense.save()
                        logger.info(f"Expense {expense.pk} reset due to failed payment.")
                        
                except Exception as e:
                    logger.error(f"Error resetting expense for failed transaction {transaction_record.pk}: {e}", exc_info=True)

            # Update common fields for MpesaTransaction
            mpesa_transaction.result_code = result_code
            mpesa_transaction.result_desc = result_desc
            mpesa_transaction.callback_data = result_data
            mpesa_transaction.transaction_date = timezone.now()
            mpesa_transaction.save()

        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'B2C result processed successfully'
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON in B2C result callback request body.", exc_info=True)
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        logger.error(f"Critical error processing B2C result callback: {str(e)}", exc_info=True)
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def b2c_timeout_callback(request):
    """
    B2C Timeout callback handler
    Handles B2C payment timeouts
    """
    try:
        timeout_data = json.loads(request.body)
        logger.info(f"B2C Timeout callback received: {timeout_data}")
        
        result = timeout_data.get('Result', {})
        originator_conversation_id = result.get('OriginatorConversationID')
        conversation_id = result.get('ConversationID')
        
        # Find and update transaction
        try:
            transaction = MpesaTransaction.objects.get(
                originator_conversation_id=originator_conversation_id,
                conversation_id=conversation_id
            )
            transaction.status = 'TIMEOUT'
            transaction.result_desc = 'Transaction timed out'
            transaction.callback_data = timeout_data
            transaction.save()
            
            logger.warning(f"B2C transaction timed out: {originator_conversation_id}")
            
        except MpesaTransaction.DoesNotExist:
            logger.error(f"B2C Transaction not found for timeout: {originator_conversation_id}")
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Timeout processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error processing B2C timeout: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})


@csrf_exempt
@require_http_methods(["POST"])
def b2b_result_callback(request):
    """
    Enhanced B2B Result callback handler with improved transaction linking
    Handles responses from B2B payment requests and updates both MpesaTransaction and Transaction models
    """
    try:
        result_data = json.loads(request.body)
        logger.info(f"B2B Result callback received: {result_data}")
        
        result = result_data.get('Result', {})
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        originator_conversation_id = result.get('OriginatorConversationID')
        conversation_id = result.get('ConversationID')
        transaction_id = result.get('TransactionID')

        # Find the MpesaTransaction
        mpesa_transaction = None
        try:
            mpesa_transaction = MpesaTransaction.objects.get(
                originator_conversation_id=originator_conversation_id,
                conversation_id=conversation_id
            )
        except MpesaTransaction.DoesNotExist:
            logger.error(f"B2B MpesaTransaction not found for OriginatorConversationID: {originator_conversation_id} and ConversationID: {conversation_id}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'MpesaTransaction not found'})

        # Find the related Transaction record using conversation IDs
        transaction_record = None
        try:
            transaction_record = Transaction.objects.get(
                originator_conversation_id=originator_conversation_id,
                conversation_id=conversation_id
            )
            logger.debug(f"Transaction record found: {transaction_record}")
        except Transaction.DoesNotExist:
            logger.error(f"Transaction not found for conversations: {originator_conversation_id}, {conversation_id}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Transaction not found'})
        except Exception as e:
            logger.error(f"Error fetching transaction record: {e}", exc_info=True)
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Error fetching transaction'})

        with transaction.atomic():
            # Update MpesaTransaction status
            if result_code == 0:  # Success
                mpesa_transaction.status = 'COMPLETED'
                mpesa_transaction.transaction_id = transaction_id
                
                # Extract result parameters for B2B
                result_parameters = result.get('ResultParameters', {}).get('ResultParameter', [])
                amount_paid = None
                
                for param in result_parameters:
                    key = param.get('Key')
                    value = param.get('Value')
                    
                    if key == 'Amount':
                        try:
                            amount_paid = Decimal(str(float(value)))
                            mpesa_transaction.amount = amount_paid
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid amount value: {value}")
                    elif key == 'InitiatorAccountCurrentBalance':
                        # Store initiator balance if needed
                        pass
                    elif key == 'DebitAccountCurrentBalance':
                        # Store debit account balance if needed
                        pass
                    elif key == 'DebitPartyAffectedAccountBalance':
                        # Store affected balance if needed
                        pass
                    elif key == 'TransCompletedTime':
                        # Store completion time if needed
                        pass
                    elif key == 'DebitPartyCharges':
                        # Store charges if needed
                        pass
                    elif key == 'ReceiverPartyPublicName':
                        # Store receiver name if needed
                        pass

                logger.info(f"B2B payment completed successfully for transaction ID: {transaction_id}")
                
                # Update Transaction record
                transaction_record.status = "completed"
                transaction_record.completed_at = timezone.now()
                transaction_record.payment_completed = True
                transaction_record.paid_at = timezone.now()
                transaction_record.save()
                logger.debug(f"Transaction record {transaction_record.pk} updated to completed.")

                # Update fee transaction using parent_transaction relationship
                try:
                    fee_transaction = TransactionFee.objects.get(
                        parent_transaction=transaction_record,
                        transaction_type="fee"
                    )
                    fee_transaction.status = "completed"
                    fee_transaction.completed_at = timezone.now()
                    fee_transaction.save()
                    logger.debug(f"Fee transaction {fee_transaction.pk} updated to completed.")
                except TransactionFee.DoesNotExist:
                    logger.info(f"No fee transaction found for parent transaction {transaction_record.pk}.")
                except Exception as e:
                    logger.error(f"Error updating fee transaction for {transaction_record.pk}: {e}", exc_info=True)

                # Deduct amount and fee from wallet
                if transaction_record.sender_wallet:
                    try:
                        wallet = Wallet.objects.select_for_update().get(pk=transaction_record.sender_wallet.pk)
                        total_deduction = transaction_record.amount + (transaction_record.transfer_fee or Decimal('0'))
                        
                        if wallet.balance >= total_deduction:
                            wallet.balance -= total_deduction
                            wallet.save()
                            logger.info(f"Wallet {wallet.pk} balance updated. New balance: {wallet.balance}")
                        else:
                            logger.error(f"Insufficient funds in wallet {wallet.pk} for transaction {transaction_record.pk}. Wallet balance: {wallet.balance}, Deduction needed: {total_deduction}")
                            transaction_record.status = "failed_insufficient_funds"
                            transaction_record.failure_reason = "Insufficient funds in wallet"
                            transaction_record.save()
                            mpesa_transaction.status = 'FAILED_INSUFFICIENT_FUNDS'
                            mpesa_transaction.result_desc = "Insufficient funds in wallet"
                    except Wallet.DoesNotExist:
                        logger.error(f"Sender wallet {transaction_record.sender_wallet.pk} not found for transaction {transaction_record.pk}.")
                    except Exception as e:
                        logger.error(f"Error updating wallet balance for transaction {transaction_record.pk}: {e}", exc_info=True)

                # Mark expense as paid using the direct foreign key relationship
                try:
                    if transaction_record.expense:
                        expense = transaction_record.expense
                        expense.paid = True
                        expense.paid_at = timezone.now()
                        expense.payment_completed = True
                        expense.save()
                        logger.info(f"Expense {expense.pk} marked as paid.")
                    else:
                        logger.warning(f"No expense linked to transaction {transaction_record.pk}")
                        
                except Exception as e:
                    logger.error(f"Unexpected error updating expense for transaction {transaction_record.pk}: {e}", exc_info=True)
                    transaction_record.failure_reason = f"Unexpected error updating expense: {e}"
                    transaction_record.status = "failed_expense_link"
                    transaction_record.save()

            else:
                # Payment failed
                mpesa_transaction.status = 'FAILED'
                logger.warning(f"B2B payment failed for OriginatorConversationID: {originator_conversation_id}. Reason: {result_desc}")
                
                transaction_record.status = "failed"
                transaction_record.failure_reason = result_desc
                transaction_record.completed_at = timezone.now()
                transaction_record.save()
                logger.debug(f"Transaction record {transaction_record.pk} updated to failed.")

                # Update fee transaction
                try:
                    fee_transaction = TransactionFee.objects.get(
                        parent_transaction=transaction_record,
                        transaction_type="fee"
                    )
                    fee_transaction.status = "failed"
                    fee_transaction.failure_reason = result_desc
                    fee_transaction.completed_at = timezone.now()
                    fee_transaction.save()
                    logger.debug(f"Fee transaction {fee_transaction.pk} updated to failed.")
                except TransactionFee.DoesNotExist:
                    logger.info(f"No fee transaction found for failed parent transaction {transaction_record.pk}.")
                except Exception as e:
                    logger.error(f"Error updating fee transaction for failed transaction {transaction_record.pk}: {e}", exc_info=True)

                # Reset expense if payment failed using the direct foreign key relationship
                try:
                    if transaction_record.expense:
                        expense = transaction_record.expense
                        expense.payment_initiated = False
                        expense.payment_reference = None
                        expense.save()
                        logger.info(f"Expense {expense.pk} reset due to failed payment.")
                        
                except Exception as e:
                    logger.error(f"Error resetting expense for failed transaction {transaction_record.pk}: {e}", exc_info=True)

            # Update common fields for MpesaTransaction
            mpesa_transaction.result_code = result_code
            mpesa_transaction.result_desc = result_desc
            mpesa_transaction.callback_data = result_data
            mpesa_transaction.transaction_date = timezone.now()
            mpesa_transaction.save()

        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'B2B result processed successfully'
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON in B2B result callback request body.", exc_info=True)
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        logger.error(f"Critical error processing B2B result callback: {str(e)}", exc_info=True)
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'}, status=500)
@csrf_exempt
@require_http_methods(["POST"])
def b2b_timeout_callback(request):
    """
    B2B Timeout callback handler
    """
    try:
        timeout_data = json.loads(request.body)
        logger.info(f"B2B Timeout callback received: {timeout_data}")
        
        result = timeout_data.get('Result', {})
        originator_conversation_id = result.get('OriginatorConversationID')
        conversation_id = result.get('ConversationID')
        
        # Find and update transaction
        try:
            transaction = MpesaTransaction.objects.get(
                originator_conversation_id=originator_conversation_id,
                conversation_id=conversation_id
            )
            transaction.status = 'TIMEOUT'
            transaction.result_desc = 'Transaction timed out'
            transaction.callback_data = timeout_data
            transaction.save()
            
            logger.warning(f"B2B transaction timed out: {originator_conversation_id}")
            
        except MpesaTransaction.DoesNotExist:
            logger.error(f"B2B Transaction not found for timeout: {originator_conversation_id}")
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Timeout processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error processing B2B timeout: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})


@csrf_exempt
@require_http_methods(["POST"])
def transaction_status_result_callback(request):
    """
    Transaction Status Query result callback
    """
    try:
        result_data = json.loads(request.body)
        logger.info(f"Transaction Status result callback received: {result_data}")
        
        result = result_data.get('Result', {})
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        originator_conversation_id = result.get('OriginatorConversationID')
        conversation_id = result.get('ConversationID')
        
        # Process the status result
        if result_code == 0:
            # Extract result parameters for transaction details
            result_parameters = result.get('ResultParameters', {}).get('ResultParameter', [])
            transaction_details = {}
            
            for param in result_parameters:
                key = param.get('Key')
                value = param.get('Value')
                transaction_details[key] = value
            
            logger.info(f"Transaction status retrieved successfully: {transaction_details}")
        else:
            logger.warning(f"Transaction status query failed: {result_desc}")
        
        # You can store this information or use it for business logic
        # For example, update a separate TransactionStatusQuery model
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Status result processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error processing transaction status result: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})


@csrf_exempt
@require_http_methods(["POST"])
def transaction_status_timeout_callback(request):
    """
    Transaction Status Query timeout callback
    """
    try:
        timeout_data = json.loads(request.body)
        logger.info(f"Transaction Status timeout callback received: {timeout_data}")
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Status timeout processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error processing transaction status timeout: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})


@csrf_exempt
@require_http_methods(["POST"])
def account_balance_result_callback(request):
    """
    Account Balance Query result callback
    """
    try:
        result_data = json.loads(request.body)
        logger.info(f"Account Balance result callback received: {result_data}")
        
        result = result_data.get('Result', {})
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        
        if result_code == 0:
            # Extract balance information
            result_parameters = result.get('ResultParameters', {}).get('ResultParameter', [])
            balance_info = {}
            
            for param in result_parameters:
                key = param.get('Key')
                value = param.get('Value')
                balance_info[key] = value
            
            logger.info(f"Account balance retrieved successfully: {balance_info}")
            
            # You can store balance information in a separate model if needed
            # or use it for business logic
            
        else:
            logger.warning(f"Account balance query failed: {result_desc}")
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Balance result processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error processing account balance result: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})


@csrf_exempt
@require_http_methods(["POST"])
def account_balance_timeout_callback(request):
    """
    Account Balance Query timeout callback
    """
    try:
        timeout_data = json.loads(request.body)
        logger.info(f"Account Balance timeout callback received: {timeout_data}")
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Balance timeout processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error processing account balance timeout: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})


@csrf_exempt
@require_http_methods(["POST"])
def reversal_result_callback(request):
    """
    Transaction Reversal result callback
    """
    try:
        result_data = json.loads(request.body)
        logger.info(f"Reversal result callback received: {result_data}")
        
        result = result_data.get('Result', {})
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        originator_conversation_id = result.get('OriginatorConversationID')
        conversation_id = result.get('ConversationID')
        
        if result_code == 0:
            # Extract reversal result parameters
            result_parameters = result.get('ResultParameters', {}).get('ResultParameter', [])
            reversal_details = {}
            
            for param in result_parameters:
                key = param.get('Key')
                value = param.get('Value')
                reversal_details[key] = value
            
            logger.info(f"Transaction reversal completed successfully: {reversal_details}")
            
            # You might want to create a separate model for reversal tracking
            # or update the original transaction status
            
        else:
            logger.warning(f"Transaction reversal failed: {result_desc}")
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Reversal result processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error processing reversal result: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})


@csrf_exempt
@require_http_methods(["POST"])
def reversal_timeout_callback(request):
    """
    Transaction Reversal timeout callback
    """
    try:
        timeout_data = json.loads(request.body)
        logger.info(f"Reversal timeout callback received: {timeout_data}")
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Reversal timeout processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error processing reversal timeout: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal server error'})