import csv
import io

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Role, User
from accounts.permissions import admin_required, require_course_access, staff_required

from .forms import (
    ClassSessionForm,
    CourseForm,
    DepartmentForm,
    EnrolmentForm,
    SessionGeneratorForm,
)
from .models import ClassSession, Course, Department, Enrolment


@admin_required
def department_list(request):
    departments = Department.objects.annotate(course_count=Count("courses"))
    return render(request, "academics/department_list.html", {"departments": departments})


@admin_required
def department_form(request, pk=None):
    department = get_object_or_404(Department, pk=pk) if pk else None
    form = DepartmentForm(request.POST or None, instance=department)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department saved.")
        return redirect("academics:department_list")
    return render(
        request,
        "academics/department_form.html",
        {"form": form, "object": department},
    )


def visible_courses(user):
    courses = Course.objects.select_related("department").prefetch_related("teachers")
    if user.is_teacher:
        return courses.filter(teachers=user)
    return courses


@staff_required
def course_list(request):
    courses = visible_courses(request.user).annotate(
        enrolled=Count("enrolments", filter=Q(enrolments__is_active=True))
    )
    query = request.GET.get("q", "").strip()
    if query:
        courses = courses.filter(Q(code__icontains=query) | Q(name__icontains=query))
    page = Paginator(courses, 25).get_page(request.GET.get("page"))
    return render(request, "academics/course_list.html", {"page": page, "q": query})


@admin_required
def course_form(request, pk=None):
    course = get_object_or_404(Course, pk=pk) if pk else None
    form = CourseForm(request.POST or None, instance=course)
    if request.method == "POST" and form.is_valid():
        course = form.save()
        messages.success(request, f"Course {course.code} saved.")
        return redirect("academics:course_detail", pk=course.pk)
    return render(
        request, "academics/course_form.html", {"form": form, "object": course}
    )


@staff_required
def course_detail(request, pk):
    course = get_object_or_404(
        Course.objects.select_related("department").prefetch_related("teachers"), pk=pk
    )
    require_course_access(request.user, course)
    enrolments = (
        Enrolment.objects.filter(course=course, is_active=True)
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
    )
    sessions = course.sessions.all()[:20]
    enrol_form = EnrolmentForm(course=course)
    return render(
        request,
        "academics/course_detail.html",
        {
            "course": course,
            "enrolments": enrolments,
            "sessions": sessions,
            "enrol_form": enrol_form,
        },
    )


@admin_required
@require_POST
def enrolment_add(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    form = EnrolmentForm(request.POST, course=course)
    if form.is_valid():
        enrolment = form.save()
        messages.success(request, f"{enrolment.student.display_name} enrolled.")
    else:
        messages.error(request, "That student could not be enrolled.")
    return redirect("academics:course_detail", pk=course.pk)


@admin_required
@require_POST
def enrolment_remove(request, pk):
    enrolment = get_object_or_404(Enrolment, pk=pk)
    course_pk = enrolment.course_id
    enrolment.is_active = False
    enrolment.save(update_fields=["is_active"])
    messages.success(
        request, f"{enrolment.student.display_name} removed from the course."
    )
    return redirect("academics:course_detail", pk=course_pk)


ENROLMENT_CSV_COLUMNS = ["username", "course_code"]


@admin_required
def enrolment_import(request):
    results = None
    if request.method == "POST" and request.FILES.get("file"):
        results = import_enrolments(request.FILES["file"])
        messages.success(
            request,
            f"{results['created']} enrolments created, "
            f"{len(results['errors'])} rows rejected.",
        )
    return render(
        request,
        "academics/enrolment_import.html",
        {"results": results, "columns": ENROLMENT_CSV_COLUMNS},
    )


def import_enrolments(upload):
    text = io.TextIOWrapper(upload.file, encoding="utf-8-sig")
    reader = csv.DictReader(text)
    created, errors = 0, []

    for line, row in enumerate(reader, start=2):
        username = (row.get("username") or "").strip()
        code = (row.get("course_code") or "").strip()

        student = User.objects.filter(username=username, role=Role.STUDENT).first()
        if student is None:
            errors.append(
                {"line": line, "row": row, "error": f"no student '{username}'"}
            )
            continue
        course = Course.objects.filter(code=code).first()
        if course is None:
            errors.append({"line": line, "row": row, "error": f"no course '{code}'"})
            continue

        _, was_created = Enrolment.objects.get_or_create(
            student=student, course=course, defaults={"is_active": True}
        )
        if was_created:
            created += 1
        else:
            errors.append({"line": line, "row": row, "error": "already enrolled"})

    return {"created": created, "errors": errors}


@staff_required
def session_list(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    require_course_access(request.user, course)
    sessions = course.sessions.all()
    page = Paginator(sessions, 30).get_page(request.GET.get("page"))
    return render(
        request, "academics/session_list.html", {"course": course, "page": page}
    )


@staff_required
def session_form(request, course_pk, pk=None):
    course = get_object_or_404(Course, pk=course_pk)
    require_course_access(request.user, course)
    session = get_object_or_404(ClassSession, pk=pk, course=course) if pk else None
    form = ClassSessionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.course = course
        session.save()
        messages.success(request, "Session saved.")
        return redirect("academics:session_list", course_pk=course.pk)
    return render(
        request,
        "academics/session_form.html",
        {"form": form, "course": course, "object": session},
    )


@staff_required
def session_generate(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    require_course_access(request.user, course)
    form = SessionGeneratorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        created, skipped = 0, 0
        for day in form.dates():
            _, was_created = ClassSession.objects.get_or_create(
                course=course,
                date=day,
                start_time=form.cleaned_data["start_time"],
                defaults={
                    "end_time": form.cleaned_data["end_time"],
                    "room": form.cleaned_data["room"],
                },
            )
            created += 1 if was_created else 0
            skipped += 0 if was_created else 1
        messages.success(
            request,
            f"{created} sessions created"
            + (f", {skipped} already existed." if skipped else "."),
        )
        return redirect("academics:session_list", course_pk=course.pk)
    return render(
        request, "academics/session_generate.html", {"form": form, "course": course}
    )


@staff_required
@require_POST
def session_cancel(request, pk):
    session = get_object_or_404(ClassSession, pk=pk)
    require_course_access(request.user, session.course)
    session.is_cancelled = not session.is_cancelled
    session.save(update_fields=["is_cancelled"])
    state = "cancelled" if session.is_cancelled else "reinstated"
    messages.success(request, f"Session {state}.")
    return redirect("academics:session_list", course_pk=session.course_id)
