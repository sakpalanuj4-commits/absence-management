from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from academics.models import ClassSession, Course, Department
from accounts.models import Role
from accounts.permissions import (
    admin_required,
    require_course_access,
    role_required,
    staff_required,
    student_required,
    teacher_required,
)
from attendance.models import AbsenceRequest, RequestStatus, Status

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


def filtered_records(request):
    return services.apply_filters(services.visible_records(request.user), request.GET)


@role_required(Role.ADMIN, Role.TEACHER, Role.STUDENT)
def attendance_report(request):
    records = filtered_records(request).order_by(
        "-session__date", "session__start_time", "student__last_name"
    )
    page = Paginator(records, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "reports/attendance_report.html",
        {
            "page": page,
            "summary": services.overall_summary(records),
            "courses": services.visible_courses(request.user),
            "departments": Department.objects.all(),
            "statuses": Status.choices,
            "threshold": services.threshold(),
            "filters": request.GET,
            "query_string": request.GET.urlencode(),
        },
    )


@staff_required
def course_report(request, course_pk):
    course = Course.objects.select_related("department").get(pk=course_pk)
    require_course_access(request.user, course)
    return render(
        request,
        "reports/course_report.html",
        {
            "course": course,
            "summary": services.course_summary(course),
            "rows": services.course_student_rows(course),
            "threshold": services.threshold(),
            "sessions": course.sessions.annotate(
                total=Count("attendance_records"),
                attended=Count(
                    "attendance_records",
                    filter=Q(
                        attendance_records__status__in=[
                            Status.PRESENT,
                            Status.LATE,
                            Status.EXCUSED,
                        ]
                    ),
                ),
            )[:20],
        },
    )


@role_required(Role.ADMIN, Role.TEACHER, Role.STUDENT)
def chart_attendance_trend(request):
    records = filtered_records(request)
    bucket = "month" if request.GET.get("bucket") == "month" else "week"
    return JsonResponse({"data": services.trend(records, bucket)})


@role_required(Role.ADMIN, Role.TEACHER, Role.STUDENT)
def chart_status_distribution(request):
    data = services.status_distribution(filtered_records(request))
    return JsonResponse({"data": data})


@role_required(Role.ADMIN, Role.TEACHER, Role.STUDENT)
def chart_course_comparison(request):
    data = services.course_comparison(filtered_records(request))
    return JsonResponse({"data": data})


EXPORT_COLUMNS = [
    "Date",
    "Course code",
    "Course",
    "Student",
    "Username",
    "Status",
    "Remark",
    "Marked by",
]
