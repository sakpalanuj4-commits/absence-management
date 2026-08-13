from datetime import time, timedelta

import pytest

from academics.models import ClassSession
from accounts.models import AppSetting
from attendance.models import AttendanceRecord, Status
from reports import services

pytestmark = pytest.mark.django_db


def test_percentage_ignores_cancelled_sessions(marked_sessions, students, course):
    """Student 1 has present, present, absent on live sessions, plus an absent
    record on a cancelled session that must not count."""
    summary = services.student_course_summary(students[0], course)

    assert summary["total"] == 3
    assert summary["attended"] == 2
    assert summary["absent"] == 1
    assert summary["percentage"] == pytest.approx(66.7)


def test_late_and_excused_count_as_attended(sessions, students, teacher, course):
    live = [s for s in sessions if not s.is_cancelled]
    for session, status in zip(live, [Status.PRESENT, Status.LATE, Status.EXCUSED]):
        AttendanceRecord.objects.create(
            session=session, student=students[1], status=status, marked_by=teacher
        )

    summary = services.student_course_summary(students[1], course)

    assert summary["total"] == 3
    assert summary["attended"] == 3
    assert summary["percentage"] == 100.0


def test_percentage_is_none_when_nothing_recorded(students, course):
    summary = services.student_course_summary(students[2], course)

    assert summary["total"] == 0
    assert summary["percentage"] is None


def test_unmarked_sessions_do_not_drag_the_percentage_down(
    marked_sessions, students, course, sessions
):
    """A register that has not been taken is not an absence."""
    ClassSession.objects.create(
        course=course,
        date=sessions[-1].date + timedelta(weeks=1),
        start_time=time(9, 0),
        end_time=time(11, 0),
    )

    summary = services.student_course_summary(students[0], course)

    assert summary["total"] == 3
    assert summary["percentage"] == pytest.approx(66.7)


def test_below_threshold_flag_uses_the_configured_value(
    marked_sessions, students, course
):
    AppSetting.set(AppSetting.ATTENDANCE_THRESHOLD, 75)
    rows = {row["course"].pk: row for row in services.student_course_rows(students[0])}
    assert rows[course.pk]["below_threshold"] is True

    AppSetting.set(AppSetting.ATTENDANCE_THRESHOLD, 50)
    rows = {row["course"].pk: row for row in services.student_course_rows(students[0])}
    assert rows[course.pk]["below_threshold"] is False


def test_course_summary_aggregates_every_student(
    marked_sessions, students, teacher, course, sessions
):
    live = [s for s in sessions if not s.is_cancelled]
    for session in live:
        AttendanceRecord.objects.create(
            session=session,
            student=students[1],
            status=Status.PRESENT,
            marked_by=teacher,
        )

    summary = services.course_summary(course)

    assert summary["total"] == 6
    assert summary["attended"] == 5
    assert summary["percentage"] == pytest.approx(83.3)
