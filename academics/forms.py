from datetime import timedelta

from django import forms

from accounts.forms import StyledFormMixin, style
from accounts.models import Role, User

from .models import ClassSession, Course, Department, Enrolment


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


class ClassSessionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ClassSession
        fields = ["date", "start_time", "end_time", "room", "is_cancelled"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }


WEEKDAYS = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]


class SessionGeneratorForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    weekdays = forms.MultipleChoiceField(
        choices=WEEKDAYS, widget=forms.CheckboxSelectMultiple
    )
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    room = forms.CharField(max_length=50, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self.fields)

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end:
            if end < start:
                raise forms.ValidationError("The end date is before the start date.")
            if (end - start) > timedelta(days=400):
                raise forms.ValidationError("Choose a range of at most one year.")
        if data.get("start_time") and data.get("end_time"):
            if data["end_time"] <= data["start_time"]:
                raise forms.ValidationError("The end time is before the start time.")
        return data

    def dates(self):
        wanted = {int(d) for d in self.cleaned_data["weekdays"]}
        day = self.cleaned_data["start_date"]
        end = self.cleaned_data["end_date"]
        while day <= end:
            if day.weekday() in wanted:
                yield day
            day += timedelta(days=1)
