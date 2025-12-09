from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid
from userauths.models import User
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
class ActivationCategory(CategoryBase):
    class Meta:
        verbose_name_plural = "Activation Categories"
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
    client = models.ForeignKey('wallet.Client', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey('wallet.CompanyKYC', on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    budget_file = models.FileField(upload_to='budget', blank=True, null=True)
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
    category = models.ForeignKey(OperationCategory, on_delete=models.CASCADE, related_name='operations',blank=True, null=True)
    client = models.ForeignKey('wallet.Client', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey('wallet.CompanyKYC', on_delete=models.SET_NULL, null=True, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    budget_file = models.FileField(upload_to='budget', blank=True, null=True)
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
        return f"{self.name}"

class Activation(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(ActivationCategory, on_delete=models.CASCADE, related_name='activations')
    client = models.ForeignKey('wallet.Client', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey('wallet.CompanyKYC', on_delete=models.SET_NULL, null=True, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    budget_file = models.FileField(upload_to='budget', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activation',blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    project_lead = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_activations',blank=True, null=True)

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
    activation = models.ForeignKey(Activation, on_delete=models.CASCADE, null=True, blank=True, related_name='expenses')
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
    batch_disbursement_type = models.BooleanField(default=False)  
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

class BatchPayments(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE)
    file = models.FileField(upload_to='batch_payments/')
    company = models.ForeignKey('wallet.CompanyKYC', on_delete=models.CASCADE)  
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_batch_payments', null=True, blank=True)

    def __str__(self):
        return f"Batch Payment for {self.expense}"

    class Meta:
        verbose_name_plural = "Batch Payments"

class AssetType(models.TextChoices):
    COMPANY = 'Company', 'Company'
    EVENT = 'Event', 'Event',
    OTHER = 'Other', 'Other'


class SupplierType(models.TextChoices):
    FLOWERS = 'Flowers', 'Flowers'
    FURNITURES = 'Furnitures', 'Furnitures'
    CARS = 'Cars', 'Cars'
    CLOTHES = 'Clothes', 'Clothes'
    JEWELRY = 'Jewelry', 'Jewelry'
    DECORATIONS = 'Decorations', 'Decorations'
    TABLE_CHARGES = 'Table Charges', 'Table Charges'
    OTHER = 'Other', 'Other'

class InventoryItem(models.Model):
    name = models.CharField(max_length=255)
    organization = models.ForeignKey('wallet.CompanyKYC', on_delete=models.CASCADE, related_name='inventory_items')
    asset_type = models.CharField(max_length=50, choices=AssetType.choices)
    description = models.TextField(blank=True, null=True)
    date_captured = models.DateField(auto_now_add=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2)
    lease_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    captured_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='captured_items')
    state = models.CharField(max_length=50, choices=[('Available', 'Available'), ('Checked Out', 'Checked Out')], default='Available')
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name

class InventoryTransaction(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=50, choices=[('Check Out', 'Check Out'), ('Check In', 'Check In')])
    transaction_date = models.DateTimeField(auto_now_add=True)
    checked_out_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    check_out_date = models.DateTimeField(null=True, blank=True)
    check_in_date = models.DateTimeField(null=True, blank=True)
    check_in_remarks = models.TextField(blank=True, null=True)
    check_in_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='check_in_transactions')
    check_out_remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item.name} transaction"

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    date_captured = models.DateField(auto_now_add=True)
    captured_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='suppliers')
    service_category = models.CharField(max_length=255, choices=SupplierType.choices, default=SupplierType.OTHER)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    organization = models.ForeignKey('wallet.CompanyKYC', on_delete=models.CASCADE, related_name='suppliers')
    email = models.EmailField(blank=True, null=True)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.name

class SupplierInvoice(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50)
    date_issued = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(blank=True, null=True)
    paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, choices=[('Bank Transfer', 'Bank Transfer'), ('Cash', 'Cash'), ('Cheque', 'Cheque')], default='Bank Transfer')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='supplier_invoices', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    remarks = models.TextField(blank=True, null=True)
    class Meta:
        verbose_name_plural = "Supplier Invoices"
        ordering = ['-date_issued']
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{self.supplier.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.supplier.name}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    state_of_item = models.CharField(max_length=255, blank=True, null=True)


    def __str__(self):
        return f"{self.quantity} x {self.name}"
    
    @property
    def total(self):
        return self.quantity * self.unit_price