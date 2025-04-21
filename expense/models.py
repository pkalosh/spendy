from django.db import models
from django.utils import timezone
from wallet.models import Wallet
from django.conf import settings

class ExpenseGroup(models.TextChoices):
    EVENT = 'event', 'Event'
    OPERATION = 'operation', 'Operation'

class CategoryBase(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(class)s_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        
    def __str__(self):
        return self.name

class EventCategory(CategoryBase):
    class Meta:
        verbose_name_plural = "Event Categories"
        ordering = ['name']

class OperationCategory(CategoryBase):
    class Meta:
        verbose_name_plural = "Operation Categories"
        ordering = ['name']

class ExpenseCategory(CategoryBase):
    class Meta:
        verbose_name_plural = "Expense Categories"
        ordering = ['name']

class Event(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(EventCategory, on_delete=models.CASCADE, related_name='events')
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    project_lead = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='events')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"

class Operation(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(OperationCategory, on_delete=models.CASCADE, related_name='operations')
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='operations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"

class Expense(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_group = models.CharField(max_length=50, choices=ExpenseGroup.choices)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='expenses', null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True, related_name='expenses')
    operation = models.ForeignKey(Operation, on_delete=models.CASCADE, null=True, blank=True, related_name='expenses')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        related_item = self.event if self.expense_group == ExpenseGroup.EVENT else self.operation
        return f"{self.category.name if self.category else ''} expense: {self.amount} for {related_item if related_item else 'N/A'}"

    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.expense_group == ExpenseGroup.EVENT and not self.event:
            raise ValidationError("Event is required for event expenses")
        
        if self.expense_group == ExpenseGroup.OPERATION and not self.operation:
            raise ValidationError("Operation is required for operation expenses")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
