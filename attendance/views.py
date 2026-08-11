import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import ClassSession, Course
from accounts.models import Role
from accounts.permissions import (
    require_course_access,
    role_required,
    staff_required,
    student_required,
    teacher_owns_course,
)
from reports import services

from .forms import AbsenceRequestForm, ReviewForm
from .models import AbsenceRequest, AttendanceRecord, RequestStatus, Status
from .services import (
    approve_request,
    notify_absent_students,
    notify_low_attendance,
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

    page = Paginator(sessions, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "attendance/register_list.html",
        {
            "page": page,
            "courses": services.visible_courses(request.user),
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

    written, newly_absent, marked_students = save_register(session, request.user, rows)
    notify_absent_students(session, newly_absent)
    notify_low_attendance(session.course, marked_students, services.threshold())

    summary = services.session_summary(session)
    return JsonResponse(
        {
            "ok": True,
            "saved": written,
            "absent_notified": len(newly_absent),
            "summary": {
                "present": summary["present"],
                "absent": summary["absent"],
                "late": summary["late"],
                "excused": summary["excused"],
                "percentage": summary["percentage"],
            },
        }
    )


@student_required
def my_attendance(request):
    records = services.apply_filters(
        services.visible_records(request.user), request.GET
    ).order_by("-session__date", "session__start_time")
    page = Paginator(records, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "attendance/my_attendance.html",
        {
            "page": page,
            "rows": services.student_course_rows(request.user),
            "courses": services.visible_courses(request.user),
            "statuses": Status.choices,
            "threshold": services.threshold(),
            "filters": request.GET,
        },
    )


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


@staff_required
def course_attendance(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    require_course_access(request.user, course)
    rows = services.course_student_rows(course)
    return render(
        request,
        "attendance/course_attendance.html",
        {
            "course": course,
            "rows": rows,
            "summary": services.course_summary(course),
            "threshold": services.threshold(),
            "flagged": [r for r in rows if r["below_threshold"]],
        },
    )
