from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("registers/", views.register_list, name="register_list"),
    path("session/<int:session_pk>/", views.register, name="register"),
    path("session/<int:session_pk>/save/", views.register_save, name="register_save"),
    path("my-attendance/", views.my_attendance, name="my_attendance"),
    path("requests/new/", views.request_create, name="request_create"),
]
