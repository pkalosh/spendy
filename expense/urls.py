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

    path('create-event/', views.create_event, name='create_event'),
    path('create-operation/', views.create_operation, name='create_operation'),
    path('create-event-ajax/', views.create_event_ajax, name='create_event_ajax'),
    path('create-operation-ajax/', views.create_operation_ajax, name='create_operation_ajax'),

    path('create_event/', views.create_event, name='create_event'),
    path('create_operation/', views.create_operation, name='create_operation'),
]