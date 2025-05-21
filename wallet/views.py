from itertools import chain
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from wallet.forms import KYCForm, StaffProfileForm, UserForm,RoleForm,WalletForm
from expense.forms import ExpenseRequestForm ,ExpenseApprovalForm,EventExpenseForm,OperationExpenseForm
from django.contrib import messages
from wallet.models import Wallet, Notification, Transaction,CompanyKYC, StaffProfile,Role
from expense.models import ExpenseCategory, OperationCategory, EventCategory,Expense,ExpenseRequestType
from userauths.models import User
from django.core.paginator import Paginator
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils.html import escape
def is_admin(user):
    return user.is_authenticated and user.is_admin

@login_required
def settings_view(request):
    """View for system settings page"""
    company = get_object_or_404(CompanyKYC,user=request.user)
 
    context = {
        'expense_categories': ExpenseCategory.objects.filter(company=company).order_by('name'),
        'operation_categories': OperationCategory.objects.filter(company=company).order_by('name'),
        'event_categories': EventCategory.objects.filter(company=company).order_by('name'),
    }
    return render(request, 'settings.html', context)

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
        category_type = request.GET.get('type')
        name = request.POST.get('name')
        
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
                
            category.name = name
            category.save()
            messages.success(request, f'{category_type.title()} category updated successfully')
            
        except (ExpenseCategory.DoesNotExist, OperationCategory.DoesNotExist, EventCategory.DoesNotExist):
            messages.error(request, 'Category not found')
            
    return redirect('wallet:settings_view')

@login_required
def delete_category(request):
    """Delete a category (expense, operation, or event)"""
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        category_type = request.GET.get('type')
        
        if not all([category_id, category_type]):
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
                
            category.delete()
            messages.success(request, f'{category_type.title()} category deleted successfully')
            
        except (ExpenseCategory.DoesNotExist, OperationCategory.DoesNotExist, EventCategory.DoesNotExist):
            messages.error(request, 'Category not found')
            
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
            
            user.set_password(random_password)
            # Assign appropriate user flags for staff
            user.is_staff = True
            user.company_name = company.company_name
            user.is_org_staff = True
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

        if wallet_name:
            wallet = Wallet(
                wallet_name=wallet_name,
                balance=balance,
                user=request.user,
                wallet_type=wallet_type,
                company=request.user.companykyc
            )
            wallet.save()

            messages.success(request, f"Wallet '{wallet.wallet_name}' created successfully!")
            return redirect('wallet:dashboard')
        else:
            messages.error(request, "Wallet name is required.")
            return redirect('wallet:dashboard')

    return redirect('wallet:dashboard')

@login_required
@user_passes_test(is_admin)
def wallet_transfer(request):
    if request.method == 'POST':
        from_wallet_id = request.POST.get('from_wallet_id')
        to_wallet_id = request.POST.get('to_wallet_id')
        amount_str = request.POST.get('amount')

        if not all([from_wallet_id, to_wallet_id, amount_str]):
            messages.error(request, "All fields are required.")
            return redirect('wallet:dashboard')

        if from_wallet_id == to_wallet_id:
            messages.error(request, "Source and destination wallets must be different.")
            return redirect('wallet:dashboard')

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except:
            messages.error(request, "Amount must be a positive number.")
            return redirect('wallet:dashboard')

        # Fetch wallets by ID
        from_wallet = get_object_or_404(Wallet, id=from_wallet_id, company=request.user.companykyc)
        to_wallet = get_object_or_404(Wallet, id=to_wallet_id, company=request.user.companykyc)

        if from_wallet.balance < amount:
            messages.error(request, "Insufficient balance in the source wallet.")
            return redirect('wallet:dashboard')

        # Perform transfer
        from_wallet.balance -= amount
        to_wallet.balance += amount
        from_wallet.save()
        to_wallet.save()

        messages.success(
            request,
            f"Transferred KES {amount} from {from_wallet.wallet_name.title()} to {to_wallet.wallet_name.title()}."
        )
        return redirect('wallet:dashboard')
    
    messages.error(request, "Invalid request method.")
    return redirect('wallet:dashboard')




@login_required
@user_passes_test(is_admin)
def fund_wallet(request):
    if request.method == 'POST':
        business_id = request.POST.get('business_id')  # e.g. mobile number
        amount_str = request.POST.get('amount')
        wallet_id = request.POST.get('wallet_id')

        if not all([business_id, amount_str]):
            messages.error(request, "Mobile number and amount are required.")
            return redirect('wallet:dashboard')

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except:
            messages.error(request, "Amount must be a positive number.")
            return redirect('wallet:dashboard')

        # Fund the primary wallet
        wallet = get_object_or_404(Wallet, id = wallet_id, company=request.user.companykyc)
        # Simulate MPESA funding success
        wallet.balance += amount
        wallet.save()

        messages.success(request, f"Wallet funded with KES {amount} via mobile {business_id}.")
        return redirect('wallet:dashboard')
    else:
        messages.error(request, "Invalid request method.")
        return redirect('wallet:dashboard')



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
                
            wallets = Wallet.objects.filter(user=request.user)
            primary_wallet  = Wallet.objects.get(user=request.user,wallet_type = "PRIMARY")
            print(primary_wallet)
            recent_txns = Transaction.objects.filter(company= kyc)
            print(recent_txns)
            if not kyc.kyc_confirmed:
                messages.warning(request, "Your KYC is Under Review.")
                return redirect("wallet:kyc-reg")
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
        "primary_wallet":primary_wallet,
        "transactions": recent_txns,
    }
    return render(request, "account/account.html", context)
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
    user = request.user
    txn = Transaction.objects.filter(company= get_object_or_404(CompanyKYC, user=request.user))

    context = {
        "transactions": txn,
    }
    return render(request, "transaction/approvals.html", context)



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
    transactions = Transaction.objects.filter(company=kyc).order_by("-id")
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
        "wallets": wallets,
        "primary_wallets": primary_wallets,
        "form": form,
        "wallet_form": wallet_form,
        "transactions": transactions,
    }

    return render(request, "account/dashboard.html", context)

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
        
        # Set up expense request form
        expense_form = ExpenseRequestForm(company=company.company)
        
        # Add to context
        context["pending_expenses"] = pending_expenses
        context["declined_expenses"] = declined_expenses
        context["expense_form"] = expense_form
        
        # Get request types and categories
        context['request_type'] = ExpenseRequestType.objects.filter(Q(company=company.company))
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

from decimal import Decimal
from django.db.models import Sum
from .models import Expense

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

