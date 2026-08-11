from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from academics.models import ClassSession, Course
from accounts.permissions import admin_required, student_required, teacher_required
from attendance.models import AbsenceRequest, RequestStatus

from . import services


@admin_required
def admin_dashboard(request):
    records = services.visible_records(request.user)
    summary = services.overall_summary(records)
    return render(
        request,
        "reports/admin_dashboard.html",
        {
            "summary": summary,
            "threshold": services.threshold(),
            "student_count": services.student_count(),
            "course_count": Course.objects.filter(is_active=True).count(),
            "flagged": services.students_below_threshold()[:10],
            "unmarked": services.unmarked_sessions(request.user, limit=8),
            "pending_requests": AbsenceRequest.objects.filter(
                status=RequestStatus.PENDING
            ).select_related("student", "course")[:8],
            "departments": services.department_rows(),
        },
    )


@teacher_required
def teacher_dashboard(request):
    today = timezone.localdate()
    courses = Course.objects.filter(teachers=request.user, is_active=True)
    todays_sessions = (
        ClassSession.objects.filter(course__in=courses, date=today, is_cancelled=False)
        .select_related("course")
        .annotate(marked=Count("attendance_records"))
        .order_by("start_time")
    )
    records = services.visible_records(request.user)
    return render(
        request,
        "reports/teacher_dashboard.html",
        {
            "summary": services.overall_summary(records),
            "threshold": services.threshold(),
            "courses": services.course_rows(courses),
            "todays_sessions": todays_sessions,
            "unmarked": services.unmarked_sessions(request.user, limit=8),
            "pending_requests": AbsenceRequest.objects.filter(
                course__in=courses, status=RequestStatus.PENDING
            ).select_related("student", "course")[:8],
            "flagged": services.students_below_threshold(courses)[:10],
        },
    )


@student_required
def student_dashboard(request):
    today = timezone.localdate()
    rows = services.student_course_rows(request.user)
    upcoming = (
        ClassSession.objects.filter(
            course__enrolments__student=request.user,
            course__enrolments__is_active=True,
            date__gte=today,
            is_cancelled=False,
        )
        .select_related("course")
        .order_by("date", "start_time")[:6]
    )
    return render(
        request,
        "reports/student_dashboard.html",
        {
            "summary": services.student_overall_summary(request.user),
            "rows": rows,
            "threshold": services.threshold(),
            "at_risk": [row for row in rows if row["below_threshold"]],
            "upcoming": upcoming,
            "notifications": request.user.notifications.all()[:5],
            "requests": AbsenceRequest.objects.filter(student=request.user)[:5],
        },
    )
