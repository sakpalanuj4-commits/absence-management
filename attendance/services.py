from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from academics.models import ClassSession
from accounts.models import Role, User
from accounts.services import notify

from .models import AttendanceRecord, RequestStatus, Status


@transaction.atomic
def save_register(session, marked_by, rows):
    """Create or update the records for one session from the posted rows."""
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
            AttendanceRecord.objects.create(
                session=session,
                student=enrolled[student_id],
                status=status,
                remark=remark,
                marked_by=marked_by,
            )
        else:
            record.status = status
            record.remark = remark
            record.marked_by = marked_by
            record.save(update_fields=["status", "remark", "marked_by", "updated_at"])
        written += 1

    return written


def reviewers_for(course):
    """The course teachers, or the administrators if it has none."""
    teachers = list(course.teachers.filter(is_active=True))
    if teachers:
        return teachers
    return list(User.objects.filter(role=Role.ADMIN, is_active=True))


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
