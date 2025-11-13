from django.shortcuts import render, redirect
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from wallet.models import CompanyKYC, StaffProfile, Role
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.conf import settings
from django.db import IntegrityError,transaction
from userauths.models import User,ContactMessage
from userauths.forms import UserRegisterForm, ContactMessageForm,DemoForm
from django.core.mail import send_mail
import re
import logging

logger = logging.getLogger(__name__)

@transaction.atomic  # Ensures all-or-nothing: auto-rollback on any exception in try
def RegisterView(request):
    if request.user.is_authenticated:
        messages.warning(request, "You are already logged in.")
        return redirect("wallet:wallet")
    if request.method == "POST":
        print(request.POST)  # Keep for debugging
        logger.info(f"Registration attempt: {request.POST}")  # Better logging
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        company_name = request.POST.get('company', '').strip()
        country = request.POST.get('country', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('confirmPassword', '').strip()
        
        # Improved phone normalization: For Kenya, convert local 07xx to +2547xx
        phone_digits = re.sub(r'[^\d+]', '', phone_number)
        if country.lower() == 'kenya':
            if phone_digits.startswith('0') and len(phone_digits) == 10 and phone_digits[1] in '56789':
                # Local Kenyan mobile: 07xx... -> +2547xx...
                phone_digits = '254' + phone_digits[1:]
            elif phone_digits.startswith('254') and len(phone_digits) == 12:
                pass  # Already international
            else:
                phone_digits = '254' + phone_digits.lstrip('0')  # Fallback, strip leading 0
            phone_number = f'+{phone_digits}'
        elif phone_digits.startswith('254'):  # Keep if mistakenly entered
            phone_number = f'+{phone_digits}'
        elif len(phone_digits) > 3 and not phone_digits.startswith('+'):
            phone_number = f'+{phone_digits}'
        
        # Full validation
        errors = []
        required_fields = [first_name, last_name, email, phone_number, company_name, country, password, password_confirm]
        if not all(required_fields):
            errors.append("All fields are required.")
        if password != password_confirm:
            errors.append("Passwords do not match.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("Please enter a valid email address.")
        if not re.match(r'^\+\d{10,15}$', phone_number):
            errors.append("Please enter a valid phone number (e.g., +254723456789 for Kenya).")
        valid_countries = ['kenya', 'tanzania', 'uganda', 'rwanda', 'ethiopia', 'nigeria', 'ghana', 'south-africa']
        if country.lower() not in valid_countries:
            errors.append("Please select a valid country.")
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "users/sign-up.html")
        
        # Pre-check User duplicates
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, f"An account with email '{email}' already exists.")
            return render(request, "users/sign-up.html")
        if User.objects.filter(phone_number=phone_number).exists():
            messages.error(request, f"An account with phone '{phone_number}' already exists.")
            return render(request, "users/sign-up.html")
        
        try:
            # Create User
            new_user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                company_name=company_name,
                country=country.upper(),
                is_admin = True,
                is_verified = True
            )
            print(f"Created User ID: {new_user.id}")  # Debug: Track ID
            logger.info(f"User created: ID {new_user.id}, email {email}")

            # Get the CompanyKYC created by the post_save signal
            user_company = CompanyKYC.objects.get(user=new_user)

            # Update CompanyKYC with form data (signal sets defaults; override for registration)
            user_company.company_name = company_name
            user_company.country = country.title()  # Assuming CompanyKYC has a 'country' field
            user_company.mobile = phone_number  # Assuming CompanyKYC has a 'mobile' field
            user_company.organization_type = 'event_organization'
            user_company.status = 'pending'
            user_company.kyc_submitted = False
            user_company.kyc_confirmed = False
            user_company.save(update_fields=[
                'company_name', 'country', 'mobile', 'organization_type',
                'status', 'kyc_submitted', 'kyc_confirmed'
            ])  # Efficient: only update changed fields
            logger.info(f"CompanyKYC updated for user {new_user.id}")

            # Create StaffProfile (inner try for Role-specific error)
            try:
                admin_role = Role.objects.get(is_admin=True)
                StaffProfile.objects.create(
                    user=new_user,
                    role=admin_role,
                    company=user_company,
                    is_active=True,
                )
                # Set user as staff (for Django admin/custom perms) and save
                new_user.is_staff = True  # Enables staff status for admin access
                new_user.is_superuser = False  # Not full superuser, just staff admin
                new_user.save(update_fields=['is_staff', 'is_superuser'])
                logger.info(f"StaffProfile created for user {new_user.id} as admin")
            except Role.DoesNotExist:
                logger.error("Admin role not found during registration")
                raise ValueError("Admin role not found. Please contact administrator.")  # Re-raise to trigger transaction rollback

            # Authenticate and login (do this before email to ensure session is set)
            user = authenticate(request, email=email, password=password)
            if user:
                login(request, user)
            else:
                # Fallback login with new_user (rare, but ensures login)
                login(request, new_user)
            logger.info(f"User {new_user.id} authenticated and logged in")

            # Send welcome email (non-blocking; moved after login for better flow, but still in try)
            # Note: If email hangs, consider async (e.g., Celery) or console backend for dev
            try:
                message = f"""
Hi {first_name},
Welcome to Spendy! We're excited to help you take control of your event and operational expenses.
Ready to get started? Set up your first wallet in under 2 minutes: https://spendy.africa/sign-in/
With Spendy, you can:
- Create dedicated wallets for events and operations
- Manage and approve expenses in real time
- Track budgets and spending effortlessly
- Generate reports that keep your team informed
We built Spendy for event professionals like you who value transparency, teamwork, and smarter financial decisions.
Need help? Our support team is here for you at info@spendy.africa
Best regards,
The Spendy Team
                """.strip()
                send_mail(
                    subject='Welcome to Spendy — where event expense management gets simple',
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[new_user.email],
                    fail_silently=True,  # Prevents crash; log errors via logging
                )
                logger.info(f"Welcome email sent to {new_user.email}")
            except Exception as email_err:
                logger.error(f"Failed to send welcome email to {new_user.email}: {email_err}")
                # Don't rollback transaction for email failure

            messages.success(request, f"Hey {first_name}, your account was created successfully.")
            logger.info(f"Registration successful for user {new_user.id}; redirecting to wallet")
            return redirect("wallet:wallet")
            
        except ValueError as ve:  # For Role error
            logger.error(f"ValueError during registration: {ve}")
            messages.error(request, str(ve))
            return render(request, "users/sign-up.html")
        except IntegrityError as ie:
            error_str = str(ie)
            logger.error(f"IntegrityError during registration: {error_str}")
            if 'companykyc' in error_str.lower() and 'user_id' in error_str.lower():
                user_id_match = re.search(r"'(\d+)'", error_str)
                orphan_id = user_id_match.group(1) if user_id_match else "unknown"
                messages.error(request, f"Company setup conflict for ID {orphan_id}. Try again or contact support.")
            else:
                messages.error(request, f"Duplicate account detected: {error_str}")
            return render(request, "users/sign-up.html")
        except Exception as e:
            logger.error(f"Unexpected error during registration: {str(e)}", exc_info=True)
            messages.error(request, f"An error occurred during registration: {str(e)}")
            return render(request, "users/sign-up.html")
    # GET: Render template
    return render(request, "users/sign-up.html")
def LoginView(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        print(email, password)

        try:
            user = User.objects.get(email=email)
            user = authenticate(request, email=email, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, "Welcome Back!")

                # Now check roles
                if user.is_admin and hasattr(user, 'staffprofile') and user.staffprofile.role.is_admin:
                    return redirect("wallet:dashboard")
                elif user.is_staff or (hasattr(user, 'staffprofile') and user.staffprofile.role in ["staff", "org_staff"]):
                    return redirect("wallet:staff-dashboard")
                else:
                    messages.warning(request, "Unauthorized role.")
                    return redirect("userauths:sign-in")
            else:
                messages.warning(request, "Username or password does not exist")
                return redirect("userauths:sign-in")

        except User.DoesNotExist:
            messages.warning(request, "User does not exist")
            return redirect("userauths:sign-in")

    if request.user.is_authenticated:
        messages.warning(request, "You are already logged In")
        return redirect("wallet:dashboard")

    return render(request, "users/sign-in.html")

@login_required
def logoutView(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("userauths:home")


def reset_passwordView(request):

    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            if user:
                # Send password reset email
                user.send_password_reset_email()
                messages.success(request, "Password reset email sent successfully.")
                return redirect("userauths:sign-in")
        except User.DoesNotExist:
            messages.error(request, "No user found with the provided email.")
            return redirect("userauths:reset-password")

    return render(request, "users/resetpassword.html")

def password_reset_confirm(request, uidb64, token):
    """
    Handles the password reset confirmation via the emailed link.
    Validates the token and allows setting a new password.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_object_or_404(User, id=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == "POST":
            password = request.POST.get("password")
            password_confirm = request.POST.get("password_confirm")
            if password == password_confirm:
                if len(password) < 8:
                    messages.error(request, "Password must be at least 8 characters long.")
                else:
                    user.set_password(password)
                    user.save()
                    messages.success(request, "Password reset successfully. You can now sign in.")
                    login(request, user)  # Auto-login after reset (optional; remove if preferred)
                    return redirect("userauths:sign-in")
            else:
                messages.error(request, "Passwords do not match.")
        return render(request, "users/resetconfirm.html", {"uidb64": uidb64, "token": token})
    else:
        messages.error(request, "Invalid or expired reset link.")
        return redirect("userauths:sign-in")

@login_required
def change_passwordView(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep the user logged in
            messages.success(request, 'Your password was successfully updated!')
            return redirect('userauths:sign-in')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, "users/changepassword.html", {'form': form})


def homeView(request):
    contact_form = ContactMessageForm()
    demo_form = DemoForm()

    return render(request, "public/index.html",{'contact_form': contact_form, 'demo_form': demo_form})

def contact(request):
    if request.method == "POST":
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your message has been sent successfully.")
            return redirect("userauths:home")
        else:
            messages.error(request, "There was an error with your message. Please try again.")

    return render(request, "public/index.html",{})

def demo(request):
    if request.method == "POST":
        form = DemoForm(request.POST)
        if form.is_valid():
            demo_request = form.save(commit=False)
            demo_request.is_demo_request = True
            demo_request.save()
            messages.success(request, "Your demo request has been sent successfully.")
            return redirect("userauths:home")
        else:
            messages.error(request, "There was an error with your demo request. Please try again.")
    return render(request, "public/index.html",{})