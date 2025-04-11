from django.db import models
from django.conf import settings
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from shortuuid.django_fields import ShortUUIDField

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