from django.contrib import admin

from .models import AbsenceRequest, AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "session", "status", "marked_by", "marked_at")
    list_filter = ("status", "session__course")
    search_fields = ("student__username", "student__last_name")
    autocomplete_fields = ("student",)
    readonly_fields = ("marked_at", "updated_at")


@admin.register(AbsenceRequest)
class AbsenceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course",
        "start_date",
        "end_date",
        "category",
        "status",
        "reviewed_by",
    )
    list_filter = ("status", "category", "course")
    search_fields = ("student__username", "reason")
    autocomplete_fields = ("student",)
    readonly_fields = ("created_at", "reviewed_at")
