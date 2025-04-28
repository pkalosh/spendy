from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from django.core.exceptions import ValidationError


class UserRegisterForm(UserCreationForm):
    COUNTRIES = [
        ('KENYA', 'Kenya'),
        ('UGANDA', 'Uganda'),
    ]
    phone_number = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Phone Number"}),
        max_length=15,
        help_text="Enter your phone number"
    )
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "First Name"}),
        max_length=50,
        required=True
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Last Name"}),
        max_length=50,
        required=True
    )
    company_name = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Company Name"}),
        max_length=50,
        required=True
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "Email"}),
        required=True
    )
    country = forms.ChoiceField(
        choices=COUNTRIES,
        widget=forms.Select(attrs={"placeholder": "Select Country"}),
        label="Country"
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password"}),
        help_text="Your password must be at least 8 characters long"
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm Password"}),
        help_text="Enter the same password as before, for verification"
    )

    class Meta:
        model = User
        fields = ['phone_number', 'first_name', 'last_name','company_name', 'email', 'country', 'password1', 'password2']

    def clean_country(self):
        country = self.cleaned_data.get('country')
        if country not in ['KENYA', 'UGANDA']:
            raise ValidationError("Invalid country selection")
        return country

   # def clean_phone_number(self):
       # phone_number = self.cleaned_data.get('phone_number')
      #  if User.objects.filter(phone_number=phone_number).exists():
     #       raise ValidationError("This phone number is already in use.")
    #    return phone_number

   # def clean_email(self):
   #     email = self.cleaned_data.get('email')
  #      if User.objects.filter(email=email).exists():
 #           raise ValidationError("This email is already in use.")
#        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_customer = True
        user.is_verified = True
        user.is_org_user = True
        user.is_admin = True
        user.phone_number = self.cleaned_data['phone_number']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.country = self.cleaned_data.get('country')
        user.company_name = self.cleaned_data.get('company_name')
        
        if commit:
            user.save()
        return user

