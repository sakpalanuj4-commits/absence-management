from django.conf import settings
from django.db import models

from academics.models import ClassSession, Course
from accounts.models import Role


class Status(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"
    EXCUSED = "EXCUSED", "Excused"


# Statuses that count towards a student's attendance percentage.
COUNTS_AS_ATTENDED = [Status.PRESENT, Status.LATE, Status.EXCUSED]


class AttendanceRecord(models.Model):
    session = models.ForeignKey(
        ClassSession, on_delete=models.CASCADE, related_name="attendance_records"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        limit_choices_to={"role": Role.STUDENT},
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PRESENT
    )
    remark = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="marked_records",
    )
    marked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("session", "student")
        ordering = ["-session__date", "student"]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["session", "status"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.session} - {self.get_status_display()}"


class RequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class Category(models.TextChoices):
    MEDICAL = "MEDICAL", "Medical"
    PERSONAL = "PERSONAL", "Personal"
    AUTHORISED = "AUTHORISED", "University authorised"
    OTHER = "OTHER", "Other"


class AbsenceRequest(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="absence_requests",
        limit_choices_to={"role": Role.STUDENT},
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="absence_requests"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    category = models.CharField(
        max_length=12, choices=Category.choices, default=Category.PERSONAL
    )
    reason = models.TextField()
    document = models.FileField(upload_to="absence_documents/%Y/%m/", blank=True)
    status = models.CharField(
        max_length=10, choices=RequestStatus.choices, default=RequestStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_requests",
    )
    review_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "course"])]

    def __str__(self):
        return (
            f"{self.student} - {self.course.code} "
            f"({self.start_date} to {self.end_date})"
        )

    @property
    def is_pending(self):
        return self.status == RequestStatus.PENDING

    @property
    def day_count(self):
        return (self.end_date - self.start_date).days + 1
