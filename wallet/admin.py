from django.contrib import admin
from .models import Wallet,CompanyKYC,Notification,Transaction
# Register your models here.
admin.site.register(Wallet)
admin.site.register(CompanyKYC)
admin.site.register(Notification)
admin.site.register(Transaction)