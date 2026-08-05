from django.contrib import admin

from .models import ClassSession, Course, Department, Enrolment


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "credits", "term", "is_active")
    list_filter = ("department", "is_active", "term")
    search_fields = ("code", "name")
    filter_horizontal = ("teachers",)


@admin.register(Enrolment)
class EnrolmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "enrolled_on", "is_active")
    list_filter = ("course", "is_active")
    search_fields = ("student__username", "course__code")
    autocomplete_fields = ("student",)


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ("course", "date", "start_time", "end_time", "room", "is_cancelled")
    list_filter = ("course", "is_cancelled", "date")
    date_hierarchy = "date"
