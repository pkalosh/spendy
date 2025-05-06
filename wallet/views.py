from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from wallet.forms import KYCForm, StaffProfileForm, UserForm,RoleForm,WalletForm
from expense.forms import ExpenseRequestForm ,ExpenseApprovalForm,EventExpenseForm,OperationExpenseForm
from django.contrib import messages
from wallet.models import Wallet, Notification, Transaction,CompanyKYC, StaffProfile,Role
from expense.models import ExpenseCategory, OperationCategory, EventCategory,Expense
from userauths.models import User
from django.core.paginator import Paginator
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_http_methods
from django.db.models import Q
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





@login_required
@user_passes_test(is_admin)
def create_wallet(request):
    if request.method == 'POST':
        wallet_form = WalletForm(request.POST)
        print(wallet_form)
        if wallet_form.is_valid():
            wallet = wallet_form.save(commit=False)
            wallet.user = request.user
            wallet.company = request.user.companykyc
            wallet.save()

            messages.success(request, f"Wallet '{wallet.wallet_name}' created successfully!")
            return redirect('wallet:dashboard')
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        wallet_form = WalletForm()

    return render(request, 'account/dashboard.html', {'wallet_form': wallet_form})


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
@require_http_methods(["GET", "POST"])
def expenses(request):
    context = {}
    user = request.user
    company = get_object_or_404(CompanyKYC, user=user)
    
    # Handle POST (create or actions)
    if request.method == "POST":
        action = request.POST.get("action")
        
        # CREATE EXPENSE
        if action == "create":
            # Important: Pass user and company to the form
            form = ExpenseRequestForm(request.POST, user=user, company=company)
            
            if form.is_valid():
                expense = form.save()
                messages.success(request, "Expense created successfully.")
                return redirect("wallet:expenses")
            else:
                # Store form with errors to display in template
                context["expense_form"] = form
                
                # Load all necessary data for the template
                expenses = Expense.objects.filter(company=company).order_by("-created_at")
                transactions = Transaction.objects.filter(company=company).order_by("-id")
                context["transactions"] = transactions
                context["pending_expenses"] = expenses.filter(approved=False, declined=False)
                context["approved_expenses"] = expenses.filter(approved=True, paid=False)
                context["declined_expenses"] = expenses.filter(declined=True)
                context["payment_form"] = PaymentForm(user=user, company=company)
                context["is_admin"] = True
                
                # Return render directly here to preserve form errors
                return render(request, "expenses/expense.html", context)
                
        # APPROVE EXPENSE
        elif action == "approve":
            expense_id = request.POST.get("expense_id")
            expense = get_object_or_404(Expense, id=expense_id, company=company)
            expense.approved = True
            expense.approved_by = request.user
            expense.save()
            messages.success(request, "Expense approved.")
            return redirect("wallet:expenses")
            
        # REJECT EXPENSE
        elif action == "reject":
            expense_id = request.POST.get("expense_id")
            reason = request.POST.get("reason")
            expense = get_object_or_404(Expense, id=expense_id, company=company)
            expense.approved = False
            expense.declined = True  # Added this to mark as declined
            expense.rejection_reason = reason
            expense.approved_by = request.user
            expense.save()
            messages.error(request, "Expense rejected.")
            return redirect("wallet:expenses")
            
        # MARK AS PAID
        elif action == "pay":
            expense_id = request.POST.get("expense_id")
            expense = get_object_or_404(Expense, id=expense_id, company=company)
            expense.paid = True  # Mark as paid
            expense.status = "completed"
            expense.save()
            messages.success(request, "Expense marked as paid.")
            return redirect("wallet:expenses")
    
    # GET - show all expenses related to the company
    expenses = Expense.objects.filter(company=company).order_by("-created_at")
    
    # Get transactions and wallets
    transactions = Transaction.objects.filter(company=company).order_by("-id")
    
    # Add to context
    context["transactions"] = transactions
    pending_expenses = expenses.filter(approved=False, declined=False)
    approved_expenses = expenses.filter(approved=True, paid=False)
    declined_expenses = expenses.filter(declined=True)
    
    # Initialize forms if not already in context (due to validation error)
    if "expense_form" not in context:
        context["expense_form"] = ExpenseRequestForm(user=user, company=company)
        
    context["payment_form"] = PaymentForm(user=user, company=company)
    context["pending_expenses"] = pending_expenses
    context["approved_expenses"] = approved_expenses
    context["declined_expenses"] = declined_expenses
    
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
    # First check if user is authenticated
    if request.user.is_authenticated:
        # Check if user is admin - only admins can access dashboard
        if not request.user.is_admin:
            messages.warning(request, "Only admin users can access the dashboard.")
            return redirect("wallet:staff-dashboard")  # Redirect non-admin users to wallet
            
        form = KYCForm()
        wallet_form = WalletForm()
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
            
        transactions = Transaction.objects.filter(company=kyc).order_by("-id")
        print(transactions)
        wallets = Wallet.objects.filter(company=kyc).order_by("-id").exclude(wallet_type="PRIMARY")
        primary_wallets = Wallet.objects.filter(company=kyc,wallet_type="PRIMARY").order_by("-id")
    else:
        messages.warning(request, "You need to login to access the dashboard")
        return redirect("userauths:sign-in")
        
    context = {
        "kyc": kyc,
        "wallets": wallets,
        "primary_wallets": primary_wallets,
        "form": form,
        "wallet_form": wallet_form,
        "transactions": transactions
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
        
        # Initialize forms
        # expense_form = ExpenseRequestForm(user=user, company=company.company)
        payment_form = PaymentForm(user=user, company=company.company)
        # event_form = EventExpenseForm(user=user, company=company.company)
        # operation_form = OperationExpenseForm(user=user, company=company.company)
        
        # Debug information - print to console
        print("============= FORM DEBUG INFO =============")
        # print(f"expense_form fields: {expense_form.fields.keys()}")
        # print(f"event_form fields: {event_form.fields.keys()}")
        # print(f"operation_form fields: {operation_form.fields.keys()}")
        
        events_queryset = Event.objects.filter(
            created_by=user,
            company=company.company, 
            approved=False,
            paid=False
        )
        print(f"Available events count: {events_queryset.count()}")
        print(f"Available events: {list(events_queryset.values_list('id', 'name'))}")
        
        operations_queryset = Operation.objects.filter(
            created_by=user,
            company=company.company, 
            approved=False,
            paid=False
        )
        
        # user1 = get_object_or_404(User, id=user.id)
        wallet = get_pending_approved_expense_sum(user)
        print(f"Available wallets count: {wallet}")
        print(f"Available operations count: {operations_queryset.count()}")
        print(f"Available operations: {list(operations_queryset.values_list('id', 'name'))}")
        
        context["pending_expenses"] = pending_expenses
        context["approved_expenses"] = approved_expenses
        context["declined_expenses"] = declined_expenses
        # context["expense_form"] = expense_form
        # context["payment_form"] = payment_form
        # context["event_form"] = event_form
        # context["operation_form"] = operation_form
        context["expense_groups"] = [{"name": "Event", "value": "EVENT"}, {"name": "Operation", "value": "OPERATION"}]
        context["wallet"] = wallet
        context["operations"] = Operation.objects.filter(company=company.company, created_by=request.user)
        context["events"] = Event.objects.filter(company=company.company, created_by=request.user)

        # # Add debug info to context
        # context["debug_expense_fields"] = list(expense_form.fields.keys())
        # context["debug_event_fields"] = list(event_form.fields.keys())
        # context["debug_operation_fields"] = list(operation_form.fields.keys())
        context["debug_events_count"] = events_queryset.count()
        context["debug_operations_count"] = operations_queryset.count()
        context['event_categories']  = EventCategory.objects.filter(
            Q(company=company.company)
        )
        context['operation_categories']  = OperationCategory.objects.filter(
            Q(company=company.company)
        )
        context['project_leads'] = StaffProfile.objects.filter(
            company=company.company,
            user__is_active=True
        ).select_related('user')
        return render(request, "users/staff/staff.html", context)
        
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