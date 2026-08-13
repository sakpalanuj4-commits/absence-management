# Walks every page as each role against the seeded development database and
# reports the status codes. Not part of the pytest suite:
#   venv/bin/python tests/smoke_check.py

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402

from academics.models import ClassSession, Course, Department  # noqa: E402
from accounts.models import User  # noqa: E402
from attendance.models import AbsenceRequest  # noqa: E402


def pages():
    course = Course.objects.first()
    session = ClassSession.objects.filter(is_cancelled=False).first()
    department = Department.objects.first()
    absence = AbsenceRequest.objects.first()
    student = User.objects.filter(role="STUDENT").first()

    common = [
        ("/accounts/dashboard/", (302,)),
        ("/accounts/profile/", (200,)),
        ("/accounts/notifications/", (200,)),
        ("/accounts/password/change/", (200,)),
        ("/reports/attendance/", (200,)),
        ("/reports/chart/attendance-trend/", (200,)),
        ("/reports/chart/status-distribution/", (200,)),
        ("/reports/chart/course-comparison/", (200,)),
        ("/reports/export/csv/", (200,)),
        ("/attendance/requests/", (200,)),
    ]

    admin_pages = common + [
        ("/reports/dashboard/admin/", (200,)),
        ("/accounts/users/", (200,)),
        ("/accounts/users/add/", (200,)),
        ("/accounts/users/import/", (200,)),
        ("/accounts/settings/", (200,)),
        ("/academics/departments/", (200,)),
        ("/academics/departments/add/", (200,)),
        (f"/academics/departments/{department.pk}/edit/", (200,)),
        ("/academics/courses/", (200,)),
        ("/academics/courses/add/", (200,)),
        (f"/academics/courses/{course.pk}/", (200,)),
        (f"/academics/courses/{course.pk}/edit/", (200,)),
        (f"/academics/courses/{course.pk}/sessions/", (200,)),
        (f"/academics/courses/{course.pk}/sessions/add/", (200,)),
        (f"/academics/courses/{course.pk}/sessions/generate/", (200,)),
        ("/academics/enrolments/import/", (200,)),
        ("/academics/students/search/?q=a", (200,)),
        ("/attendance/registers/", (200,)),
        (f"/attendance/session/{session.pk}/", (200,)),
        (f"/attendance/courses/{course.pk}/attendance/", (200,)),
        (f"/reports/course/{course.pk}/", (200,)),
        (f"/attendance/requests/{absence.pk}/", (200,)),
        (f"/reports/export/pdf/?student={student.pk}", (200,)),
    ]

    teacher_pages = common + [
        ("/reports/dashboard/teacher/", (200,)),
        ("/academics/courses/", (200,)),
        ("/attendance/registers/", (200,)),
        ("/accounts/users/", (403,)),
        ("/academics/departments/", (403,)),
        ("/accounts/settings/", (403,)),
    ]

    student_pages = common + [
        ("/reports/dashboard/student/", (200,)),
        ("/attendance/my-attendance/", (200,)),
        ("/attendance/requests/new/", (200,)),
        ("/accounts/users/", (403,)),
        ("/attendance/registers/", (403,)),
        ("/reports/dashboard/admin/", (403,)),
    ]

    return {
        "admin": admin_pages,
        "teacher1": teacher_pages,
        "student001": student_pages,
    }


def main():
    setup_test_environment()  # lets the test client use the "testserver" host
    failures = 0
    checked = 0

    for username, urls in pages().items():
        client = Client()
        assert client.login(username=username, password="demo1234"), username
        print(f"\n=== {username} " + "=" * (60 - len(username)))
        for url, expected in urls:
            try:
                response = client.get(url)
                code = response.status_code
            except Exception as error:  # noqa: BLE001
                print(f"  ERROR {url}\n        {type(error).__name__}: {error}")
                failures += 1
                continue
            checked += 1
            ok = code in expected
            if not ok:
                failures += 1
            print(f"  {'ok  ' if ok else 'FAIL'} {code} {url}")

    print(f"\n{checked} pages checked, {failures} problems.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
