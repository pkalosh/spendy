from django.urls import path
from wallet import views

app_name = "wallet"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("wallets/", views.wallet, name="wallet"),
    path("pending-expense/", views.pending_expenses, name="pending_expenses"),
    path("kyc-reg/", views.kyc_registration, name="kyc-reg"),
    path("expenses/", views.expenses, name="expenses"),
    path("expenses/create/", views.create_expenses, name="create-expenses"),

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

]


