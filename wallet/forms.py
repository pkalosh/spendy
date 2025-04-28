from django import forms 
from wallet.models import CompanyKYC, StaffProfile,Role
from django.forms import ImageField, FileInput, DateInput
from userauths.models import User
class DateInput(forms.DateInput):
    input_type = 'date'

class KYCForm(forms.ModelForm):

    class Meta:
        model = CompanyKYC
        fields = ['company_name','logo','kra_pin','registration_certificate','country','county','city','address','mobile','fax']


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'country']
        labels = {
            'email': 'Email Address',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'phone_number': 'Phone Number',
            'country': 'Country',
        }


class StaffProfileForm(forms.ModelForm):
    class Meta:
        model = StaffProfile
        fields = ['company', 'profile_image', 'role', 'assigned_modules', 'is_active']
        labels = {
            'company': 'Company Name',
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