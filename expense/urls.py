from django.urls import path
from . import views


app_name="expense"

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('expense/submit/', views.submit_expense, name='submit_expense'),
    path('expense/<int:expense_id>/', views.expense_detail, name='expense_detail'),
    path('expense/<int:expense_id>/approve/', views.approve_expense, name='approve_expense'),
    path('payment/make/', views.make_payment, name='make_payment'),
    path('ajax/expense-options/', views.get_expense_options, name='get_expense_options'),
]