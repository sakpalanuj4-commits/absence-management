import json

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from accounts.models import Notification
from attendance.models import AttendanceRecord, Status

pytestmark = pytest.mark.django_db


def save(client, session, records):
    return client.post(
        reverse("attendance:register_save", kwargs={"session_pk": session.pk}),
        data=json.dumps({"records": records}),
        content_type="application/json",
    )


def test_register_save_round_trip(client_teacher, sessions, students, teacher):
    session = sessions[0]
    response = save(
        client_teacher,
        session,
        [
            {"student": students[0].pk, "status": "PRESENT", "remark": ""},
            {"student": students[1].pk, "status": "ABSENT", "remark": "No show"},
            {"student": students[2].pk, "status": "LATE", "remark": "20 min"},
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["saved"] == 3
    assert payload["summary"]["absent"] == 1

    records = {r.student_id: r for r in AttendanceRecord.objects.filter(session=session)}
    assert records[students[1].pk].status == Status.ABSENT
    assert records[students[1].pk].remark == "No show"
    assert records[students[0].pk].marked_by == teacher


def test_saving_twice_updates_rather_than_duplicates(
    client_teacher, sessions, students
):
    session = sessions[0]
    save(client_teacher, session, [{"student": students[0].pk, "status": "ABSENT"}])
    save(client_teacher, session, [{"student": students[0].pk, "status": "PRESENT"}])

    records = AttendanceRecord.objects.filter(session=session, student=students[0])
    assert records.count() == 1
    assert records.first().status == Status.PRESENT


def test_unique_constraint_on_session_and_student(sessions, students, teacher):
    AttendanceRecord.objects.create(
        session=sessions[0], student=students[0], status=Status.PRESENT
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AttendanceRecord.objects.create(
                session=sessions[0], student=students[0], status=Status.ABSENT
            )


def test_students_not_enrolled_are_ignored(client_teacher, sessions, other_teacher):
    """A student id that is not on the course cannot be smuggled in."""
    session = sessions[0]
    save(client_teacher, session, [{"student": other_teacher.pk, "status": "PRESENT"}])

    assert AttendanceRecord.objects.count() == 0


def test_invalid_status_is_ignored(client_teacher, sessions, students):
    save(client_teacher, sessions[0], [{"student": students[0].pk, "status": "NOPE"}])

    assert AttendanceRecord.objects.count() == 0


def test_marking_absent_notifies_the_student(client_teacher, sessions, students):
    save(client_teacher, sessions[0], [{"student": students[0].pk, "status": "ABSENT"}])

    messages = [
        n.message.lower()
        for n in Notification.objects.filter(recipient=students[0])
    ]
    assert any("marked absent" in message for message in messages)


def test_malformed_body_is_rejected(client_teacher, sessions):
    response = client_teacher.post(
        reverse("attendance:register_save", kwargs={"session_pk": sessions[0].pk}),
        data="not json",
        content_type="application/json",
    )
    assert response.status_code == 400
