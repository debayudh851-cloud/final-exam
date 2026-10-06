from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class PortalUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'email_verified', 'is_staff')
    list_filter = ('role', 'email_verified', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (('Portal access', {'fields': ('role', 'email_verified')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Portal access', {'fields': ('email', 'role', 'email_verified')}),)
