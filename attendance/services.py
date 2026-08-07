from django.db import transaction

from accounts.models import Role, User

from .models import AttendanceRecord, Status


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
