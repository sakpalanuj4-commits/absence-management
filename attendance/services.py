from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from academics.models import ClassSession
from accounts.models import Notification, Role, User
from accounts.services import notify

from .models import AttendanceRecord, RequestStatus, Status


@transaction.atomic
def save_register(session, marked_by, rows):
    """Create or update the records for one session from the posted rows.

    Returns the number written, the students newly marked absent, and every
    student touched by this save.
    """
    enrolled = {
        student.pk: student
        for student in User.objects.filter(
            enrolments__course=session.course,
            enrolments__is_active=True,
            role=Role.STUDENT,
        )
    }
    existing = {
        record.student_id: record
        for record in AttendanceRecord.objects.filter(session=session)
    }
    valid_statuses = {value for value, _ in Status.choices}

    written = 0
    newly_absent = []
    touched = []

    for row in rows:
        try:
            student_id = int(row.get("student"))
        except (TypeError, ValueError):
            continue
        status = str(row.get("status", "")).upper()
        if student_id not in enrolled or status not in valid_statuses:
            continue

        remark = (row.get("remark") or "").strip()[:255]
        record = existing.get(student_id)

        if record is None:
            record = AttendanceRecord.objects.create(
                session=session,
                student=enrolled[student_id],
                status=status,
                remark=remark,
                marked_by=marked_by,
            )
            if status == Status.ABSENT:
                newly_absent.append(enrolled[student_id])
        else:
            became_absent = record.status != Status.ABSENT and status == Status.ABSENT
            record.status = status
            record.remark = remark
            record.marked_by = marked_by
            record.save(update_fields=["status", "remark", "marked_by", "updated_at"])
            if became_absent:
                newly_absent.append(enrolled[student_id])
        touched.append(enrolled[student_id])
        written += 1

    return written, newly_absent, touched


def notify_absent_students(session, students):
    link = reverse("attendance:my_attendance")
    for student in students:
        notify(
            student,
            f"You were marked absent for {session.course.code} on "
            f"{session.date:%d %b %Y}.",
            link=link,
            email=True,
            subject=f"Absence recorded: {session.course.code}",
        )


def notify_low_attendance(course, students, limit):
    """Warn students who have dropped below the threshold on this course.

    A student with an unread warning already is skipped, otherwise every save
    of the register would repeat it.
    """
    from reports.services import student_course_summary

    link = reverse("attendance:my_attendance")
    for student in students:
        summary = student_course_summary(student, course)
        if summary["percentage"] is None or summary["percentage"] >= limit:
            continue
        already_warned = Notification.objects.filter(
            recipient=student,
            is_read=False,
            message__startswith=f"Your attendance for {course.code}",
        ).exists()
        if already_warned:
            continue
        notify(
            student,
            f"Your attendance for {course.code} is {summary['percentage']}%, "
            f"below the required {limit}%.",
            link=link,
            email=True,
            subject=f"Low attendance warning: {course.code}",
        )


def reviewers_for(course):
    """The course teachers, or the administrators if it has none."""
    teachers = list(course.teachers.filter(is_active=True))
    if teachers:
        return teachers
    return list(User.objects.filter(role=Role.ADMIN, is_active=True))


def submit_request(absence_request):
    absence_request.status = RequestStatus.PENDING
    absence_request.save()
    link = reverse("attendance:request_list")
    for reviewer in reviewers_for(absence_request.course):
        notify(
            reviewer,
            f"{absence_request.student.display_name} requested absence for "
            f"{absence_request.course.code} "
            f"({absence_request.start_date:%d %b} - {absence_request.end_date:%d %b}).",
            link=link,
            email=True,
            subject="New absence request",
        )
    return absence_request


@transaction.atomic
def approve_request(absence_request, reviewer, comment=""):
    """Approve a request and excuse the sessions it covers.

    Records are created where the register has not been taken yet.
    """
    absence_request.status = RequestStatus.APPROVED
    absence_request.reviewed_by = reviewer
    absence_request.review_comment = comment
    absence_request.reviewed_at = timezone.now()
    absence_request.save()

    sessions = ClassSession.objects.filter(
        course=absence_request.course,
        date__gte=absence_request.start_date,
        date__lte=absence_request.end_date,
        is_cancelled=False,
    )
    excused = 0
    for session in sessions:
        AttendanceRecord.objects.update_or_create(
            session=session,
            student=absence_request.student,
            defaults={
                "status": Status.EXCUSED,
                "marked_by": reviewer,
                "remark": f"Excused: {absence_request.get_category_display()}",
            },
        )
        excused += 1

    notify(
        absence_request.student,
        f"Your absence request for {absence_request.course.code} was approved"
        + (f": {comment}" if comment else "."),
        link=reverse("attendance:request_list"),
        email=True,
        subject="Absence request approved",
    )
    return excused


def reject_request(absence_request, reviewer, comment=""):
    absence_request.status = RequestStatus.REJECTED
    absence_request.reviewed_by = reviewer
    absence_request.review_comment = comment
    absence_request.reviewed_at = timezone.now()
    absence_request.save()

    notify(
        absence_request.student,
        f"Your absence request for {absence_request.course.code} was rejected"
        + (f": {comment}" if comment else "."),
        link=reverse("attendance:request_list"),
        email=True,
        subject="Absence request rejected",
    )
    return absence_request
