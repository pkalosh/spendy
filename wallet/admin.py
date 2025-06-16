from django.contrib import admin
from .models import Wallet,CompanyKYC,Notification,Transaction,StaffProfile,Role,Module,SMSLog,MpesaCallbackLog,MpesaTransaction
# Register your models here.
# admin.site.register(Wallet)
# admin.site.register(CompanyKYC)
admin.site.register(Notification)
admin.site.register(Transaction)
admin.site.register(StaffProfile)
admin.site.register(Role)
admin.site.register(Module)
admin.site.register(SMSLog)
admin.site.register(MpesaCallbackLog)

@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_type',
        'status',
        'amount',
        'mpesa_receipt_number',
        'phone_number',
        'user',
        'created_at',
        'completed_at',
        'is_processed',
    )
    
    list_filter = (
        'transaction_type',
        'status',
        'command_id',
        'created_at',
        'is_processed',
    )
    
    search_fields = (
        'mpesa_receipt_number',
        'checkout_request_id',
        'transaction_id',
        'phone_number',
        'account_reference',
        'user__username',
        'user__email',
    )
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'completed_at',
        'callback_data',
        'response_code',
        'response_description',
        'error_code',
        'error_message',
    )
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Transaction Info', {
            'fields': ('id', 'transaction_type', 'status', 'command_id', 'amount', 'transaction_fee')
        }),
        ('Identifiers', {
            'fields': (
                'mpesa_receipt_number', 'transaction_id',
                'merchant_request_id', 'checkout_request_id',
                'conversation_id', 'originator_conversation_id',
            )
        }),
        ('Parties', {
            'fields': ('party_a', 'party_b', 'phone_number', 'account_reference')
        }),
        ('Descriptions', {
            'fields': ('transaction_desc', 'remarks', 'occasion', 'customer_message')
        }),
        ('Balance Details', {
            'classes': ('collapse',),
            'fields': (
                'account_balance', 'available_balance',
                'reserved_balance', 'uncleared_balance'
            )
        }),
        ('Reversal Details', {
            'classes': ('collapse',),
            'fields': ('original_transaction_id', 'reversal_reason')
        }),
        ('Callback & API Response', {
            'classes': ('collapse',),
            'fields': (
                'callback_data',
                'result_code', 'result_desc',
                'response_code', 'response_description',
                'error_code', 'error_message',
            )
        }),
        ('User & System Info', {
            'fields': ('user', 'ip_address', 'user_agent')
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at', 'completed_at', 'retry_count', 'is_processed', 'notes')
        }),
    )


@admin.register(CompanyKYC)
class CompanyKYCAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'status', 'date')
    search_fields = ('company_name', 'user__email', 'user__first_name')

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('wallet_number', 'user', 'wallet_type', 'balance', 'currency', 'is_active')
    search_fields = ('wallet_number', 'user__email', 'user__first_name')