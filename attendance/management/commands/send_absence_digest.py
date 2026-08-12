# Daily digest of unexplained absences, meant to be run from cron:
#   0 18 * * * /path/to/venv/bin/python /path/to/manage.py send_absence_digest

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from accounts.services import notify
from attendance.models import AttendanceRecord, Status


class Command(BaseCommand):
    help = "Email administrators a digest of unexplained absences."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="How many days back to include (default: 1).",
        )

    def handle(self, *args, **options):
        since = timezone.localdate() - timedelta(days=options["days"])
        absences = (
            AttendanceRecord.objects.filter(
                status=Status.ABSENT,
                session__date__gte=since,
                session__is_cancelled=False,
            )
            .select_related("student", "session", "session__course")
            .order_by("session__date", "student__last_name")
        )

        if not absences:
            self.stdout.write("No unexplained absences to report.")
            return

        lines = [
            f"{record.session.date:%d %b} - {record.student.display_name} "
            f"({record.session.course.code})"
            for record in absences
        ]
        summary = f"{len(lines)} unexplained absences since {since:%d %b %Y}"
        body = summary + ":\n\n" + "\n".join(lines[:100])
        if len(lines) > 100:
            body += f"\n\n... and {len(lines) - 100} more."

        admins = User.objects.filter(role=Role.ADMIN, is_active=True)
        link = reverse("reports:attendance_report")
        recipients = [admin.email for admin in admins if admin.email]

        # The in-app message carries the headline, the email the full list.
        for admin in admins:
            notify(admin, summary, link=link)

        if recipients:
            send_mail(
                "Daily absence digest",
                body,
                settings.DEFAULT_FROM_EMAIL,
                recipients,
                fail_silently=True,
            )

        self.stdout.write(
            self.style.SUCCESS(f"{summary}, sent to {admins.count()} administrators.")
        )
