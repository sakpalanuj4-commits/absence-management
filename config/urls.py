from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="accounts:dashboard"), name="home"),
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("academics/", include("academics.urls")),
    path("attendance/", include("attendance.urls")),
    path("reports/", include("reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "config.errors.permission_denied"
handler404 = "config.errors.page_not_found"
