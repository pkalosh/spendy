from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.db.models.signals import post_save
from django.dispatch import receiver
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    COUNTRY_CURRENCY_MAP = {
        'KENYA': 'KES',
        'UGANDA': 'UGX',
    }


    username = None  # Disable username field
    phone_number = models.CharField(max_length=15, unique=True)
    country = models.CharField(max_length=15,blank=True, null=True)
    email = models.EmailField(unique=True)
    company_name = models.CharField(max_length=250,blank=True, null=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    is_staff = models.BooleanField(default=False)
    is_org_user = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_org_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'  # Use email as the username field
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone_number']  # Required fields for createsuperuser


    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def send_password_reset_email(self):
        """
        Generates a password reset token and sends an email with a reset link to the user.
        Assumes a URL pattern named 'password_reset_confirm' under app_name='userauths'.
        """
        # Generate the token and UID
        token = default_token_generator.make_token(self)
        uid = urlsafe_base64_encode(force_bytes(self.pk))
        
        # Build the reset URL (using app label 'userauths')
        reset_url = reverse('userauths:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        
        # Determine domain from ALLOWED_HOSTS (prefer production domain like 'spendy.africa', fallback to localhost:8000)
        from django.conf import settings
        allowed_hosts = settings.ALLOWED_HOSTS
        domain = 'localhost:8000'  # Default fallback
        for host in allowed_hosts:
            if 'spendy.africa' in host:  # Prioritize production (handles exact or wildcard)
                domain = host.replace('*', 'spendy')  # Strip wildcard if present
                break
            elif host == '127.0.0.1':
                domain = '127.0.0.1:8000'
                break
            elif host == 'localhost':
                domain = 'localhost:8000'
                break
        
        # Use HTTPS for production domains, HTTP for localhost
        protocol = 'https' if not domain.startswith('localhost') and not domain.startswith('127.0.0.1') else 'http'
        full_reset_url = f"{protocol}://{domain}{reset_url}"
        
        # Email configuration (adjusted to use full name since username is disabled)
        subject = 'Password Reset Request'
        full_name = f"{self.first_name} {self.last_name}".strip() or self.email
        message = f"""
        Hello {full_name},
        
        You requested a password reset. Click the link below to set a new password:
        {full_reset_url}
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        Your App Team
        """
        
        # Send the email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.email],
            fail_silently=False,
        )

class ContactMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    organization = models.CharField(max_length=250, blank=True, null=True)
    phone_number = models.CharField(max_length=50,  blank=True, null=True)
    subject = models.CharField(max_length=200, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_demo_request = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.name} - {self.subject}"