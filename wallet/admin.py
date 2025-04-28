from django.contrib import admin
from .models import Wallet,CompanyKYC,Notification,Transaction,StaffProfile,Role,Module
# Register your models here.
admin.site.register(Wallet)
admin.site.register(CompanyKYC)
admin.site.register(Notification)
admin.site.register(Transaction)
admin.site.register(StaffProfile)
admin.site.register(Role)
admin.site.register(Module)