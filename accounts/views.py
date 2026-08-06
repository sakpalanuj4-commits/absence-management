import secrets

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
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
from .models import Role, User
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
    # The real per-role dashboards arrive with the reports app.
    return render(request, "accounts/dashboard.html", {"page_id": "dashboard"})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


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
