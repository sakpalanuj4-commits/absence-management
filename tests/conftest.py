from datetime import date, time, timedelta

import pytest

from academics.models import ClassSession, Course, Department, Enrolment
from accounts.models import Role, User
from attendance.models import AttendanceRecord, Status

PASSWORD = "test-password-123"

TERM_START = date(2026, 3, 2)  # a Monday


def make_user(username, role, **extra):
    return User.objects.create_user(
        username=username,
        password=PASSWORD,
        email=f"{username}@example.ac.uk",
        role=role,
        **extra,
    )


@pytest.fixture
def admin_user(db):
    return make_user("admin1", Role.ADMIN, first_name="Ada", last_name="Admin")


@pytest.fixture
def teacher(db):
    return make_user("teach1", Role.TEACHER, first_name="Tom", last_name="Teacher")


@pytest.fixture
def other_teacher(db):
    return make_user("teach2", Role.TEACHER, first_name="Tina", last_name="Other")


@pytest.fixture
def students(db):
    return [
        make_user(f"stud{i}", Role.STUDENT, first_name=f"S{i}", last_name="Student")
        for i in range(1, 4)
    ]


@pytest.fixture
def department(db):
    return Department.objects.create(code="CS", name="Computing")


@pytest.fixture
def course(department, teacher, students):
    course = Course.objects.create(
        code="CS101", name="Intro to Computing", department=department, credits=20
    )
    course.teachers.add(teacher)
    for student in students:
        Enrolment.objects.create(student=student, course=course)
    return course


@pytest.fixture
def other_course(department, other_teacher, students):
    course = Course.objects.create(
        code="CS202", name="Networks", department=department, credits=20
    )
    course.teachers.add(other_teacher)
    Enrolment.objects.create(student=students[0], course=course)
    return course


@pytest.fixture
def sessions(course):
    """Four weekly sessions; the third one is cancelled."""
    created = []
    for week in range(4):
        created.append(
            ClassSession.objects.create(
                course=course,
                date=TERM_START + timedelta(weeks=week),
                start_time=time(9, 0),
                end_time=time(11, 0),
                room="E01",
                is_cancelled=(week == 2),
            )
        )
    return created


@pytest.fixture
def marked_sessions(sessions, students, teacher):
    """Student 1: present, present, (cancelled), absent."""
    live = [s for s in sessions if not s.is_cancelled]
    statuses = [Status.PRESENT, Status.PRESENT, Status.ABSENT]
    for session, status in zip(live, statuses):
        AttendanceRecord.objects.create(
            session=session, student=students[0], status=status, marked_by=teacher
        )
    # A record on the cancelled session, which must never count.
    cancelled = next(s for s in sessions if s.is_cancelled)
    AttendanceRecord.objects.create(
        session=cancelled, student=students[0], status=Status.ABSENT, marked_by=teacher
    )
    return sessions


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def client_teacher(client, teacher):
    client.force_login(teacher)
    return client


@pytest.fixture
def client_student(client, students):
    client.force_login(students[0])
    return client
