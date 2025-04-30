from django import forms
from .models import Expense, Event, Operation, ExpenseGroup

class ExpenseRequestForm(forms.ModelForm):
    """Form for creating expense requests"""
    
    class Meta:
        model = Expense
        fields = ['wallet', 'amount', 'expense_group', 'event', 'operation']
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

        # Avoid 'NoneType' error by always defining fields
        self.fields['event'].queryset = Event.objects.none()
        self.fields['operation'].queryset = Operation.objects.none()

        if self.company:
            self.fields['event'].queryset = Event.objects.filter(company=self.company, approved=False)
            self.fields['operation'].queryset = Operation.objects.filter(company=self.company, approved=False)

    
    def clean(self):
        cleaned_data = super().clean()
        expense_group = cleaned_data.get('expense_group')
        event = cleaned_data.get('event')
        operation = cleaned_data.get('operation')
        wallet = cleaned_data.get('wallet')
        amount = cleaned_data.get('amount')
        
        # Validate based on expense group selection
        if expense_group == ExpenseGroup.EVENT and not event:
            raise forms.ValidationError("Event is required for event expenses.")
            
        if expense_group == ExpenseGroup.OPERATION and not operation:
            raise forms.ValidationError("Operation is required for operation expenses.")
        
        # Check if wallet has enough balance
        if wallet and amount and wallet.balance < amount:
            raise forms.ValidationError(
                f"Insufficient funds in wallet. Available balance: {wallet.balance} {wallet.currency}"
            )
            
        return cleaned_data
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.created_by = self.user
        instance.company = self.company
        
        if commit:
            instance.save()
        return instance


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