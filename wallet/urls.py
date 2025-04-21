from django.urls import path
from wallet import views

app_name = "wallet"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("wallet/", views.wallet, name="wallet"),
    path("pending-expense/", views.pending_expenses, name="pending_expenses"),
    path("kyc-reg/", views.kyc_registration, name="kyc-reg"),
]