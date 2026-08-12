from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path("dashboard/student/", views.student_dashboard, name="student_dashboard"),
    path("attendance/", views.attendance_report, name="attendance_report"),
    path("course/<int:course_pk>/", views.course_report, name="course_report"),
    path(
        "chart/attendance-trend/",
        views.chart_attendance_trend,
        name="chart_attendance_trend",
    ),
    path(
        "chart/status-distribution/",
        views.chart_status_distribution,
        name="chart_status_distribution",
    ),
    path(
        "chart/course-comparison/",
        views.chart_course_comparison,
        name="chart_course_comparison",
    ),
]
