import json

from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import ClassSession, Course
from accounts.permissions import (
    require_course_access,
    staff_required,
    teacher_owns_course,
)

from .models import AttendanceRecord, Status
from .services import save_register


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

    written = save_register(session, request.user, rows)
    return JsonResponse({"ok": True, "saved": written})
