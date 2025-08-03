from django.urls import path
from wallet import views

app_name = "wallet"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),

    path("notifications/", views.notifications, name="notifications"),
    path("notifications/staff", views.staff_notifications, name="staff-notifications"),

    path('notifications/mark-read/', views.mark_alert_as_read, name='mark_alert_as_read'),
    path("wallets/", views.wallet, name="wallet"),
    path("wallet/create", views.create_wallet, name="create-wallet"),
    path("wallet/transfer", views.wallet_transfer, name="wallet-transfer"),
    path("wallet/fund", views.fund_wallet, name="fund-wallet"),
    path('wallet/edit/<int:wallet_id>/', views.edit_wallet, name='edit_wallet'),
    path('wallets/<int:wallet_id>/delete/', views.delete_wallet, name='delete_wallet'),
    path("staff-dashboard/", views.staff_dashboard, name="staff-dashboard"),
    path("kyc-reg/", views.kyc_registration, name="kyc-reg"),
    path("expenses/", views.expenses, name="expenses"),
    path("expenses/create/", views.create_expenses, name="create-expenses"),
    path("transactions/", views.transactions, name="transactions"),
    path("transactions/export/", views.transaction_export, name="transaction_export"),
    path('expense-requests/', views.expense_requests ,name='expense-requests'),

    path('roles/', views.list_roles ,name='staff-roles'),
    path('staff/', views.list_staff_profiles, name='staff-list'),
    path('staff/<int:pk>/', views.get_staff_profile, name='staff-detail'),
    path('staff/create/', views.create_staff_profile, name='staff-create'),
    path('staff/update/<int:pk>/', views.update_staff_profile, name='staff-update'),
    path('staff/delete/<int:pk>/', views.delete_staff_profile, name='staff-delete'),


    path('settings/', views.settings_view, name='settings_view'),
    path('settings/expense-category/add/', views.add_expense_category, name='add_expense_category'),
    path('settings/operation-category/add/', views.add_operation_category, name='add_operation_category'),
    path('settings/event-category/add/', views.add_event_category, name='add_event_category'),
    path('settings/category/edit/', views.edit_category, name='edit_category'),
    path('settings/category/delete/', views.delete_category, name='delete_category'),

    # New URLs for Clients and Brands
    path('add-client/', views.add_client, name='add_client'),
    path('edit-client/', views.edit_client, name='edit_client'),
    path('delete-client/', views.delete_client, name='delete_client'),
    path('add-brand/', views.add_brand, name='add_brand'),
    path('edit-brand/', views.edit_brand, name='edit_brand'),
    path('delete-brand/', views.delete_brand, name='delete_brand'),

    # STK Push callbacks
    path('stk/callback/', views.stk_push_callback, name='stk_push_callback'),
    path('stk/timeout/', views.stk_push_timeout_callback, name='stk_push_timeout_callback'),
    # C2B callbacks
    path('c2b/validation/', views.c2b_validation, name='c2b_validation'),
    path('c2b/confirmation/', views.c2b_confirmation, name='c2b_confirmation'),
    
    # B2C callbacks
    path('b2c/result/', views.b2c_result_callback, name='b2c_result'),
    path('b2c/timeout/', views.b2c_timeout_callback, name='b2c_timeout'),
    
    # B2B callbacks
    path('b2b/result/', views.b2b_result_callback, name='b2b_result'),
    path('b2b/timeout/', views.b2b_timeout_callback, name='b2b_timeout'),
    
    # Transaction Status Query callbacks
    path('status/result/', views.transaction_status_result_callback, name='transaction_status_result'),
    path('status/timeout/', views.transaction_status_timeout_callback, name='transaction_status_timeout'),
    
    # Account Balance Query callbacks
    path('balance/result/', views.account_balance_result_callback, name='account_balance_result'),
    path('balance/timeout/', views.account_balance_timeout_callback, name='account_balance_timeout'),
    
    # Transaction Reversal callbacks
    path('reversal/result/', views.reversal_result_callback, name='reversal_result'),
    path('reversal/timeout/', views.reversal_timeout_callback, name='reversal_timeout'),

]


