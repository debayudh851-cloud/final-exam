from django.utils import timezone
from rest_framework import serializers
from .models import JobRole, Candidate, ApplicationBatch, ScreeningResult, InterviewSlot, InterviewFeedback
from ingestion.validators import CandidateValidator, RowValidationError


class JobRoleSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = JobRole
        fields = ['url', 'id', 'name', 'code', 'required_skills', 'min_experience_months', 'max_notice_period_days', 'max_salary']
        extra_kwargs = {'url': {'view_name': 'role-detail'}}


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ['id', 'candidate_name', 'email', 'phone', 'college', 'applied_role', 'batch', 'skills',
                  'experience_months', 'notice_period_days', 'expected_salary', 'resume_text', 'portfolio_url',
                  'historical_selection_status', 'status', 'created_at', 'updated_at']
        read_only_fields = ['batch', 'created_at', 'updated_at']

    def validate(self, attrs):
        row = {field: getattr(self.instance, field, '') if self.instance else '' for field in [
            'candidate_name', 'email', 'phone', 'college', 'applied_role', 'skills', 'experience_months',
            'notice_period_days', 'expected_salary', 'resume_text', 'portfolio_url', 'historical_selection_status']}
        row.update(attrs)
        role = row.get('applied_role')
        if not isinstance(role, JobRole):
            raise serializers.ValidationError({'applied_role': 'Select an existing job role.'})
        row['applied_role'] = role.name
        try:
            clean = CandidateValidator().validate(row, {role.name.casefold(): role})
        except RowValidationError as exc:
            raise serializers.ValidationError({'rows': exc.errors}) from exc
        if Candidate.objects.filter(email=clean['email']).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError({'email': 'Email already registered.'})
        return {**attrs, **clean}


class BatchSerializer(serializers.ModelSerializer):
    exports = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationBatch
        fields = ['id', 'status', 'total_rows', 'processed_rows', 'accepted_count', 'rejected_count', 'error', 'task_id', 'exports', 'created_at']

    def get_exports(self, batch) -> dict:
        request = self.context['request']
        return {kind: request.build_absolute_uri(f'/api/batches/{batch.id}/download/{kind}/')
                for kind in ('accepted', 'rejected') if getattr(batch, f'{kind}_file')}


class ScreeningSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningResult
        fields = '__all__'


class SlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewSlot
        fields = ['id', 'role', 'candidate', 'interviewer', 'starts_at', 'ends_at', 'location']

    def validate(self, attrs):
        if attrs['ends_at'] <= attrs['starts_at'] or attrs['starts_at'] <= timezone.now():
            raise serializers.ValidationError('Choose a future slot with an end after its start.')
        interviewer = attrs['interviewer']
        if not interviewer.verified or (interviewer.role != 'INTERVIEWER' and not interviewer.is_portal_admin):
            raise serializers.ValidationError('Assign a verified interviewer or admin.')
        if attrs.get('candidate') and attrs['candidate'].applied_role_id != attrs['role'].pk:
            raise serializers.ValidationError('Candidate and slot roles must match.')
        if InterviewSlot.objects.filter(interviewer=interviewer, starts_at__lt=attrs['ends_at'], ends_at__gt=attrs['starts_at']).exists():
            raise serializers.ValidationError('Interviewer has an overlapping slot.')
        return attrs


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewFeedback
        fields = ['id', 'slot', 'rating', 'comments', 'recommendation', 'submitted_by', 'created_at']
        read_only_fields = ['submitted_by', 'created_at']

    def validate_slot(self, slot):
        user = self.context['request'].user
        if not user.is_portal_admin and slot.interviewer_id != user.pk:
            raise serializers.ValidationError('You can only submit feedback for assigned slots.')
        if not slot.candidate_id:
            raise serializers.ValidationError('A candidate must be assigned first.')
        return slot


class PredictSerializer(serializers.Serializer):
    experience_months = serializers.IntegerField(min_value=0, max_value=600)
    notice_period_days = serializers.IntegerField(min_value=0, max_value=365)
    expected_salary = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    skills = serializers.CharField(max_length=2000)
    applied_role = serializers.CharField(max_length=100)

    def validate_applied_role(self, value):
        role = JobRole.objects.filter(name__iexact=value).first()
        if not role:
            raise serializers.ValidationError('Unknown job role name.')
        return role.name


class NLPSerializer(serializers.Serializer):
    resume_text = serializers.CharField(allow_blank=True, max_length=30000)
    role = serializers.PrimaryKeyRelatedField(queryset=JobRole.objects.all())


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    background = serializers.BooleanField(default=False)
