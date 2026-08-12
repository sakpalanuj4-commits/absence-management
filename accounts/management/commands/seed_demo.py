# Demonstration data so every screen has something to show.
# Run with --reset to wipe what is already there. Password: demo1234.

import random
from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from academics.models import ClassSession, Course, Department, Enrolment
from accounts.models import AppSetting, Notification, Role, User
from attendance.models import (
    AbsenceRequest,
    AttendanceRecord,
    Category,
    RequestStatus,
    Status,
)
from attendance.services import approve_request

PASSWORD = "demo1234"

FIRST_NAMES = [
    "Aisha", "Liam", "Priya", "Noah", "Chloe", "Omar", "Ella", "Rahul", "Maya",
    "Tom", "Zara", "Ben", "Nadia", "Jack", "Leah", "Sam", "Iris", "Ravi",
    "Grace", "Adam", "Nina", "Josh", "Amara", "Felix", "Sofia", "Hugo",
    "Yasmin", "Owen", "Layla", "Ethan",
]
LAST_NAMES = [
    "Khan", "Smith", "Patel", "Brown", "Wilson", "Ahmed", "Taylor", "Sharma",
    "Evans", "Clark", "Ali", "Walker", "Hussain", "Roberts", "Morgan", "Shah",
    "Bennett", "Nair", "Hughes", "Baker",
]

DEPARTMENTS = [
    ("CS", "Computing and Mathematics"),
    ("BUS", "Business and Management"),
    ("ENG", "Engineering"),
]

COURSES = [
    ("6G7V0007", "MSc Computer Science Project", "CS", 60, [0, 2]),
    ("6G6Z1010", "Web Application Development", "CS", 20, [1, 3]),
    ("6G6Z1102", "Database Systems", "CS", 20, [0, 3]),
    ("6G6Z1150", "Software Engineering", "CS", 20, [2, 4]),
    ("6B7A2001", "Organisational Behaviour", "BUS", 20, [1, 4]),
    ("6B7A2010", "Marketing Analytics", "BUS", 20, [0, 2]),
    ("6E7C3001", "Control Systems", "ENG", 20, [3]),
    ("6E7C3020", "Thermodynamics", "ENG", 20, [1, 4]),
]


class Command(BaseCommand):
    help = "Create demonstration users, courses, sessions and attendance."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo data before seeding.",
        )
        parser.add_argument(
            "--students", type=int, default=60, help="How many students to create."
        )
        parser.add_argument(
            "--weeks", type=int, default=10, help="How many weeks of sessions."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)

        if options["reset"]:
            self.stdout.write("Removing existing demo data...")
            AttendanceRecord.objects.all().delete()
            AbsenceRequest.objects.all().delete()
            Notification.objects.all().delete()
            ClassSession.objects.all().delete()
            Enrolment.objects.all().delete()
            Course.objects.all().delete()
            Department.objects.all().delete()
            User.objects.exclude(is_superuser=True).delete()

        AppSetting.set(AppSetting.ATTENDANCE_THRESHOLD, 75)

        admin = self._admin()
        teachers = self._teachers()
        students = self._students(options["students"])
        departments = self._departments()
        courses = self._courses(departments, teachers)
        self._enrol(courses, students)
        sessions = self._sessions(courses, options["weeks"])
        self._attendance(sessions, teachers)
        self._requests(courses, students, teachers)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeeded {len(courses)} courses, {len(students)} students, "
                f"{len(sessions)} sessions, "
                f"{AttendanceRecord.objects.count()} attendance records.\n\n"
                f"  Administrator : {admin.username} / {PASSWORD}\n"
                f"  Teacher       : {teachers[0].username} / {PASSWORD}\n"
                f"  Student       : {students[0].username} / {PASSWORD}\n"
            )
        )

    def _make(self, username, first, last, role, email=None):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first,
                "last_name": last,
                "email": email or f"{username}@example.ac.uk",
                "role": role,
            },
        )
        if created:
            user.set_password(PASSWORD)
            if role == Role.ADMIN:
                user.is_staff = True
                user.is_superuser = True
            user.save()
        return user

    def _admin(self):
        return self._make("admin", "Alex", "Registrar", Role.ADMIN)

    def _teachers(self):
        names = [
            ("Yanlong", "Zhang"),
            ("Helen", "Marsh"),
            ("David", "Okoro"),
            ("Priya", "Menon"),
            ("Mark", "Ellis"),
        ]
        return [
            self._make(f"teacher{i + 1}", first, last, Role.TEACHER)
            for i, (first, last) in enumerate(names)
        ]

    def _students(self, count):
        students = []
        for i in range(count):
            first = FIRST_NAMES[i % len(FIRST_NAMES)]
            last = LAST_NAMES[(i * 7) % len(LAST_NAMES)]
            students.append(
                self._make(f"student{i + 1:03d}", first, last, Role.STUDENT)
            )
        return students

    def _departments(self):
        return {
            code: Department.objects.get_or_create(
                code=code, defaults={"name": name}
            )[0]
            for code, name in DEPARTMENTS
        }

    def _courses(self, departments, teachers):
        courses = []
        for code, name, dept, credits, teacher_indexes in COURSES:
            course, _ = Course.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "department": departments[dept],
                    "credits": credits,
                    "term": "2026/27 Semester 1",
                },
            )
            course.teachers.set([teachers[i] for i in teacher_indexes])
            courses.append(course)
        return courses

    def _enrol(self, courses, students):
        for student in students:
            for course in random.sample(courses, random.randint(2, 4)):
                Enrolment.objects.get_or_create(student=student, course=course)

    def _sessions(self, courses, weeks):
        """Weekly sessions, so there is both history and a couple to come."""
        today = timezone.localdate()
        start = today - timedelta(weeks=weeks)
        start -= timedelta(days=start.weekday())  # back to a Monday

        slots = [
            (0, time(9, 0), time(11, 0), "JD E01"),
            (2, time(13, 0), time(15, 0), "JD E02"),
            (4, time(10, 0), time(12, 0), "JD LT1"),
        ]

        sessions = []
        for index, course in enumerate(courses):
            weekday, begins, ends, room = slots[index % len(slots)]
            day = start + timedelta(days=weekday)
            while day <= today + timedelta(weeks=2):
                session, _ = ClassSession.objects.get_or_create(
                    course=course,
                    date=day,
                    start_time=begins,
                    defaults={"end_time": ends, "room": room},
                )
                sessions.append(session)
                day += timedelta(days=7)
        return sessions

    def _attendance(self, sessions, teachers):
        """Mark the past sessions, each student keeping a consistent habit."""
        today = timezone.localdate()
        habits = {}
        records = []

        for session in sessions:
            if session.date > today:
                continue
            marker = session.course.teachers.first() or teachers[0]
            for student in session.course.active_students():
                habit = habits.setdefault(student.pk, random.uniform(0.62, 0.99))
                roll = random.random()
                if roll < habit:
                    status = Status.PRESENT
                elif roll < habit + 0.06:
                    status = Status.LATE
                elif roll < habit + 0.10:
                    status = Status.EXCUSED
                else:
                    status = Status.ABSENT
                records.append(
                    AttendanceRecord(
                        session=session,
                        student=student,
                        status=status,
                        marked_by=marker,
                        remark="Arrived late" if status == Status.LATE else "",
                    )
                )

        AttendanceRecord.objects.bulk_create(records, ignore_conflicts=True)

    def _requests(self, courses, students, teachers):
        today = timezone.localdate()
        reasons = [
            ("Hospital appointment", Category.MEDICAL),
            ("Family emergency at home", Category.PERSONAL),
            ("Representing the university at a conference", Category.AUTHORISED),
            ("Unwell with flu for several days", Category.MEDICAL),
            ("Visa appointment", Category.PERSONAL),
        ]

        for i in range(12):
            student = random.choice(students)
            enrolment = Enrolment.objects.filter(student=student).first()
            if enrolment is None:
                continue
            reason, category = reasons[i % len(reasons)]
            start = today - timedelta(days=random.randint(3, 40))
            absence = AbsenceRequest.objects.create(
                student=student,
                course=enrolment.course,
                start_date=start,
                end_date=start + timedelta(days=random.choice([0, 1, 2])),
                category=category,
                reason=reason,
            )
            if i % 3 == 0:
                continue  # leave pending
            reviewer = absence.course.teachers.first() or teachers[0]
            if i % 3 == 1:
                approve_request(absence, reviewer, "Evidence accepted.")
            else:
                absence.status = RequestStatus.REJECTED
                absence.reviewed_by = reviewer
                absence.review_comment = "No supporting evidence provided."
                absence.reviewed_at = timezone.now()
                absence.save()
