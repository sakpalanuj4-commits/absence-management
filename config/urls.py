from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="accounts:dashboard"), name="home"),
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
]

handler403 = "config.errors.permission_denied"
handler404 = "config.errors.page_not_found"
