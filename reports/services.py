from django.db.models import Count, Q
from django.utils import timezone

from academics.models import ClassSession, Course, Department, Enrolment
from accounts.models import AppSetting, Role, User
from attendance.models import COUNTS_AS_ATTENDED, AttendanceRecord, Status


ATTENDED_FILTER = Q(status__in=COUNTS_AS_ATTENDED)
LIVE_SESSION_FILTER = Q(session__is_cancelled=False)


def threshold():
    return AppSetting.attendance_threshold()


def percentage(attended, total):
    """The attendance percentage, or None when nothing is recorded yet."""
    if not total:
        return None
    return round(attended * 100 / total, 1)


def summarise(queryset, sessions=None):
    """Totals for a set of records.

    Sessions with no record yet count against the student.
    """
    totals = queryset.filter(LIVE_SESSION_FILTER).aggregate(
        total=Count("id"),
        attended=Count("id", filter=ATTENDED_FILTER),
        present=Count("id", filter=Q(status=Status.PRESENT)),
        absent=Count("id", filter=Q(status=Status.ABSENT)),
        late=Count("id", filter=Q(status=Status.LATE)),
        excused=Count("id", filter=Q(status=Status.EXCUSED)),
    )
    if sessions is not None:
        totals["total"] = max(totals["total"], sessions)
    totals["percentage"] = percentage(totals["attended"], totals["total"])
    return totals


def student_course_summary(student, course):
    held = ClassSession.objects.filter(course=course, is_cancelled=False).count()
    return summarise(
        AttendanceRecord.objects.filter(student=student, session__course=course),
        sessions=held,
    )


def student_overall_summary(student):
    return summarise(AttendanceRecord.objects.filter(student=student))


def student_course_rows(student):
    """One row per course the student is enrolled on."""
    rows = []
    enrolments = (
        Enrolment.objects.filter(student=student, is_active=True)
        .select_related("course", "course__department")
        .order_by("course__code")
    )
    limit = threshold()
    for enrolment in enrolments:
        summary = student_course_summary(student, enrolment.course)
        summary["course"] = enrolment.course
        summary["below_threshold"] = (
            summary["percentage"] is not None and summary["percentage"] < limit
        )
        rows.append(summary)
    return rows


def course_summary(course):
    return summarise(AttendanceRecord.objects.filter(session__course=course))


def course_student_rows(course):
    """One row per student enrolled on the course."""
    students = User.objects.filter(
        enrolments__course=course, enrolments__is_active=True
    ).order_by("last_name", "first_name")
    limit = threshold()
    rows = []
    for student in students:
        summary = student_course_summary(student, course)
        summary["student"] = student
        summary["below_threshold"] = (
            summary["percentage"] is not None and summary["percentage"] < limit
        )
        rows.append(summary)
    return rows


def session_summary(session):
    return summarise(AttendanceRecord.objects.filter(session=session))


def overall_summary(records=None):
    if records is None:
        records = AttendanceRecord.objects.all()
    return summarise(records)


def students_below_threshold(courses=None):
    course_qs = Course.objects.filter(is_active=True)
    if courses is not None:
        course_qs = course_qs.filter(pk__in=[c.pk for c in courses])
    flagged = []
    for course in course_qs:
        for row in course_student_rows(course):
            if row["below_threshold"]:
                flagged.append(
                    {
                        "student": row["student"],
                        "course": course,
                        "percentage": row["percentage"],
                        "absent": row["absent"],
                    }
                )
    flagged.sort(key=lambda r: r["percentage"])
    return flagged


def department_rows():
    rows = []
    for department in Department.objects.all():
        summary = summarise(
            AttendanceRecord.objects.filter(session__course__department=department)
        )
        summary["department"] = department
        rows.append(summary)
    return rows


def course_rows(courses=None):
    if courses is None:
        courses = Course.objects.filter(is_active=True)
    rows = []
    for course in courses:
        summary = course_summary(course)
        summary["course"] = course
        rows.append(summary)
    return rows


def visible_records(user):
    records = AttendanceRecord.objects.select_related(
        "session", "session__course", "student"
    )
    if user.is_admin:
        return records
    if user.is_teacher:
        return records.filter(session__course__teachers=user)
    return records.filter(student=user)


def visible_courses(user):
    courses = Course.objects.select_related("department")
    if user.is_teacher:
        return courses.filter(teachers=user)
    if user.is_student:
        return courses.filter(enrolments__student=user, enrolments__is_active=True)
    return courses


def unmarked_sessions(user, limit=None):
    """Past sessions with no register taken yet."""
    sessions = (
        ClassSession.objects.filter(is_cancelled=False, date__lte=timezone.localdate())
        .annotate(marked=Count("attendance_records"))
        .filter(marked=0)
        .select_related("course")
        .order_by("-date")
    )
    if user.is_teacher:
        sessions = sessions.filter(course__teachers=user)
    return sessions[:limit] if limit else sessions


def student_count():
    return User.objects.filter(role=Role.STUDENT, is_active=True).count()
