from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import admin_required, require_course_access, staff_required

from .forms import CourseForm, DepartmentForm, EnrolmentForm
from .models import Course, Department, Enrolment


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
