from django import forms 
from wallet.models import CompanyKYC
from django.forms import ImageField, FileInput, DateInput

class DateInput(forms.DateInput):
    input_type = 'date'

class KYCForm(forms.ModelForm):

    class Meta:
        model = CompanyKYC
        fields = ['company_name']
