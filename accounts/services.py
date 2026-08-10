from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def notify(user, message, link="", email=False, subject=None):
    notification = Notification.objects.create(
        recipient=user, message=message, link=link
    )
    if email and user.email:
        send_mail(
            subject or "Absence Management System",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
    return notification


def unread_count(user):
    if not user.is_authenticated:
        return 0
    return Notification.objects.filter(recipient=user, is_read=False).count()
