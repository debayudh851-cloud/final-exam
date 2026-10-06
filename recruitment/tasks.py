from celery import shared_task
from ingestion.service import process_batch


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True)
def process_upload(self, batch_id):
    return process_batch(batch_id)
