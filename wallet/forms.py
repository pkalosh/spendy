from django import forms 
from wallet.models import CompanyKYC, StaffProfile,Role,Wallet
from django.forms import ImageField, FileInput, DateInput
from userauths.models import User
from decimal import Decimal

class WalletForm(forms.ModelForm):
    class Meta:
        model = Wallet
        fields = ['wallet_name', 'company', 'wallet_type', 'currency', 'balance']
        widgets = {
            'wallet_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Wallet Name'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'wallet_type': forms.Select(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'balance': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'min': '0'}),
        }
    
    def clean_balance(self):
        balance = self.cleaned_data.get('balance')
        if balance < Decimal('0'):
            raise forms.ValidationError("Balance cannot be negative")
        return balance
class DateInput(forms.DateInput):
    input_type = 'date'

class KYCForm(forms.ModelForm):

    class Meta:
        model = CompanyKYC
        fields = ['company_name','logo','kra_pin','registration_certificate','country','county','city','address','mobile','fax']


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'country','password']
        labels = {
            'email': 'Email Address',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'phone_number': 'Phone Number',
            'country': 'Country',
            'password': 'Password',
        }


class StaffProfileForm(forms.ModelForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=True,
        label='Role or Designation',
        empty_label="Select a role"
    )    
    class Meta:
        model = StaffProfile
        fields = ['profile_image', 'role', 'assigned_modules', 'is_active']
        labels = {
            'profile_image': 'Profile Image',
            'role': 'Role or Designation',
            'assigned_modules': 'Modules Assigned',
            'is_active': 'Active Status',
        }
        widgets = {
            'assigned_modules': forms.CheckboxSelectMultiple
        }




class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'description']
        labels = {
            'name': 'Role Name',
            'description': 'Role Description',
        }