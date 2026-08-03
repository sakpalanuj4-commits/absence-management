# The Jinja2 backend has no context processors, so the things every template
# needs are registered here as globals.

from django.contrib import messages as django_messages
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from jinja2 import Environment


def percent(value, places=1):
    if value is None:
        return "-"
    return f"{value:.{places}f}%"


def environment(**options):
    options.setdefault("trim_blocks", True)
    options.setdefault("lstrip_blocks", True)
    env = Environment(**options)
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            "get_messages": django_messages.get_messages,
            "now": timezone.localtime,
            "today": timezone.localdate,
        }
    )
    env.filters["percent"] = percent
    return env
