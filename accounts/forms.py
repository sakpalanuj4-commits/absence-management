from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)

from .models import User

INPUT = (
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm "
    "text-slate-900 placeholder-slate-400 focus:border-indigo-500 "
    "focus:outline-none focus:ring-2 focus:ring-indigo-200"
)


def style(fields, css=INPUT):
    for field in fields.values():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.FileInput)):
            continue
        existing = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{existing} {css}".strip()


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self.fields)


class LoginForm(StyledFormMixin, AuthenticationForm):
    pass


class ChangePasswordForm(StyledFormMixin, PasswordChangeForm):
    pass


class ResetPasswordForm(StyledFormMixin, SetPasswordForm):
    pass


class ResetRequestForm(StyledFormMixin, PasswordResetForm):
    pass


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]
