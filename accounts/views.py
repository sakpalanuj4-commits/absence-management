from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import (
    ChangePasswordForm,
    LoginForm,
    ProfileForm,
    ResetPasswordForm,
    ResetRequestForm,
)
from .models import User


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
