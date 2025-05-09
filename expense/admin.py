from django.contrib import admin
from .models import Expense, ExpenseCategory, CategoryBase, Event, Operation, EventCategory, OperationCategory,ExpenseRequestType


admin.site.register(Expense)
admin.site.register(ExpenseCategory)
admin.site.register(Event)
admin.site.register(Operation)
admin.site.register(EventCategory)
admin.site.register(OperationCategory)
admin.site.register(ExpenseRequestType)
