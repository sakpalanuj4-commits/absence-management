from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AppSetting, Notification, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Absence Management", {"fields": ("role", "phone", "must_change_password")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Absence Management", {"fields": ("role", "email", "phone")}),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "message", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("recipient__username", "message")


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value")
