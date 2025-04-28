from django.contrib import admin
from .models import Wallet,CompanyKYC,Notification,Transaction,StaffProfile,Role,Module
# Register your models here.
# admin.site.register(Wallet)
# admin.site.register(CompanyKYC)
admin.site.register(Notification)
admin.site.register(Transaction)
admin.site.register(StaffProfile)
admin.site.register(Role)
admin.site.register(Module)

@admin.register(CompanyKYC)
class CompanyKYCAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'status', 'date')
    search_fields = ('company_name', 'user__email', 'user__first_name')

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('wallet_number', 'user', 'wallet_type', 'balance', 'currency', 'is_active')
    search_fields = ('wallet_number', 'user__email', 'user__first_name')