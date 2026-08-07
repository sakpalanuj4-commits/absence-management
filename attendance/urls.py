from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("registers/", views.register_list, name="register_list"),
    path("session/<int:session_pk>/", views.register, name="register"),
]
