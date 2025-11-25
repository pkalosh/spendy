from django.contrib import admin
from .models import Expense,InventoryItem, InventoryTransaction,InvoiceItem,SupplierInvoice,Supplier, BatchPayments,ExpenseCategory,Activation,ActivationCategory, CategoryBase, Event, Operation, EventCategory, OperationCategory,ExpenseRequestType


admin.site.register(Expense)
admin.site.register(ExpenseCategory)
admin.site.register(Event)
admin.site.register(Operation)
admin.site.register(EventCategory)
admin.site.register(OperationCategory)
admin.site.register(ExpenseRequestType)
admin.site.register(Activation)
admin.site.register(ActivationCategory)
admin.site.register(BatchPayments)
admin.site.register(InventoryItem)
admin.site.register(InventoryTransaction)
admin.site.register(InvoiceItem)
admin.site.register(SupplierInvoice)
admin.site.register(Supplier)