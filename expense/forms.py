from django import forms
from .models import Expense, Event, Operation, ExpenseRequestType, ExpenseCategory, EventCategory, OperationCategory, Activation, ActivationCategory
from wallet.models import Wallet
class EventExpenseForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'category','client', 'start_date','budget_file', 'end_date', 'budget', 'project_lead', 'location']
        # widgets = {
        #             'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        #             'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        #             'name': forms.TextInput(attrs={'class': 'form-control'}),
        #             'category': forms.Select(attrs={'class': 'form-control'}),
        #             'budget': forms.NumberInput(attrs={'class': 'form-control'}),
        #             'project_lead': forms.TextInput(attrs={'class': 'form-control'}),
        #             'location': forms.TextInput(attrs={'class': 'form-control'}),
        #         }
    def __init__(self, *args, **kwargs):
        super(EventExpenseForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class ActivationExpenseForm(forms.ModelForm):
    class Meta:
        model = Activation
        fields = ['name','category','client','budget','budget_file','description','project_lead']

    def __init__(self, *args, **kwargs):
        super(ActivationExpenseForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class OperationExpenseForm(forms.ModelForm):
    class Meta:
        model = Operation
        fields = ['name', 'category','client', 'budget','budget_file', 'project_lead']
        # widgets = {
        #             'name': forms.TextInput(attrs={'class': 'form-control'}),
        #             'category': forms.Select(attrs={'class': 'form-control'}),
        #             'budget': forms.NumberInput(attrs={'class': 'form-control'}),
        #             'project_lead': forms.Select(attrs={'class': 'form-control'}),
        #         }

    def __init__(self, *args, **kwargs):
        super(OperationExpenseForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class ExpenseRequestForm(forms.ModelForm):
    """Form for creating expense requests"""
    batch_file = forms.FileField(required=False, widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'batch_file', 'accept': '.csv'}))

    class Meta:
        model = Expense
        fields = ['request_type', 'wallet', 'expense_category', 'event', 'activation', 'batch_disbursement_type', 'operation', 'amount', 'description']
        widgets = {
            'request_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_request_type', 'data-nice-select': 'false'}),
            'expense_category': forms.Select(attrs={'class': 'form-control', 'id': 'id_expense_category'}),
            'event': forms.Select(attrs={'class': 'form-control'}),
            'operation': forms.Select(attrs={'class': 'form-control'}),
            'activation': forms.Select(attrs={'class': 'form-control'}),
            'batch_disbursement_type': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_batch_disbursement_type'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': '3', 'placeholder': 'Enter detailed reason for this expense'}),
        }
        
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        
        super().__init__(*args, **kwargs)
        
        # Initialize with empty querysets to avoid NoneType errors
        self.fields['event'].queryset = Event.objects.none()
        self.fields['operation'].queryset = Operation.objects.none()
        self.fields['activation'].queryset = Activation.objects.none()
        self.fields['wallet'].queryset = Wallet.objects.none()
        self.fields['request_type'].queryset = ExpenseRequestType.objects.none()
        self.fields['expense_category'].queryset = ExpenseCategory.objects.none()
        
        # Only filter if company is provided
        if self.company:
            self.fields['event'].queryset = Event.objects.filter(
                company=self.company, 
                approved=False,
                paid=False
            )
            self.fields['operation'].queryset = Operation.objects.filter(
                company=self.company, 
                approved=False,
                paid=False
            )
            self.fields['activation'].queryset = Activation.objects.filter(
                company=self.company, 
                approved=False,
                paid=False
            )
            self.fields['request_type'].queryset = ExpenseRequestType.objects.filter(
                company=self.company, 
                is_active=True
            )
            self.fields['expense_category'].queryset = ExpenseCategory.objects.filter(
                company=self.company, 
                is_active=True
            )
            self.fields['wallet'].queryset = Wallet.objects.filter(
                company=self.company, 
                is_active=True
            ).exclude(wallet_type="PRIMARY")
    
    def clean(self):
        cleaned_data = super().clean()
        request_type = cleaned_data.get('request_type')
        event = cleaned_data.get('event')
        operation = cleaned_data.get('operation')
        activation = cleaned_data.get('activation')
        batch_disbursement_type = cleaned_data.get('batch_disbursement_type')
        batch_file = self.files.get('batch_file')

        if request_type:
            request_type_name = request_type.name.lower()
            if 'event' in request_type_name and not event:
                self.add_error('event', 'This field is required for event requests.')
            elif 'operation' in request_type_name and not operation:
                self.add_error('operation', 'This field is required for operation requests.')
            elif 'activation' in request_type_name and not activation:
                self.add_error('activation', 'This field is required for activation requests.')

        if batch_disbursement_type and not batch_file:
            self.add_error('batch_file', 'A CSV file is required for batch disbursements.')
        elif batch_file:
            if not batch_file.name.endswith('.csv'):
                self.add_error('batch_file', 'File must be a CSV.')

        return cleaned_data
class ExpenseApprovalForm(forms.ModelForm):
    """Form for approving or declining expense requests"""
    
    APPROVAL_CHOICES = (
        ('approve', 'Approve'),
        ('decline', 'Decline'),
    )
    
    action = forms.ChoiceField(choices=APPROVAL_CHOICES, widget=forms.RadioSelect)
    
    class Meta:
        model = Expense
        fields = ['decline_reason']
        widgets = {
            'decline_reason': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter reason for declining'})
        }
        
    def __init__(self, *args, **kwargs):
        self.admin_user = kwargs.pop('admin_user', None)
        super(ExpenseApprovalForm, self).__init__(*args, **kwargs)
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        action = self.cleaned_data.get('action')
        
        if action == 'approve':
            instance.approved = True
            instance.declined = False
            instance.decline_reason = None
            instance.approved_by = self.admin_user
        else:
            instance.approved = False
            instance.declined = True
            instance.approved_by = None
            
        if commit:
            instance.save()
        return instance


class PaymentForm(forms.Form):
    """Form for making payments for approved expenses"""
    
    PAYMENT_METHODS = (
        ('mpesa_number', 'M-Pesa Number'),
        ('paybill', 'Paybill'),
        ('till_number', 'Till Number'),
    )
    
    expense = forms.ModelChoiceField(queryset=None)
    payment_method = forms.ChoiceField(choices=PAYMENT_METHODS)
    mpesa_number = forms.CharField(max_length=15, required=False)
    paybill_number = forms.CharField(max_length=15, required=False)
    account_number = forms.CharField(max_length=30, required=False)
    till_number = forms.CharField(max_length=15, required=False)
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.company = kwargs.pop('company', None)
        super(PaymentForm, self).__init__(*args, **kwargs)
        
        # Only show approved expenses that haven't been paid
        if self.company:
            self.fields['expense'].queryset = Expense.objects.filter(
                company=self.company, 
                approved=True, 
                declined=False
            )
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        
        # Validate based on payment method
        if payment_method == 'mpesa_number' and not cleaned_data.get('mpesa_number'):
            raise forms.ValidationError("M-Pesa number is required for this payment method.")
            
        if payment_method == 'paybill':
            if not cleaned_data.get('paybill_number'):
                raise forms.ValidationError("Paybill number is required for this payment method.")
            if not cleaned_data.get('account_number'):
                raise forms.ValidationError("Account number is required for this payment method.")
                
        if payment_method == 'till_number' and not cleaned_data.get('till_number'):
            raise forms.ValidationError("Till number is required for this payment method.")
            
        return cleaned_data


