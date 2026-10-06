import logging
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from .models import ApplicationBatch, InterviewSlot, Candidate
from .tasks import process_upload
from ingestion.service import process_batch
from screening.services import invalidate_role_cache

logger = logging.getLogger('portal.audit')


def submit_upload(user, file, row_count, background=False):
    batch = ApplicationBatch.objects.create(uploaded_by=user, source_file=file, total_rows=row_count)
    try:
        if background or row_count >= settings.ASYNC_UPLOAD_THRESHOLD:
            task = process_upload.delay(batch.pk)
            batch.task_id = task.id
            batch.save(update_fields=['task_id'])
        else:
            process_batch(batch.pk)
    except Exception:
        logger.exception('Could not submit/process batch %s', batch.pk)
        ApplicationBatch.objects.filter(pk=batch.pk).update(status='FAILED', error='Upload could not complete. Check Redis, the Celery worker, and the server logs.')
    batch.refresh_from_db()
    return batch


def assign_slot(candidate, slot_id):
    with transaction.atomic():
        candidate = Candidate.objects.select_for_update().get(pk=candidate.pk)
        slot = InterviewSlot.objects.select_for_update().get(pk=slot_id)
        if slot.candidate_id or slot.role_id != candidate.applied_role_id or slot.starts_at <= timezone.now():
            raise ValueError('This slot is unavailable, past, or belongs to another role.')
        if InterviewSlot.objects.filter(candidate=candidate, ends_at__gt=timezone.now()).exists():
            raise ValueError('Candidate already has an upcoming interview.')
        slot.candidate = candidate
        slot.save(update_fields=['candidate'])
        Candidate.objects.filter(pk=candidate.pk).update(status='INTERVIEW')
        transaction.on_commit(lambda: invalidate_role_cache(candidate.applied_role_id))
    return slot


def save_feedback(serializer, user):
    with transaction.atomic():
        feedback = serializer.save(submitted_by=user)
        candidate = feedback.slot.candidate
        Candidate.objects.filter(pk=candidate.pk).update(status=feedback.recommendation)
        transaction.on_commit(lambda: invalidate_role_cache(candidate.applied_role_id))
    return feedback
