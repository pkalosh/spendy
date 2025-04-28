from django.contrib import admin
from userauths.models import User
# Register your models here.
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html


class UserAdmin(BaseUserAdmin):
    list_display = (
        'email', 'first_name', 'last_name', 'phone_number','company_name',
         'verified_status', 'created_at'
    )
    list_filter = ('is_staff', 'is_admin', 'is_verified', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number','company_name')
    ordering = ('email','first_name','last_name','phone_number','created_at')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Information', {'fields': ('first_name', 'last_name', 'phone_number', 'country','company_name')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'is_admin', 'is_verified')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
        ('Groups & Permissions', {'fields': ('groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name','company_name', 'password1', 'password2', 'is_staff', 'is_superuser', 'is_admin', 'is_verified')}
        ),
    )

    readonly_fields = ('created_at', 'updated_at')

    def staff_status(self, obj):
        return obj.is_staff
    staff_status.short_description = "Staff"

    def superuser_status(self, obj):
        return obj.is_superuser
    superuser_status.short_description = "Super User"



    def verified_status(self, obj):
        return obj.is_verified
    verified_status.short_description = "Verified"


# Register the custom UserAdmin
admin.site.register(User, UserAdmin)
