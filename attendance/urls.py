from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("registers/", views.register_list, name="register_list"),
    path("session/<int:session_pk>/", views.register, name="register"),
    path("session/<int:session_pk>/save/", views.register_save, name="register_save"),
    path("my-attendance/", views.my_attendance, name="my_attendance"),
    path("requests/", views.request_list, name="request_list"),
    path("requests/new/", views.request_create, name="request_create"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/<int:pk>/review/", views.request_review, name="request_review"),
    path(
        "requests/<int:pk>/withdraw/",
        views.request_withdraw,
        name="request_withdraw",
    ),
    path(
        "courses/<int:course_pk>/attendance/",
        views.course_attendance,
        name="course_attendance",
    ),
]
