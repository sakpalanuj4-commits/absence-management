import json
from datetime import time

import pytest
from django.urls import reverse

from academics.models import ClassSession
from attendance.models import AbsenceRequest, AttendanceRecord, Status
from tests.conftest import TERM_START

pytestmark = pytest.mark.django_db


STUDENT_FORBIDDEN = [
    "/accounts/users/",
    "/accounts/users/add/",
    "/accounts/settings/",
    "/academics/departments/",
    "/attendance/registers/",
    "/reports/dashboard/admin/",
    "/reports/dashboard/teacher/",
]

TEACHER_FORBIDDEN = [
    "/accounts/users/",
    "/accounts/settings/",
    "/academics/departments/",
    "/reports/dashboard/admin/",
    "/reports/dashboard/student/",
]


@pytest.mark.parametrize("path", STUDENT_FORBIDDEN)
def test_student_cannot_reach_staff_pages(client_student, path):
    assert client_student.get(path).status_code == 403


@pytest.mark.parametrize("path", TEACHER_FORBIDDEN)
def test_teacher_cannot_reach_admin_pages(client_teacher, path):
    assert client_teacher.get(path).status_code == 403


def test_anonymous_visitor_is_sent_to_login(client):
    response = client.get("/reports/dashboard/admin/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_teacher_cannot_open_another_teachers_course(client_teacher, other_course):
    path = reverse("academics:course_detail", kwargs={"pk": other_course.pk})
    assert client_teacher.get(path).status_code == 403


def test_teacher_cannot_mark_another_teachers_register(
    client_teacher, other_course, other_teacher
):
    session = ClassSession.objects.create(
        course=other_course,
        date=TERM_START,
        start_time=time(9, 0),
        end_time=time(11, 0),
    )
    path = reverse("attendance:register", kwargs={"session_pk": session.pk})
    assert client_teacher.get(path).status_code == 403


def test_teacher_register_save_is_rejected_for_another_teachers_course(
    client_teacher, other_course, students
):
    session = ClassSession.objects.create(
        course=other_course,
        date=TERM_START,
        start_time=time(9, 0),
        end_time=time(11, 0),
    )
    response = client_teacher.post(
        reverse("attendance:register_save", kwargs={"session_pk": session.pk}),
        data=json.dumps({"records": [{"student": students[0].pk, "status": "ABSENT"}]}),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert AttendanceRecord.objects.count() == 0


def test_student_sees_only_their_own_records(
    client_student, marked_sessions, students, teacher, course
):
    other = students[1]
    AttendanceRecord.objects.create(
        session=marked_sessions[0],
        student=other,
        status=Status.ABSENT,
        marked_by=teacher,
    )

    response = client_student.get("/reports/attendance/")
    body = response.content.decode()

    assert students[0].display_name in body
    assert other.display_name not in body


def test_student_cannot_view_another_students_absence_request(
    client_student, students, course
):
    absence = AbsenceRequest.objects.create(
        student=students[1],
        course=course,
        start_date=TERM_START,
        end_date=TERM_START,
        reason="Private",
    )
    path = reverse("attendance:request_detail", kwargs={"pk": absence.pk})
    assert client_student.get(path).status_code == 403


def test_forced_password_change_blocks_the_rest_of_the_app(client, students):
    student = students[0]
    student.must_change_password = True
    student.save()
    client.force_login(student)

    response = client.get("/attendance/my-attendance/")

    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:password_change")
