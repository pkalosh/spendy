from django.db import models
from django.conf import settings
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
from shortuuid.django_fields import ShortUUIDField
from userauths.models import User
from django.core.validators import FileExtensionValidator
from expense.models import Expense
class TransactionError(Exception):
    pass

class InsufficientFunds(TransactionError):
    pass


def user_directory_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = "%s_%s" % (instance.id, ext)
    return "user_{0}/{1}".format(instance.user.id, filename)


    
class CompanyKYC(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    user =  models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=1000)
    logo = models.ImageField(upload_to="kyc", default="default.jpg",validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])])
    kra_pin = models.FileField(upload_to="kyc", null=True, blank=True,validators=[FileExtensionValidator(['pdf'])])
    registration_certificate = models.FileField(upload_to="kyc", null=True, blank=True,validators=[FileExtensionValidator(['pdf'])])

    # Address
    country = models.CharField(max_length=100, null=True, blank=True)
    county = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)

    # Contact Detail
    mobile = models.CharField(max_length=100, null=True, blank=True)
    fax = models.CharField(max_length=100, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='pending')

    kyc_submitted = models.BooleanField(default=False)
    kyc_confirmed = models.BooleanField(default=False)
    recommended_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True, related_name="recommended_by")
    review = models.CharField(max_length=100, null=True, blank=True, default="Review")
    
    def __str__(self):
        return f"{self.company_name} - {self.user.first_name} {self.user.last_name}"    

    
    class Meta:
        ordering = ['-date']


class Wallet(models.Model):
    CURRENCY_CHOICES = [
        ('KES', 'KES'),
        ('UGX', 'UGX'),
    ]
    WALLET_TYPES = [
        ('PRIMARY', 'PRIMARY'),
        ('EVENT', 'EVENT'),
        ('OPERATIONS', 'OPERATIONS'),
        ('EMERGENCY', 'EMERGENCY'),

    ]
    wallet_number = ShortUUIDField(length=7,blank=True, null=True, max_length=25, prefix="SPDY", alphabet="1234567890") #2175893745837
    wallet_name = models.CharField(blank=True, null=True, max_length=50) #2175893745837
    company = models.ForeignKey(CompanyKYC, on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    wallet_type = models.CharField(max_length=10, choices=WALLET_TYPES, default='PRIMARY')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                validators=[MinValueValidator(Decimal('0.00'))])
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'currency']),
        ]

    def __str__(self):
        company_name = self.company.company_name if self.company else "NoCompany"
        return f"{company_name}-{self.wallet_type} Wallet: {self.balance} {self.currency}"


    def validate_sufficient_funds(self, amount):
        if self.balance < amount:
            raise InsufficientFunds(f"Insufficient funds. Current balance: {self.balance} {self.currency}")

    def validate_transaction_amount(self, amount):
        if amount <= 0:
            raise ValidationError("Transaction amount must be positive")
        if amount > Decimal('1000000'):  # Example maximum transaction limit
            raise ValidationError("Transaction amount exceeds maximum limit")


TRANSACTION_TYPE = (
    ("transfer", "Transfer"),
    ("received", "Received"),
    ("deposit", "Deposit"),
    ("withdraw", "Withdraw"),
    ("refund", "Refund"),
    ("request", "Payment Request"),
    ("none", "None")
)

TRANSACTION_STATUS = (
    ("failed", "failed"),
    ("completed", "completed"),
    ("pending", "pending"),
    ("processing", "processing"),
    ("request_sent", "request_sent"),
    ("request_settled", "request settled"),
    ("request_processing", "request processing"),

)


NOTIFICATION_TYPE = (
    ("None", "None"),
    ("Transfer", "Transfer"),
    ("Sent Expense request", "Sent Expense request"),
    ("Approved Expense request", "Approved Expense request"),
    ("Sent Payment Request", "Sent Payment Request"),
    ("Received Payment Request", "Received Payment Request"),

)

class Transaction(models.Model):
    transaction_id = ShortUUIDField(unique=True, length=15, max_length=20, prefix="TRN")
    
    # Core fields
    company = models.ForeignKey('CompanyKYC', on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="user_transactions")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    description = models.CharField(max_length=1000, null=True, blank=True)
    
    # Transaction participants
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_transactions")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_transactions")
    receiver_wallet = models.ForeignKey('Wallet', on_delete=models.SET_NULL, null=True, blank=True, related_name="received_transactions")
    sender_wallet = models.ForeignKey('Wallet', on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_transactions")
    
    # Transaction state
    status = models.CharField(choices=TRANSACTION_STATUS, max_length=100, default="pending")
    transaction_type = models.CharField(choices=TRANSACTION_TYPE, max_length=100, default="none")
    
    # Related models for different transaction types
    expense = models.ForeignKey(Expense, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    # For admin wallet funding
    funded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="funding_transactions")
    
    # Timestamps
    date = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    def __str__(self):
        if self.transaction_type == "expense":
            return f"Expense Transaction: {self.transaction_id} - {self.amount}"
        elif self.transaction_type == "wallet_funding":
            return f"Wallet Funding: {self.transaction_id} - {self.amount}"
        elif self.transaction_type == "transfer":
            return f"Transfer: {self.transaction_id} - {self.amount}"
        else:
            return f"Transaction: {self.transaction_id} - {self.amount}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Validation for expense transactions
        if self.transaction_type == "expense" and not self.expense:
            raise ValidationError("Expense record is required for expense transactions")
        
        # Validation for transfers
        if self.transaction_type == "transfer" and (not self.sender_wallet or not self.receiver_wallet):
            raise ValidationError("Both sender and receiver wallets are required for transfers")
        
        # Validation for wallet funding
        if self.transaction_type == "wallet_funding" and not self.receiver_wallet:
            raise ValidationError("Receiver wallet is required for wallet funding")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notification_type = models.CharField(max_length=100, choices=NOTIFICATION_TYPE, default="none")
    amount = models.IntegerField(default=0)
    is_read = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    nid = ShortUUIDField(length=10, max_length=25, alphabet="abcdefghijklmnopqrstuvxyz")
    
    class Meta:
        ordering = ["-date"]
        verbose_name_plural = "Notification"

    def __str__(self):
        return f"{self.user} - {self.notification_type}"

class Module(models.Model):
    """Model to define different system modules/functions"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Role(models.Model):
    """Model to define staff roles with default module permissions"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_admin = models.BooleanField(default=False)
    default_modules = models.ManyToManyField(Module, null=True, blank=True)
    def __str__(self):
        return self.name

class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyKYC, on_delete=models.SET_NULL, null=True, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/',blank=True, null=True, default='default_profile_image.jpg')
    role = models.ForeignKey(Role, on_delete=models.PROTECT,blank=True, null=True)
    assigned_modules = models.ManyToManyField(Module, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"
    
    def has_module_access(self, module_code):
        """Check if staff has access to a specific module"""
        # Check if user has direct module assignment
        if self.assigned_modules.filter(code=module_code).exists():
            return True
        # Check if role has admin privileges
        if self.role.is_admin:
            return True
        # Check if module is in role's default modules
        if self.role.default_modules.filter(code=module_code).exists():
            return True
        return False