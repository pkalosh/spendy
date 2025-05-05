from django import forms
from .models import Expense, Event, Operation, ExpenseGroup
from wallet.models import Wallet
class EventExpenseForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'category', 'company', 'start_date', 'end_date', 'budget', 'project_lead', 'location', 'created_by','description']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control'}),
            'project_lead': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Extract user and company from kwargs before passing to parent class
        self.user = kwargs.pop('user', None)
        self.company = kwargs.pop('company', None)
        super(EventExpenseForm, self).__init__(*args, **kwargs)
        
        # Set initial values and hide certain fields
        if self.user:
            self.fields['created_by'].initial = self.user
            self.fields['created_by'].widget = forms.HiddenInput()
        
        if self.company:
            self.fields['company'].initial = self.company
            self.fields['company'].widget = forms.HiddenInput()


class OperationExpenseForm(forms.ModelForm):
    class Meta:
        model = Operation
        fields = ['name', 'category', 'company', 'budget', 'project_lead', 'created_by','description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control'}),
            'project_lead': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Extract user and company from kwargs before passing to parent class
        self.user = kwargs.pop('user', None)
        self.company = kwargs.pop('company', None)
        super(OperationExpenseForm, self).__init__(*args, **kwargs)
        
        # Set initial values and hide certain fields
        if self.user:
            self.fields['created_by'].initial = self.user
            self.fields['created_by'].widget = forms.HiddenInput()
        
        if self.company:
            self.fields['company'].initial = self.company
            self.fields['company'].widget = forms.HiddenInput()


class ExpenseRequestForm(forms.ModelForm):
    """Form for creating expense requests"""
    class Meta:
        model = Expense
        fields = ['wallet', 'expense_group', 'event', 'operation']
        widgets = {
            'wallet': forms.Select(attrs={'class': 'form-control'}),
            'expense_group': forms.Select(attrs={'class': 'form-control', 'id': 'id_expense_group'}),
            'event': forms.Select(attrs={'class': 'form-control'}),
            'operation': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': '3', 'placeholder': 'Enter detailed reason for this expense'}),
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.company = kwargs.pop('company', None)
        
        super().__init__(*args, **kwargs)
        
        # Initialize with empty querysets to avoid NoneType errors
        self.fields['event'].queryset = Event.objects.none()
        self.fields['operation'].queryset = Operation.objects.none()
        self.fields['wallet'].queryset = Wallet.objects.none()
        
        # Only filter if company is provided
        if self.company:
            self.fields['event'].queryset = Event.objects.filter(
                created_by=self.user,
                company=self.company, 
                approved=False,
                paid=False
            )
            self.fields['operation'].queryset = Operation.objects.filter(
                created_by=self.user,
                company=self.company, 
                approved=False,
                paid=False
            )
            self.fields['wallet'].queryset = Wallet.objects.filter(
                company=self.company, 
                is_active=True
            ).exclude(wallet_type="PRIMARY")
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


