# Settings for the pytest suite: in-memory SQLite and fast password hashing.

import os

os.environ.setdefault("SECRET_KEY", "test-only-key")
os.environ["DB_ENGINE"] = "sqlite"

from .settings import *  # noqa: F401,F403,E402

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

DEBUG = False
