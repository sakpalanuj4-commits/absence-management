from django import forms

from academics.models import Course
from accounts.forms import StyledFormMixin

from .models import AbsenceRequest

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = (".pdf", ".png", ".jpg", ".jpeg")


class AbsenceRequestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AbsenceRequest
        fields = [
            "course",
            "start_date",
            "end_date",
            "category",
            "reason",
            "document",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.fields["course"].queryset = Course.objects.filter(
            enrolments__student=student, enrolments__is_active=True
        ).distinct()
        self.fields["document"].help_text = "Optional. PDF or image, up to 5 MB."

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "The end date is before the start date.")
        return data

    def clean_document(self):
        document = self.cleaned_data.get("document")
        if not document:
            return document
        if document.size > MAX_DOCUMENT_BYTES:
            raise forms.ValidationError("The file must be 5 MB or smaller.")
        if not document.name.lower().endswith(ALLOWED_DOCUMENT_TYPES):
            raise forms.ValidationError("Upload a PDF or an image file.")
        return document

    def save(self, commit=True):
        absence_request = super().save(commit=False)
        absence_request.student = self.student
        if commit:
            absence_request.save()
        return absence_request
