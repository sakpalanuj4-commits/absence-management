import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import ClassSession, Course, Enrolment
from accounts.models import AppSetting, Role
from accounts.permissions import (
    require_course_access,
    role_required,
    staff_required,
    student_required,
    teacher_owns_course,
)

from .forms import AbsenceRequestForm, ReviewForm
from .models import (
    COUNTS_AS_ATTENDED,
    AbsenceRequest,
    AttendanceRecord,
    RequestStatus,
    Status,
)
from .services import (
    approve_request,
    notify_absent_students,
    reject_request,
    save_register,
    submit_request,
)


@staff_required
def register_list(request):
    sessions = (
        ClassSession.objects.filter(is_cancelled=False)
        .select_related("course")
        .annotate(marked=Count("attendance_records"))
        .order_by("-date", "start_time")
    )
    if request.user.is_teacher:
        sessions = sessions.filter(course__teachers=request.user)

    course_id = request.GET.get("course")
    state = request.GET.get("state", "")
    if course_id:
        sessions = sessions.filter(course_id=course_id)
    if state == "unmarked":
        sessions = sessions.filter(marked=0, date__lte=timezone.localdate())
    elif state == "marked":
        sessions = sessions.filter(marked__gt=0)

    courses = Course.objects.all()
    if request.user.is_teacher:
        courses = courses.filter(teachers=request.user)

    page = Paginator(sessions, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "attendance/register_list.html",
        {
            "page": page,
            "courses": courses,
            "course_id": course_id,
            "state": state,
        },
    )


@staff_required
def register(request, session_pk):
    session = get_object_or_404(
        ClassSession.objects.select_related("course"), pk=session_pk
    )
    require_course_access(request.user, session.course)

    students = session.course.active_students()
    existing = {
        record.student_id: record
        for record in AttendanceRecord.objects.filter(session=session)
    }
    rows = []
    for student in students:
        record = existing.get(student.pk)
        rows.append(
            {
                "student": student,
                "status": record.status if record else "",
                "remark": record.remark if record else "",
            }
        )

    return render(
        request,
        "attendance/register.html",
        {
            "session": session,
            "rows": rows,
            "statuses": Status.choices,
            "is_marked": bool(existing),
        },
    )


@staff_required
@require_POST
def register_save(request, session_pk):
    session = get_object_or_404(ClassSession, pk=session_pk)
    if not teacher_owns_course(request.user, session.course):
        return JsonResponse(
            {"ok": False, "error": "You are not assigned to this course."}, status=403
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Malformed request."}, status=400)

    rows = payload.get("records") or []
    if not isinstance(rows, list):
        return JsonResponse({"ok": False, "error": "Malformed request."}, status=400)

    written, newly_absent, _ = save_register(session, request.user, rows)
    notify_absent_students(session, newly_absent)
    return JsonResponse(
        {"ok": True, "saved": written, "absent_notified": len(newly_absent)}
    )


def course_rows_for(student, limit):
    """Attendance per course for one student."""
    rows = []
    enrolments = (
        Enrolment.objects.filter(student=student, is_active=True)
        .select_related("course")
        .order_by("course__code")
    )
    for enrolment in enrolments:
        counts = AttendanceRecord.objects.filter(
            student=student,
            session__course=enrolment.course,
            session__is_cancelled=False,
        ).aggregate(
            total=Count("id"),
            attended=Count("id", filter=Q(status__in=COUNTS_AS_ATTENDED)),
            absent=Count("id", filter=Q(status=Status.ABSENT)),
        )
        percentage = (
            round(counts["attended"] * 100 / counts["total"], 1)
            if counts["total"]
            else None
        )
        rows.append(
            {
                "course": enrolment.course,
                "total": counts["total"],
                "attended": counts["attended"],
                "absent": counts["absent"],
                "percentage": percentage,
                "below_threshold": percentage is not None and percentage < limit,
            }
        )
    return rows


@student_required
def my_attendance(request):
    records = AttendanceRecord.objects.filter(student=request.user).select_related(
        "session", "session__course"
    )
    if request.GET.get("course"):
        records = records.filter(session__course_id=request.GET["course"])
    if request.GET.get("status"):
        records = records.filter(status=request.GET["status"])
    if request.GET.get("from"):
        records = records.filter(session__date__gte=request.GET["from"])
    if request.GET.get("to"):
        records = records.filter(session__date__lte=request.GET["to"])
    records = records.order_by("-session__date", "session__start_time")

    limit = AppSetting.attendance_threshold()
    page = Paginator(records, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "attendance/my_attendance.html",
        {
            "page": page,
            "rows": course_rows_for(request.user, limit),
            "courses": Course.objects.filter(
                enrolments__student=request.user, enrolments__is_active=True
            ),
            "statuses": Status.choices,
            "threshold": limit,
            "filters": request.GET,
        },
    )


@student_required
def request_create(request):
    form = AbsenceRequestForm(
        request.POST or None, request.FILES or None, student=request.user
    )
    if request.method == "POST" and form.is_valid():
        submit_request(form.save(commit=False))
        messages.success(request, "Your absence request has been submitted.")
        return redirect("attendance:request_list")
    return render(request, "attendance/request_form.html", {"form": form})


@role_required(Role.ADMIN, Role.TEACHER, Role.STUDENT)
def request_list(request):
    requests = AbsenceRequest.objects.select_related("student", "course", "reviewed_by")
    if request.user.is_student:
        requests = requests.filter(student=request.user)
    elif request.user.is_teacher:
        requests = requests.filter(course__teachers=request.user)

    status = request.GET.get("status", "")
    if status:
        requests = requests.filter(status=status)

    page = Paginator(requests, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "attendance/request_list.html",
        {
            "page": page,
            "status": status,
            "statuses": RequestStatus.choices,
            "review_form": ReviewForm(),
        },
    )


@role_required(Role.ADMIN, Role.TEACHER, Role.STUDENT)
def request_detail(request, pk):
    absence_request = get_object_or_404(
        AbsenceRequest.objects.select_related("student", "course", "reviewed_by"),
        pk=pk,
    )
    if request.user.is_student and absence_request.student_id != request.user.pk:
        raise PermissionDenied("This request belongs to another student.")
    if request.user.is_teacher and not teacher_owns_course(
        request.user, absence_request.course
    ):
        raise PermissionDenied("You are not assigned to this course.")

    return render(
        request,
        "attendance/request_detail.html",
        {"object": absence_request, "review_form": ReviewForm()},
    )


@staff_required
@require_POST
def request_review(request, pk):
    absence_request = get_object_or_404(AbsenceRequest, pk=pk)
    require_course_access(request.user, absence_request.course)

    if not absence_request.is_pending:
        messages.error(request, "That request has already been decided.")
        return redirect("attendance:request_list")

    form = ReviewForm(request.POST)
    comment = form.cleaned_data["comment"] if form.is_valid() else ""

    if request.POST.get("decision") == "approve":
        excused = approve_request(absence_request, request.user, comment)
        messages.success(
            request, f"Request approved, {excused} sessions marked as excused."
        )
    else:
        reject_request(absence_request, request.user, comment)
        messages.success(request, "Request rejected.")
    return redirect("attendance:request_list")


@student_required
@require_POST
def request_withdraw(request, pk):
    absence_request = get_object_or_404(
        AbsenceRequest, pk=pk, student=request.user, status=RequestStatus.PENDING
    )
    absence_request.delete()
    messages.success(request, "Request withdrawn.")
    return redirect("attendance:request_list")
