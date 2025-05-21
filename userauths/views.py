from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm

from userauths.models import User
from userauths.forms import UserRegisterForm

def RegisterView(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # form.save()
            new_user = form.save() # new_user.email
            username = form.cleaned_data.get("email")
            # username = request.POST.get("username")
            messages.success(request, f"Hey {username}, your account was created successfully.")
            # new_user = authenticate(username=form.cleaned_data.get('email'))
            new_user = authenticate(email=form.cleaned_data['email'],
                                    password=form.cleaned_data['password1'])
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
