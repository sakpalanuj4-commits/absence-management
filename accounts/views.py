import csv
import io
import secrets

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import (
    ChangePasswordForm,
    LoginForm,
    ProfileForm,
    ResetPasswordForm,
    ResetRequestForm,
    UserEditForm,
    UserForm,
)
from .models import Notification, Role, User
from .permissions import admin_required


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = ChangePasswordForm
    success_url = reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.must_change_password:
            User.objects.filter(pk=self.request.user.pk).update(
                must_change_password=False
            )
            self.request.user.must_change_password = False
        messages.success(self.request, "Your password has been updated.")
        return response


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    form_class = ResetRequestForm
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = ResetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


@login_required
def dashboard(request):
    if request.user.is_admin:
        return redirect("reports:admin_dashboard")
    if request.user.is_teacher:
        return redirect("reports:teacher_dashboard")
    return redirect("reports:student_dashboard")


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    page = Paginator(notifications, 25).get_page(request.GET.get("page"))
    return render(request, "accounts/notifications.html", {"page": page})


@login_required
@require_POST
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return redirect(notification.link or "accounts:notifications")


@login_required
@require_POST
def notification_read_all(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    messages.success(request, "All notifications marked as read.")
    return redirect("accounts:notifications")


@admin_required
def user_list(request):
    users = User.objects.all()
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if role:
        users = users.filter(role=role)
    page = Paginator(users, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/user_list.html",
        {"page": page, "q": query, "role": role, "roles": Role.choices},
    )


@admin_required
def user_create(request):
    form = UserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Account created for {user.display_name}.")
        return redirect("accounts:user_list")
    return render(
        request, "accounts/user_form.html", {"form": form, "title": "Add user"}
    )


@admin_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "User updated.")
        return redirect("accounts:user_list")
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "title": f"Edit {user.display_name}", "object": user},
    )


@admin_required
@require_POST
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
    else:
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        state = "activated" if user.is_active else "deactivated"
        messages.success(request, f"{user.display_name} {state}.")
    return redirect("accounts:user_list")


@admin_required
@require_POST
def user_reset_password(request, pk):
    user = get_object_or_404(User, pk=pk)
    temporary = secrets.token_urlsafe(9)
    user.set_password(temporary)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
    messages.success(
        request,
        f"Temporary password for {user.display_name}: {temporary}. "
        "They will be asked to change it at next login.",
    )
    return redirect("accounts:user_list")


USER_CSV_COLUMNS = ["username", "first_name", "last_name", "email", "role", "password"]


@admin_required
def user_import(request):
    results = None
    if request.method == "POST" and request.FILES.get("file"):
        results = import_users(request.FILES["file"])
        messages.success(
            request,
            f"{results['created']} users created, "
            f"{len(results['errors'])} rows rejected.",
        )
    return render(
        request,
        "accounts/user_import.html",
        {"results": results, "columns": USER_CSV_COLUMNS},
    )


def import_users(upload):
    text = io.TextIOWrapper(upload.file, encoding="utf-8-sig")
    reader = csv.DictReader(text)
    created, errors = 0, []
    valid_roles = {r for r, _ in Role.choices}

    for line, row in enumerate(reader, start=2):
        username = (row.get("username") or "").strip()
        role = (row.get("role") or "STUDENT").strip().upper()

        if not username:
            errors.append({"line": line, "row": row, "error": "username is required"})
            continue
        if role not in valid_roles:
            errors.append({"line": line, "row": row, "error": f"unknown role '{role}'"})
            continue
        if User.objects.filter(username=username).exists():
            errors.append(
                {"line": line, "row": row, "error": "username already exists"}
            )
            continue

        password = (row.get("password") or "").strip() or secrets.token_urlsafe(9)
        with transaction.atomic():
            user = User(
                username=username,
                first_name=(row.get("first_name") or "").strip(),
                last_name=(row.get("last_name") or "").strip(),
                email=(row.get("email") or "").strip(),
                role=role,
                must_change_password=True,
            )
            user.set_password(password)
            user.save()
        created += 1

    return {"created": created, "errors": errors}
