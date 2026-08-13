from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrator"
    TEACHER = "TEACHER", "Teacher"
    STUDENT = "STUDENT", "Student"


class User(AbstractUser):
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    must_change_password = models.BooleanField(default=False)
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["last_name", "first_name", "username"]

    def __str__(self):
        full_name = self.get_full_name()
        return f"{full_name} ({self.username})" if full_name else self.username

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    @property
    def is_teacher(self):
        return self.role == Role.TEACHER

    @property
    def is_student(self):
        return self.role == Role.STUDENT

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        parts = [p for p in (self.first_name, self.last_name) if p]
        if parts:
            return "".join(p[0] for p in parts).upper()
        return self.username[:2].upper()

    @property
    def role_name(self):
        return dict(Role.choices).get(self.role, self.role)


class Notification(models.Model):
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.recipient.username}: {self.message[:50]}"


class AppSetting(models.Model):
    """Key/value settings the administrator can edit."""

    ATTENDANCE_THRESHOLD = "attendance_threshold"

    key = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get(cls, key, default=None):
        row = cls.objects.filter(key=key).first()
        return row.value if row else default

    @classmethod
    def set(cls, key, value):
        cls.objects.update_or_create(key=key, defaults={"value": str(value)})

    @classmethod
    def attendance_threshold(cls):
        raw = cls.get(cls.ATTENDANCE_THRESHOLD)
        if raw is None:
            return settings.ATTENDANCE_THRESHOLD_DEFAULT
        try:
            return int(raw)
        except (TypeError, ValueError):
            return settings.ATTENDANCE_THRESHOLD_DEFAULT
