from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from wallet.models import CompanyKYC, StaffProfile, Role
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm

from userauths.models import User,ContactMessage
from userauths.forms import UserRegisterForm, ContactMessageForm,DemoForm

def RegisterView(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # Save the user
            new_user = form.save()
            username = form.cleaned_data.get("email")
            
            # Create StaffProfile with admin role
            try:
                # Get the admin role (adjust the filter based on your Role model)
                admin_role = Role.objects.get(is_admin=True)  # or Role.objects.get(name='Admin')
                
                # Get the user's company if it exists
                try:
                    user_company = CompanyKYC.objects.get(user=new_user)
                except CompanyKYC.DoesNotExist:
                    user_company = None
                
                # Create StaffProfile
                staff_profile = StaffProfile.objects.create(
                    user=new_user,
                    role=admin_role,
                    company=user_company,
                    is_active=True
                    # assigned_modules will be empty as intended
                )
                
            except Role.DoesNotExist:
                # Handle case where admin role doesn't exist
                messages.error(request, "Admin role not found. Please contact administrator.")
                # Optionally delete the created user if staff profile creation fails
                new_user.delete()
                return render(request, "users/sign-up.html", {"form": form})
            
            except Exception as e:
                # Handle any other errors during staff profile creation
                messages.error(request, f"Error creating staff profile: {str(e)}")
                new_user.delete()
                return render(request, "users/sign-up.html", {"form": form})
            
            messages.success(request, f"Hey {username}, your account was created successfully.")
            
            # Authenticate and login the user
            new_user = authenticate(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1']
            )
            login(request, new_user)
            return redirect("wallet:wallet")
    
    if request.user.is_authenticated:
        messages.warning(request, f"You are already logged in.")
        return redirect("wallet:wallet")
    else:
        form = UserRegisterForm()
        context = {
            "form": form
        }
        return render(request, "users/sign-up.html", context)



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