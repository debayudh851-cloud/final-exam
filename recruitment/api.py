from django.db import transaction
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from rest_framework import viewsets, generics, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from accounts.permissions import IsManager, IsVerified
from .models import JobRole, Candidate, ApplicationBatch, ScreeningResult, InterviewSlot, InterviewFeedback
from .serializers import (JobRoleSerializer, CandidateSerializer, BatchSerializer, ScreeningSerializer,
                         SlotSerializer, FeedbackSerializer, PredictSerializer, NLPSerializer, UploadSerializer)
from .services import submit_upload, assign_slot, save_feedback
from ingestion.service import read_upload
from screening.ml import predict, ModelUnavailable
from screening.nlp import analyze_resume, NLPResourcesMissing
from screening.services import screen_candidate, invalidate_role_cache


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobRole.objects.all().order_by('name')
    serializer_class = JobRoleSerializer


class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.select_related('applied_role').all()
    serializer_class = CandidateSerializer
    permission_classes = [IsManager]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('role'):
            queryset = queryset.filter(applied_role_id=self.request.query_params['role'])
        if self.request.query_params.get('status'):
            queryset = queryset.filter(status=self.request.query_params['status'])
        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            candidate = serializer.save()
            screen_candidate(candidate)

    def perform_update(self, serializer):
        old_role = serializer.instance.applied_role_id
        with transaction.atomic():
            candidate = serializer.save()
            screen_candidate(candidate)
            transaction.on_commit(lambda: invalidate_role_cache(old_role))

    def perform_destroy(self, instance):
        role_id = instance.applied_role_id
        instance.delete()
        invalidate_role_cache(role_id)


class BatchStatusAPI(generics.RetrieveAPIView):
    queryset = ApplicationBatch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [IsManager]


class BatchUploadAPI(APIView):
    permission_classes = [IsManager]
    serializer_class = UploadSerializer

    @extend_schema(request=UploadSerializer, responses={201: BatchSerializer, 202: BatchSerializer, 400: dict, 503: dict})
    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            frame = read_upload(serializer.validated_data['file'])
        except ValueError as exc:
            raise serializers.ValidationError({'file': str(exc)}) from exc
        batch = submit_upload(request.user, serializer.validated_data['file'], len(frame), serializer.validated_data['background'])
        code = 503 if batch.status == 'FAILED' else (202 if batch.status == 'QUEUED' else 201)
        return Response(BatchSerializer(batch, context={'request': request}).data, status=code)


class BatchDownloadAPI(APIView):
    permission_classes = [IsManager]

    @extend_schema(responses={200: bytes, 404: dict})
    def get(self, request, pk, kind):
        batch = get_object_or_404(ApplicationBatch, pk=pk)
        if kind not in ('accepted', 'rejected') or not getattr(batch, f'{kind}_file', None):
            return Response({'detail': 'Export unavailable.'}, status=404)
        return FileResponse(getattr(batch, f'{kind}_file').open('rb'), as_attachment=True, filename=f'{kind}_rows.csv')


class ScreeningListAPI(generics.ListAPIView):
    queryset = ScreeningResult.objects.select_related('candidate').all().order_by('-updated_at')
    serializer_class = ScreeningSerializer
    permission_classes = [IsManager]


class SlotViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SlotSerializer
    queryset = InterviewSlot.objects.select_related('role', 'candidate', 'interviewer').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if self.request.user.can_manage_candidates else queryset.filter(interviewer=self.request.user)


class SlotCreateAPI(generics.CreateAPIView):
    queryset = InterviewSlot.objects.all()
    serializer_class = SlotSerializer
    permission_classes = [IsManager]


class AssignSerializer(serializers.Serializer):
    candidate = serializers.PrimaryKeyRelatedField(queryset=Candidate.objects.all())
    slot = serializers.PrimaryKeyRelatedField(queryset=InterviewSlot.objects.all())


class AssignAPI(APIView):
    permission_classes = [IsManager]
    serializer_class = AssignSerializer

    @extend_schema(request=AssignSerializer, responses={200: dict, 400: dict})
    def post(self, request):
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assign_slot(serializer.validated_data['candidate'], serializer.validated_data['slot'].pk)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response({'detail': 'Interview assigned.'})


class FeedbackAPI(generics.ListCreateAPIView):
    queryset = InterviewFeedback.objects.select_related('slot').all().order_by('-created_at')
    serializer_class = FeedbackSerializer

    def get_queryset(self):
        query = super().get_queryset()
        return query if self.request.user.is_portal_admin else query.filter(submitted_by=self.request.user)

    def perform_create(self, serializer):
        if not self.request.user.is_portal_admin and self.request.user.role != 'INTERVIEWER':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Interviewer or Admin access required.')
        save_feedback(serializer, self.request.user)


class PredictAPI(APIView):
    permission_classes = [IsManager]
    serializer_class = PredictSerializer

    @extend_schema(request=PredictSerializer, responses={200: dict, 503: dict})
    def post(self, request):
        serializer = PredictSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(predict(serializer.validated_data))
        except ModelUnavailable as exc:
            return Response({'detail': str(exc)}, status=503)


class NLPAPI(APIView):
    permission_classes = [IsManager]
    serializer_class = NLPSerializer

    @extend_schema(request=NLPSerializer, responses={200: dict, 503: dict})
    def post(self, request):
        serializer = NLPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(analyze_resume(serializer.validated_data['resume_text'], serializer.validated_data['role'].required_skills))
        except NLPResourcesMissing as exc:
            return Response({'detail': str(exc)}, status=503)
