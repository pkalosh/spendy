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
    path('edit-item/<str:id>/<str:item_type>/', views.edit_item, name='edit_item'),
    # For events
    path('expense/<str:id>/event/', views.expense_detail, {'item_type': 'event'}, name='event_expense_detail'),
    path('expense/<str:id>/activation/', views.expense_detail, {'item_type': 'activation'}, name='activation_expense_detail'),  
    # For operations
    path('expense/<str:id>/operation/', views.expense_detail, {'item_type': 'operation'}, name='operation_expense_detail'),
    path('approvals/', views.expense_approvals, name='expense_approvals'),
    path('expense/<uuid:expense_id>/approve/', views.approve_expenses, name='approve_expense'),
    path('expense/<uuid:expense_id>/csv-preview/', views.preview_expense_csv, name='preview_expense_csv'),
    path('expense/<uuid:expense_id>/decline/', views.decline_expense, name='decline_expense'),
    path('expense/<uuid:expense_id>/undo/', views.undo_expense_action, name='undo_expense'),
    
    path('expense/<str:expense_id>/approve/', views.approve_expense, name='approve_expense'),
    path('payment/make/', views.make_payment, name='make_payment'),
    path('ajax/expense-options/', views.get_expense_options, name='get_expense_options'),

    path('create-event/', views.create_event, name='create_event'),
    path('create-operation/', views.create_operation, name='create_operation'),

    path('reports/', views.reports, name='reports'),
    path('analytics/data/', views.analytics_data, name='analytics_data'),
    path('download-batch-template/', views.download_batch_template, name='download_batch_template'),
    # path('csv-preview/', views.preview_expense_csv, name='preview_expense_csv'),

    # Inventory
    path("inventory/", views.inventory_list, name="list-items"),
    path("create/", views.inventory_create, name="create-item"),
    path("<int:pk>/edit/", views.inventory_edit, name="edit-item"),
    path("<int:pk>/delete/", views.inventory_delete, name="delete-item"),
    path("<int:pk>/checkout/", views.inventory_check_out, name="check-out"),
    path("<int:pk>/checkin/", views.inventory_check_in, name="check-in"),

    # Suppliers
    path("suppliers/", views.suppliers_list, name="suppliers"),
    path("suppliers/create/", views.supplier_create, name="supplier-create"),
    path("suppliers/<int:pk>/edit/", views.supplier_edit, name="supplier-edit"),
    path("suppliers/<int:pk>/delete/", views.supplier_delete, name="supplier-delete"),

    # Supplier invoices
    path("suppliers/<int:supplier_id>/invoices/", views.supplier_invoices, name="supplier_invoices"),
    path("suppliers/<int:supplier_id>/invoices/create/", views.supplier_invoice_create, name="invoice-create"),
    path("suppliers/<int:supplier_id>/invoices/<int:invoice_id>/edit/", views.supplier_invoice_edit, name="invoice-edit"),
    path("suppliers/<int:supplier_id>/invoices/<int:invoice_id>/delete/", views.supplier_invoice_delete, name="invoice-delete"),
    path("suppliers/<int:supplier_id>/invoices/<int:invoice_id>/items/create/", views.invoice_item_create, name="invoice-item-create"),
    path('suppliers/<int:supplier_id>/invoices/<int:invoice_id>/items/<int:item_id>/edit/', views.invoice_item_edit, name='invoice-item-edit'),
    path('suppliers/<int:supplier_id>/invoices/<int:invoice_id>/items/<int:item_id>/delete/', views.invoice_item_delete, name='invoice-item-delete'),
]