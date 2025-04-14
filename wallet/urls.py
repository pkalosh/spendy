from django.urls import path
from wallet import views

app_name = "wallet"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", views.wallet, name="wallet"),
    path("kyc-reg/", views.kyc_registration, name="kyc-reg"),
]