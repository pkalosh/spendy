from django import forms
from .models import Expense, Event, Operation, ExpenseGroup
from wallet.models import Wallet
class ExpenseRequestForm(forms.ModelForm):
    """Form for creating expense requests"""
    class Meta:
        model = Expense
        fields = ['wallet', 'expense_group', 'event', 'operation']
        # Note: amount is not included in fields as it will be set automatically
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.company = kwargs.pop('company', None)
        
        super().__init__(*args, **kwargs)
        
        # Initialize with empty querysets to avoid NoneType errors
        self.fields['event'].queryset = Event.objects.none()
        self.fields['operation'].queryset = Operation.objects.none()
        self.fields['wallet'].queryset = Wallet.objects.none()
        # self.fields['expense_group'].widget.attrs.update({'id': 'id_expense_group'})
        # self.fields['wallet'].widget.attrs.update({'id': 'id_wallet'})  
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
    
    def clean(self):
        cleaned_data = super().clean()
        expense_group = cleaned_data.get('expense_group')
        event = cleaned_data.get('event')
        operation = cleaned_data.get('operation')
        wallet = cleaned_data.get('wallet')
        
        # Validate based on expense group selection
        if expense_group == ExpenseGroup.EVENT and not event:
            raise forms.ValidationError({
                'event': "Event is required for event expenses."
            })
            
        if expense_group == ExpenseGroup.OPERATION and not operation:
            raise forms.ValidationError({
                'operation': "Operation is required for operation expenses."
            })
            
        # Check if an expense request already exists for this event/operation
        if expense_group == ExpenseGroup.EVENT and event:
            existing_request = Expense.objects.filter(
                event=event,
                approved=False,
                paid=False,
                declined=False
            ).exists()
            
            if existing_request:
                raise forms.ValidationError({
                    'event': "A pending expense request already exists for this event."
                })
                
        if expense_group == ExpenseGroup.OPERATION and operation:
            existing_request = Expense.objects.filter(
                operation=operation,
                approved=False,
                paid=False,
                declined=False
            ).exists()
            
            if existing_request:
                raise forms.ValidationError({
                    'operation': "A pending expense request already exists for this operation."
                })
            
        # Determine budget amount based on expense group
        budget_amount = None
        if expense_group == ExpenseGroup.EVENT and event:
            budget_amount = event.budget
        elif expense_group == ExpenseGroup.OPERATION and operation:
            budget_amount = operation.budget
            
        # Check if wallet has enough balance
        if wallet and budget_amount is not None:
            if wallet.balance < budget_amount:
                raise forms.ValidationError({
                    'wallet': f"Insufficient funds in wallet. Available balance: {wallet.balance} {wallet.currency}"
                })
                
        return cleaned_data
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.created_by = self.user
        instance.company = self.company
        
        # Set amount based on expense group
        if instance.expense_group == ExpenseGroup.EVENT and instance.event:
            instance.amount = instance.event.budget
        elif instance.expense_group == ExpenseGroup.OPERATION and instance.operation:
            instance.amount = instance.operation.budget
            
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