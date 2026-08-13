from datetime import time

import pytest
from django.urls import reverse

from academics.models import ClassSession, Enrolment
from accounts.models import Notification
from attendance.models import AbsenceRequest, AttendanceRecord, RequestStatus, Status
from attendance.services import approve_request, reject_request

pytestmark = pytest.mark.django_db


@pytest.fixture
def absence(students, course, sessions):
    """Covers the first session only."""
    return AbsenceRequest.objects.create(
        student=students[0],
        course=course,
        start_date=sessions[0].date,
        end_date=sessions[0].date,
        reason="Hospital appointment",
    )


def test_approval_excuses_only_sessions_in_range(
    absence, students, course, sessions, teacher
):
    excused = approve_request(absence, teacher, "Evidence seen")

    assert excused == 1
    records = AttendanceRecord.objects.filter(student=students[0])
    assert records.count() == 1
    record = records.first()
    assert record.session == sessions[0]
    assert record.status == Status.EXCUSED


def test_approval_overwrites_an_existing_absence(
    absence, students, sessions, teacher
):
    AttendanceRecord.objects.create(
        session=sessions[0],
        student=students[0],
        status=Status.ABSENT,
        marked_by=teacher,
    )

    approve_request(absence, teacher, "")

    record = AttendanceRecord.objects.get(session=sessions[0], student=students[0])
    assert record.status == Status.EXCUSED


def test_approval_does_not_touch_other_students(
    absence, students, sessions, teacher
):
    AttendanceRecord.objects.create(
        session=sessions[0],
        student=students[1],
        status=Status.ABSENT,
        marked_by=teacher,
    )

    approve_request(absence, teacher, "")

    other = AttendanceRecord.objects.get(session=sessions[0], student=students[1])
    assert other.status == Status.ABSENT


def test_approval_skips_cancelled_sessions(
    students, course, sessions, teacher
):
    cancelled = next(s for s in sessions if s.is_cancelled)
    absence = AbsenceRequest.objects.create(
        student=students[0],
        course=course,
        start_date=cancelled.date,
        end_date=cancelled.date,
        reason="Ill",
    )

    excused = approve_request(absence, teacher, "")

    assert excused == 0
    assert AttendanceRecord.objects.count() == 0


def test_approval_does_not_touch_another_course(
    students, course, other_course, sessions, teacher
):
    """A request against CS101 must not excuse a CS202 session on the same day."""
    clash = ClassSession.objects.create(
        course=other_course,
        date=sessions[0].date,
        start_time=time(14, 0),
        end_time=time(16, 0),
    )
    absence = AbsenceRequest.objects.create(
        student=students[0],
        course=course,
        start_date=sessions[0].date,
        end_date=sessions[0].date,
        reason="Ill",
    )

    approve_request(absence, teacher, "")

    assert not AttendanceRecord.objects.filter(session=clash).exists()


def test_multi_day_request_excuses_every_session_in_range(
    students, course, sessions, teacher
):
    live = [s for s in sessions if not s.is_cancelled]
    absence = AbsenceRequest.objects.create(
        student=students[0],
        course=course,
        start_date=live[0].date,
        end_date=live[-1].date,
        reason="Extended illness",
    )

    excused = approve_request(absence, teacher, "")

    assert excused == len(live)
    assert (
        AttendanceRecord.objects.filter(
            student=students[0], status=Status.EXCUSED
        ).count()
        == len(live)
    )


def test_rejection_leaves_attendance_alone(absence, students, sessions, teacher):
    AttendanceRecord.objects.create(
        session=sessions[0],
        student=students[0],
        status=Status.ABSENT,
        marked_by=teacher,
    )

    reject_request(absence, teacher, "No evidence")
    absence.refresh_from_db()

    assert absence.status == RequestStatus.REJECTED
    record = AttendanceRecord.objects.get(session=sessions[0], student=students[0])
    assert record.status == Status.ABSENT


def test_student_is_notified_of_the_decision(absence, students, teacher):
    approve_request(absence, teacher, "Fine")

    assert Notification.objects.filter(
        recipient=students[0], message__icontains="approved"
    ).exists()


def test_teacher_can_review_through_the_view(client_teacher, absence, teacher):
    response = client_teacher.post(
        reverse("attendance:request_review", kwargs={"pk": absence.pk}),
        {"decision": "approve", "comment": "Approved"},
    )

    assert response.status_code == 302
    absence.refresh_from_db()
    assert absence.status == RequestStatus.APPROVED
    assert absence.reviewed_by == teacher


def test_a_decided_request_cannot_be_reviewed_twice(
    client_teacher, absence, teacher
):
    reject_request(absence, teacher, "No")

    client_teacher.post(
        reverse("attendance:request_review", kwargs={"pk": absence.pk}),
        {"decision": "approve", "comment": "changed my mind"},
    )

    absence.refresh_from_db()
    assert absence.status == RequestStatus.REJECTED


def test_student_can_submit_a_request(client_student, course, students):
    response = client_student.post(
        reverse("attendance:request_create"),
        {
            "course": course.pk,
            "start_date": "2026-03-02",
            "end_date": "2026-03-03",
            "category": "MEDICAL",
            "reason": "Unwell",
        },
    )

    assert response.status_code == 302
    absence = AbsenceRequest.objects.get(student=students[0])
    assert absence.status == RequestStatus.PENDING


def test_end_date_before_start_date_is_refused(client_student, course):
    client_student.post(
        reverse("attendance:request_create"),
        {
            "course": course.pk,
            "start_date": "2026-03-05",
            "end_date": "2026-03-01",
            "category": "MEDICAL",
            "reason": "Unwell",
        },
    )

    assert AbsenceRequest.objects.count() == 0


def test_student_cannot_request_absence_for_a_course_they_are_not_on(
    client_student, other_course, students
):
    """Student 1 is enrolled on other_course; student 2 is not."""
    Enrolment.objects.filter(student=students[0], course=other_course).delete()

    client_student.post(
        reverse("attendance:request_create"),
        {
            "course": other_course.pk,
            "start_date": "2026-03-02",
            "end_date": "2026-03-02",
            "category": "OTHER",
            "reason": "Trying it on",
        },
    )

    assert AbsenceRequest.objects.count() == 0


def test_pending_request_can_be_withdrawn(client_student, absence):
    response = client_student.post(
        reverse("attendance:request_withdraw", kwargs={"pk": absence.pk})
    )

    assert response.status_code == 302
    assert AbsenceRequest.objects.count() == 0


def test_reviewers_are_notified_of_a_new_request(client_student, course, teacher):
    client_student.post(
        reverse("attendance:request_create"),
        {
            "course": course.pk,
            "start_date": "2026-03-02",
            "end_date": "2026-03-02",
            "category": "MEDICAL",
            "reason": "Unwell",
        },
    )

    assert Notification.objects.filter(recipient=teacher).exists()
