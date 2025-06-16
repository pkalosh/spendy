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
from django.utils import timezone
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
    ('info', 'Info'),
    ('success', 'Success'),
    ('warning', 'Warning'),
    ('danger', 'Danger'),

)

class Transaction(models.Model):
    transaction_id = ShortUUIDField(unique=True, length=15, max_length=20, prefix="SPNDY")
    transaction_code = models.CharField(unique=True, max_length=50, null=True, blank=True)
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
    title = models.CharField(max_length=255,blank=True, null=True)
    message = models.TextField(blank=True, null=True)
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

            
class SMSLog(models.Model):
    """
    Log SMS messages for audit and debugging purposes
    """
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]
    
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default='general')
    message_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    cost = models.CharField(max_length=20, blank=True, null=True)
    sent_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Optional: Link to user if available
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    
    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['phone_number', '-sent_at']),
            models.Index(fields=['status', '-sent_at']),
            models.Index(fields=['notification_type', '-sent_at']),
        ]
    
    def __str__(self):
        return f"SMS to {self.phone_number} - {self.status}"



class MpesaTransaction(models.Model):
    """
    Comprehensive M-Pesa transaction model for all transaction types:
    STK Push, C2B, B2C, B2B, Transaction Status, Balance Query, Reversal
    """
    
    TRANSACTION_TYPES = [
        ('STK_PUSH', 'STK Push'),
        ('C2B', 'Customer to Business'),
        ('B2C', 'Business to Customer'),
        ('B2B', 'Business to Business'),
        ('TRANSACTION_STATUS', 'Transaction Status Query'),
        ('ACCOUNT_BALANCE', 'Account Balance Query'),
        ('REVERSAL', 'Transaction Reversal'),
    ]
    
    TRANSACTION_STATUS = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('TIMEOUT', 'Timeout'),
        ('REVERSED', 'Reversed'),
    ]
    
    COMMAND_IDS = [
        ('CustomerPayBillOnline', 'Customer Pay Bill Online'),
        ('CustomerBuyGoodsOnline', 'Customer Buy Goods Online'),
        ('BusinessPayment', 'Business Payment'),
        ('SalaryPayment', 'Salary Payment'),
        ('PromotionPayment', 'Promotion Payment'),
        ('BusinessPayBill', 'Business Pay Bill'),
        ('BusinessBuyGoods', 'Business Buy Goods'),
        ('TransactionStatusQuery', 'Transaction Status Query'),
        ('AccountBalance', 'Account Balance'),
        ('TransactionReversal', 'Transaction Reversal'),
    ]
    
    # Primary identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    status = models.CharField(max_length=15, choices=TRANSACTION_STATUS, default='PENDING')
    
    # M-Pesa transaction identifiers
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True, help_text="STK Push merchant request ID")
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True, help_text="STK Push checkout request ID")
    conversation_id = models.CharField(max_length=100, blank=True, null=True, help_text="M-Pesa conversation ID")
    originator_conversation_id = models.CharField(max_length=100, blank=True, null=True, help_text="Originator conversation ID")
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True, help_text="M-Pesa receipt number")
    transaction_id = models.CharField(max_length=50, blank=True, null=True, help_text="M-Pesa transaction ID")
    
    # Transaction details
    command_id = models.CharField(max_length=30, choices=COMMAND_IDS, blank=True, null=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    transaction_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True)
    
    # Party information
    party_a = models.CharField(max_length=15, blank=True, null=True, help_text="Sender party")
    party_b = models.CharField(max_length=15, blank=True, null=True, help_text="Receiver party")
    phone_number = models.CharField(max_length=15, blank=True, null=True, help_text="Customer phone number")
    
    # Transaction descriptions
    account_reference = models.CharField(max_length=100, blank=True, null=True, help_text="Account reference/Bill reference")
    transaction_desc = models.TextField(blank=True, null=True, help_text="Transaction description")
    remarks = models.TextField(blank=True, null=True, help_text="Transaction remarks")
    occasion = models.CharField(max_length=100, blank=True, null=True, help_text="Transaction occasion")
    
    # Callback response data (stored as JSON)
    callback_data = models.JSONField(blank=True, null=True, help_text="Complete callback response data")
    result_code = models.CharField(max_length=10, blank=True, null=True, help_text="Result code from callback")
    result_desc = models.TextField(blank=True, null=True, help_text="Result description from callback")
    
    # STK Push specific fields
    customer_message = models.TextField(blank=True, null=True, help_text="Message sent to customer")
    
    # Balance query specific fields
    account_balance = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    available_balance = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    reserved_balance = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    uncleared_balance = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    # Reversal specific fields
    original_transaction_id = models.CharField(max_length=50, blank=True, null=True, help_text="Original transaction ID for reversals")
    reversal_reason = models.TextField(blank=True, null=True, help_text="Reason for reversal")
    
    # User association (optional)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='mpesa_transactions')
    
    # API response details
    response_code = models.CharField(max_length=10, blank=True, null=True, help_text="API response code")
    response_description = models.TextField(blank=True, null=True, help_text="API response description")
    error_code = models.CharField(max_length=20, blank=True, null=True, help_text="Error code if transaction failed")
    error_message = models.TextField(blank=True, null=True, help_text="Error message if transaction failed")
    
    # Metadata
    ip_address = models.GenericIPAddressField(blank=True, null=True, help_text="Client IP address")
    user_agent = models.TextField(blank=True, null=True, help_text="Client user agent")
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # Additional tracking
    retry_count = models.PositiveIntegerField(default=0, help_text="Number of retry attempts")
    is_processed = models.BooleanField(default=False, help_text="Whether transaction has been processed by business logic")
    notes = models.TextField(blank=True, null=True, help_text="Internal notes")
    
    class Meta:
        db_table = 'mpesa_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_type', 'status']),
            models.Index(fields=['mpesa_receipt_number']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['conversation_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['account_reference']),
        ]
        verbose_name = 'M-Pesa Transaction'
        verbose_name_plural = 'M-Pesa Transactions'
    
    def __str__(self):
        if self.mpesa_receipt_number:
            return f"{self.transaction_type} - {self.mpesa_receipt_number} - KES {self.amount}"
        elif self.checkout_request_id:
            return f"{self.transaction_type} - {self.checkout_request_id} - KES {self.amount}"
        else:
            return f"{self.transaction_type} - {self.id} - KES {self.amount}"
    
    def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        if self.status == 'COMPLETED' and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)
    
    @property
    def is_successful(self):
        """Check if transaction was successful"""
        return self.status == 'COMPLETED' and self.result_code == '0'
    
    @property
    def is_pending(self):
        """Check if transaction is still pending"""
        return self.status == 'PENDING'
    
    @property
    def is_failed(self):
        """Check if transaction failed"""
        return self.status in ['FAILED', 'CANCELLED', 'TIMEOUT']
    
    @property
    def formatted_phone_number(self):
        """Return formatted phone number"""
        if self.phone_number:
            if self.phone_number.startswith('254'):
                return f"+{self.phone_number}"
            elif self.phone_number.startswith('0'):
                return f"+254{self.phone_number[1:]}"
        return self.phone_number
    
    @classmethod
    def get_by_checkout_request_id(cls, checkout_request_id):
        """Get transaction by checkout request ID"""
        try:
            return cls.objects.get(checkout_request_id=checkout_request_id)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_by_mpesa_receipt(cls, receipt_number):
        """Get transaction by M-Pesa receipt number"""
        try:
            return cls.objects.get(mpesa_receipt_number=receipt_number)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_user_transactions(cls, user, transaction_type=None):
        """Get all transactions for a user"""
        queryset = cls.objects.filter(user=user)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        return queryset
    
    @classmethod
    def get_successful_transactions(cls, start_date=None, end_date=None):
        """Get all successful transactions within date range"""
        queryset = cls.objects.filter(status='COMPLETED', result_code='0')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        return queryset
    
    def update_from_callback(self, callback_data):
        """Update transaction from M-Pesa callback data"""
        self.callback_data = callback_data
        
        # Extract common fields
        result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode') or \
                     callback_data.get('Result', {}).get('ResultCode')
        
        result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc') or \
                     callback_data.get('Result', {}).get('ResultDesc')
        
        if result_code is not None:
            self.result_code = str(result_code)
            self.result_desc = result_desc
            
            if result_code == 0:
                self.status = 'COMPLETED'
                self.completed_at = timezone.now()
                
                # Extract transaction details from callback metadata
                callback_metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', []) or \
                                  callback_data.get('Result', {}).get('ResultParameters', {}).get('ResultParameter', [])
                
                for item in callback_metadata:
                    name = item.get('Name', '')
                    value = item.get('Value')
                    
                    if name == 'MpesaReceiptNumber' and value:
                        self.mpesa_receipt_number = str(value)
                    elif name == 'TransactionDate' and value:
                        # Handle transaction date if needed
                        pass
                    elif name == 'PhoneNumber' and value:
                        self.phone_number = str(value)
                    elif name == 'Amount' and value:
                        self.amount = float(value)
            else:
                self.status = 'FAILED'
                
        self.save()

class MpesaCallbackLog(models.Model):
    """
    Log all M-Pesa callbacks for debugging and audit purposes
    """
    transaction = models.ForeignKey(MpesaTransaction, on_delete=models.CASCADE, blank=True, null=True, related_name='callback_logs')
    callback_type = models.CharField(max_length=50, help_text="Type of callback (STK, C2B, B2C, etc.)")
    raw_data = models.JSONField(help_text="Raw callback data")
    ip_address = models.GenericIPAddressField(help_text="Callback source IP")
    user_agent = models.TextField(blank=True, null=True)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'mpesa_callback_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['callback_type']),
            models.Index(fields=['processed']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.callback_type} - {self.created_at}"