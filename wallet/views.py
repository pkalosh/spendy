from django.shortcuts import render, redirect
from wallet.forms import KYCForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from wallet.models import Wallet, Notification, Transaction,CompanyKYC



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
                
            wallet = Wallet.objects.get(user=request.user)
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
        "account": wallet,
    }
    return render(request, "account/account.html", context)
@login_required
def kyc_registration(request):
    user = request.user
    wallet = Wallet.objects.get(user=user)

    try:
        kyc = CompanyKYC.objects.get(user=user)
    except:
        kyc = None
    
    if request.method == "POST":
        form = KYCForm(request.POST, request.FILES, instance=kyc)
        if form.is_valid():
            new_form = form.save(commit=False)
            new_form.user = user
            new_form.save()
            messages.success(request, "KYC Form submitted successfully, In review now.")
            return redirect("wallet:wallet")
    else:
        form = KYCForm(instance=kyc)
    context = {
        "account": wallet,
        "form": form,
        "kyc": kyc,
    }
    return render(request, "account/kyc-form.html", context)


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
                
        except CompanyKYC.DoesNotExist:
            messages.warning(request, "You need to submit your KYC")
            return redirect("wallet:kyc-reg")
        
        recent_transfer = Transaction.objects.filter(sender=request.user, transaction_type="transfer", status="completed").order_by("-id")[:1]
        recent_recieved_transfer = Transaction.objects.filter(reciever=request.user, transaction_type="transfer").order_by("-id")[:1]


        sender_transaction = Transaction.objects.filter(sender=request.user, transaction_type="transfer").order_by("-id")
        reciever_transaction = Transaction.objects.filter(reciever=request.user, transaction_type="transfer").order_by("-id")

        request_sender_transaction = Transaction.objects.filter(sender=request.user, transaction_type="request")
        request_reciever_transaction = Transaction.objects.filter(reciever=request.user, transaction_type="request")
        
        
        wallet = Wallet.objects.get(user=request.user)

    else:
        messages.warning(request, "You need to login to access the dashboard")
        return redirect("userauths:sign-in")

    context = {
        "kyc":kyc,
        "account":wallet,
        "form":form,
        "sender_transaction":sender_transaction,
        "reciever_transaction":reciever_transaction,

        'request_sender_transaction':request_sender_transaction,
        'request_reciever_transaction':request_reciever_transaction,
        'recent_transfer':recent_transfer,
        'recent_recieved_transfer':recent_recieved_transfer,
    }
    return render(request, "account/dashboard.html", context)
    