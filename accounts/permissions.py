# Access is checked here, on the view. Hiding a link in a template is not enough:
# nothing stops someone typing the URL.

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import Role


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                raise PermissionDenied("Your role does not have access to this page.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


admin_required = role_required(Role.ADMIN)
teacher_required = role_required(Role.TEACHER)
student_required = role_required(Role.STUDENT)
staff_required = role_required(Role.ADMIN, Role.TEACHER)


def teacher_owns_course(user, course):
    if user.is_admin:
        return True
    return user.is_teacher and course.teachers.filter(pk=user.pk).exists()


def require_course_access(user, course):
    if not teacher_owns_course(user, course):
        raise PermissionDenied("You are not assigned to this course.")
