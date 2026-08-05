from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import Role, User

from .models import Course, Department, Enrolment


class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["code", "name"]


class CourseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "code",
            "name",
            "department",
            "credits",
            "term",
            "teachers",
            "is_active",
        ]
        widgets = {"teachers": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teachers"].queryset = User.objects.filter(
            role=Role.TEACHER, is_active=True
        )


class EnrolmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Enrolment
        fields = ["student"]

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course
        enrolled = Enrolment.objects.filter(course=course).values_list(
            "student_id", flat=True
        )
        self.fields["student"].queryset = User.objects.filter(
            role=Role.STUDENT, is_active=True
        ).exclude(pk__in=enrolled)

    def save(self, commit=True):
        enrolment = super().save(commit=False)
        enrolment.course = self.course
        if commit:
            enrolment.save()
        return enrolment
