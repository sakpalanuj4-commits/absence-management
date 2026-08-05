from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("departments/", views.department_list, name="department_list"),
    path("departments/add/", views.department_form, name="department_create"),
    path("departments/<int:pk>/edit/", views.department_form, name="department_edit"),
    path("courses/", views.course_list, name="course_list"),
    path("courses/add/", views.course_form, name="course_create"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("courses/<int:pk>/edit/", views.course_form, name="course_edit"),
    path("courses/<int:course_pk>/enrol/", views.enrolment_add, name="enrolment_add"),
    path("enrolments/<int:pk>/remove/", views.enrolment_remove, name="enrolment_remove"),
]
