from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Role, User


class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="courses"
    )
    credits = models.PositiveSmallIntegerField(default=10)
    term = models.CharField(max_length=30, blank=True)
    teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="courses_taught",
        limit_choices_to={"role": Role.TEACHER},
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def active_students(self):
        return User.objects.filter(
            enrolments__course=self, enrolments__is_active=True
        ).order_by("last_name", "first_name")


class Enrolment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrolments",
        limit_choices_to={"role": Role.STUDENT},
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="enrolments"
    )
    enrolled_on = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "course")
        ordering = ["course", "student"]

    def __str__(self):
        return f"{self.student} in {self.course.code}"


class ClassSession(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sessions")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        unique_together = ("course", "date", "start_time")
        ordering = ["-date", "start_time"]
        indexes = [models.Index(fields=["course", "date"])]

    def __str__(self):
        return f"{self.course.code} on {self.date} at {self.start_time:%H:%M}"

    @property
    def is_marked(self):
        return self.attendance_records.exists()
