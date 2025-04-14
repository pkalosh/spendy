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
class TransactionError(Exception):
    pass

class InsufficientFunds(TransactionError):
    pass

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
        return f"{self.user.first_name}-{self.user.first_name}-{self.user.phone_number}'s {self.currency} wallet:Balance--:{self.balance}"

    def validate_sufficient_funds(self, amount):
        if self.balance < amount:
            raise InsufficientFunds(f"Insufficient funds. Current balance: {self.balance} {self.currency}")

    def validate_transaction_amount(self, amount):
        if amount <= 0:
            raise ValidationError("Transaction amount must be positive")
        if amount > Decimal('1000000'):  # Example maximum transaction limit
            raise ValidationError("Transaction amount exceeds maximum limit")

def user_directory_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = "%s_%s" % (instance.id, ext)
    return "user_{0}/{1}".format(instance.user.id, filename)


    
class CompanyKYC(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    user =  models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=1000)
    logo = models.ImageField(upload_to="kyc", default="default.jpg")
    kra_pin = models.ImageField(upload_to="kyc", null=True, blank=True)
    registration_certificate = models.ImageField(upload_to="kyc", null=True, blank=True)

    # Address
    country = models.CharField(max_length=100, null=True, blank=True)
    county = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)

    # Contact Detail
    mobile = models.CharField(max_length=100, null=True, blank=True)
    fax = models.CharField(max_length=100, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    kyc_submitted = models.BooleanField(default=False)
    kyc_confirmed = models.BooleanField(default=False)
    recommended_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True, related_name="recommended_by")
    review = models.CharField(max_length=100, null=True, blank=True, default="Review")
    
    def __str__(self):
        return f"{self.user}"    

    
    class Meta:
        ordering = ['-date']



def create_kyc(sender, instance, created, **kwargs):
    if created:
        CompanyKYC.objects.create(user=instance) #,company_name=instance.company_name)

def save_kyc(sender, instance,**kwargs):
    instance.companykyc.save()

post_save.connect(create_kyc, sender=User)
post_save.connect(save_kyc, sender=User)


@receiver(post_save, sender=User)
def create_account(sender, instance, created, **kwargs):
    if created:
        # Determine currency based on country
        currency = 'KES' if instance.country == 'KENYA' else "None"
        
        # Create wallet with the determined currency
        Wallet.objects.create(
            user=instance, 
            wallet_type = "PRIMARY",
            currency='KES'
        )
@receiver(post_save, sender=User)
def save_account(sender, instance, **kwargs):
    # Ensure wallet is saved
    if hasattr(instance, 'wallet'):
        instance.wallet.save()


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
   
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="user")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    description = models.CharField(max_length=1000, null=True, blank=True)
   
    reciever = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="reciever")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sender")
   
    reciever_wallet = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True, related_name="reciever_wallet")
    sender_wallet = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True, related_name="sender_wallet")

    status = models.CharField(choices=TRANSACTION_STATUS, max_length=100, default="pending")
    transaction_type = models.CharField(choices=TRANSACTION_TYPE, max_length=100, default="none")

    date = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=False, null=True, blank=True)

    def __str__(self):
        try:
            return f"{self.user}"
        except:
            return f"Transaction"



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