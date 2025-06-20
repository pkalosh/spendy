from django.db import models
from django.utils import timezone
# from wallet.models import Wallet, CompanyKYC
from django.conf import settings
import uuid

class ExpenseGroup(models.TextChoices):
    EVENT = 'event', 'Event'
    OPERATION = 'operation', 'Operation'

class CategoryBase(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey('wallet.CompanyKYC', on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(class)s_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
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

class ExpenseRequestType(CategoryBase):
    class Meta:
        verbose_name_plural = "Expense Request Types"
        ordering = ['name']


class Event(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(EventCategory, on_delete=models.CASCADE, related_name='events')
    company = models.ForeignKey('wallet.CompanyKYC', on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    project_lead = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='events',blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_events',blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"

class Operation(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(OperationCategory, on_delete=models.CASCADE, related_name='operations')
    company = models.ForeignKey('wallet.CompanyKYC', on_delete=models.SET_NULL, null=True, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='operations',blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    project_lead = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_operations',blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"

class Expense(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey('wallet.Wallet', on_delete=models.CASCADE, related_name='expenses',null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    request_type = models.ForeignKey(ExpenseRequestType, on_delete=models.SET_NULL, null=True, blank=True)
    expense_category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='expenses', null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True, related_name='expenses')
    operation = models.ForeignKey(Operation, on_delete=models.CASCADE, null=True, blank=True, related_name='expenses')
    company = models.ForeignKey('wallet.CompanyKYC', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)
    declined = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='approved_by', blank=True, null=True)
    decline_reason = models.TextField( null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)  # optional

    @property
    def related_item(self):
        if not self.request_type:
            return None
        
        if self.request_type.name.lower() == 'event':
            return self.event
        elif self.request_type.name.lower() == 'operation':
            return self.operation
        return None
    def __str__(self):
        return f"Expense: {self.amount} for {self.related_item or 'N/A'}"


    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
