from django.urls import path
from . import views


app_name="expense"

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('expense/submit/', views.submit_expense, name='submit_expense'),
    path('expense/create/event-operation', views.event_operation, name='event-operation'),
    # path('expense/<str:id>/', views.expense_detail, name='expense_detail'),
    # path('expense/<str:id>/<str:item_type>/', views.expense_detail, name='expense_detail'),
    path('expense/<str:id>/', views.expense_detail, name='expense_detail'),
    
    # For events
    path('expense/<str:id>/event/', views.expense_detail, {'item_type': 'event'}, name='event_expense_detail'),
    
    # For operations
    path('expense/<str:id>/operation/', views.expense_detail, {'item_type': 'operation'}, name='operation_expense_detail'),
    path('approvals/', views.expense_approvals, name='expense_approvals'),
    path('expense/<uuid:expense_id>/approve/', views.approve_expense, name='approve_expense'),
    path('expense/<uuid:expense_id>/decline/', views.decline_expense, name='decline_expense'),
    
    path('expense/<str:expense_id>/approve/', views.approve_expense, name='approve_expense'),
    path('payment/make/', views.make_payment, name='make_payment'),
    path('ajax/expense-options/', views.get_expense_options, name='get_expense_options'),

    path('create-event/', views.create_event, name='create_event'),
    path('create-operation/', views.create_operation, name='create_operation'),
]