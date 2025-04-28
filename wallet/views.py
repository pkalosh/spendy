from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from wallet.forms import KYCForm, StaffProfileForm, UserForm,RoleForm
from django.contrib import messages
from wallet.models import Wallet, Notification, Transaction,CompanyKYC, StaffProfile,Role
from expense.models import ExpenseCategory, OperationCategory, EventCategory
from userauths.models import User
from django.core.paginator import Paginator
from userauths.forms import UserRegisterForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager
from django.contrib.auth.base_user import BaseUserManager
from django.http import HttpResponseRedirect
from django.urls import reverse
from expense.models import Expense
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

# def get_staff_profile(request, pk):
#     staff = get_object_or_404(StaffProfile, pk=pk)
#     return render(request, 'users/staff/detail.html', {'staff': staff})

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
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        profile_form = StaffProfileForm(request.POST, request.FILES)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save(commit=False)

            # Generate and set random password
            
            user.set_password(random_password)
            # Assign appropriate user flags for staff
            user.is_staff = True
            user.company_name = profile_form.cleaned_data['company']
            user.is_org_staff = True
            user.save()

            staff = profile_form.save(commit=False)
            staff.user = user
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


# @login_required
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
    wallet = Wallet.objects.get(user=user)

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

    txn = Expense.objects.filter(company = get_object_or_404(CompanyKYC, user= request.user))

    print(txn)

    context = {
        "transactions": txn,
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
    if request.user.is_authenticated:
        form = KYCForm()
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
            if not kyc.kyc_confirmed and not kyc.status == "approved":
                messages.warning(request, "Your KYC is Under Review.")
                return redirect("wallet:kyc-reg")
        except CompanyKYC.DoesNotExist:
            messages.warning(request, "You need to submit your KYC")
            return redirect("wallet:kyc-reg")
    

        sender_transaction = Transaction.objects.filter(sender=request.user).order_by("-id")
        
        wallets = Wallet.objects.filter(user=request.user)

    else:
        messages.warning(request, "You need to login to access the dashboard")
        return redirect("userauths:sign-in")

    context = {
        "kyc":kyc,
        "wallets":wallets,
        "form":form,
        "sender_transaction":sender_transaction
    }
    return render(request, "account/dashboard.html", context)
    

@login_required
def staff_dashboard(request):
    if request.user.is_authenticated:

        transactions = Transaction.objects.filter(sender=request.user).order_by("-id")
        print(request.user.staffprofile.company)
        wallets = Wallet.objects.filter(company = request.user.staffprofile.company)
        print(wallets)

    else:
        messages.warning(request, "You need to login to access the dashboard")
        return redirect("userauths:sign-in")

    context = {
        "wallets":wallets,
        "transactions":transactions
    }
    return render(request, "users/staff/staff.html", context)
    