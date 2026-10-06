from django import forms
from django.db import transaction
from django.utils import timezone
from .models import Candidate, InterviewSlot, InterviewFeedback
from ingestion.validators import CandidateValidator, RowValidationError
from ingestion.service import read_upload
from .models import JobRole


class RoleReportFilterForm(forms.Form):
    min_candidates = forms.IntegerField(label='Minimum applications per role', min_value=1, max_value=50000, required=False)

    def clean_min_candidates(self):
        value = self.cleaned_data.get('min_candidates')
        return 1 if value is None else value


class UploadForm(forms.Form):
    file = forms.FileField(help_text='UTF-8 CSV or .xlsx; maximum 20 MB.')
    background = forms.BooleanField(required=False, label='Queue with Celery (recommended for large uploads)')

    def clean_file(self):
        file = self.cleaned_data['file']
        try:
            self.frame = read_upload(file)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return file


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['candidate_name', 'email', 'phone', 'college', 'applied_role', 'skills', 'experience_months',
                  'notice_period_days', 'expected_salary', 'resume_text', 'portfolio_url', 'historical_selection_status',
                  'resume_file', 'image']
        widgets = {'resume_text': forms.Textarea(attrs={'rows': 5}), 'skills': forms.TextInput()}

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        row = {**data, 'applied_role': data['applied_role'].name}
        role = data['applied_role']
        try:
            normalized = CandidateValidator().validate(row, {role.name.casefold(): role})
        except RowValidationError as exc:
            raise forms.ValidationError(exc.errors) from exc
        data.update(normalized)
        if Candidate.objects.filter(email=data['email']).exclude(pk=self.instance.pk).exists():
            self.add_error('email', 'Email already registered.')
        for field in ('resume_file', 'image'):
            file = data.get(field)
            if file and getattr(file, 'size', 0) > 5 * 1024 * 1024:
                self.add_error(field, 'Maximum size is 5 MB.')
        return data


class ScreeningStatusForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['status']


class AssignSlotForm(forms.Form):
    slot = forms.ModelChoiceField(queryset=InterviewSlot.objects.none())

    def __init__(self, *args, candidate, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slot'].queryset = InterviewSlot.objects.filter(role=candidate.applied_role, candidate__isnull=True, starts_at__gt=timezone.now())


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = InterviewFeedback
        fields = ['rating', 'comments', 'recommendation']
