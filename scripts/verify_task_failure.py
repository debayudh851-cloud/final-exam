"""Queue an intentionally malformed, synthetic batch to verify real Celery error reporting."""
import os
import sys
import time
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.core.files.base import ContentFile
from accounts.models import User
from recruitment.models import ApplicationBatch
from recruitment.tasks import process_upload

batch = ApplicationBatch.objects.create(uploaded_by=User.objects.get(username='hr'),
    source_file=ContentFile(b'not,the,required,columns\ninvalid,demo,test,data\n', name='deliberate_failure.csv'))
task = process_upload.delay(batch.pk)
batch.task_id = task.id
batch.save(update_fields=['task_id'])
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    batch.refresh_from_db()
    if batch.status == 'FAILED':
        break
    time.sleep(.2)
assert batch.status == 'FAILED' and batch.error and batch.accepted_count == 0
(root / 'evidence' / 'celery_failure.json').write_text(json.dumps({
    'check': 'Real Celery malformed-input failure', 'batch_id': batch.pk, 'status': batch.status,
    'error': batch.error, 'accepted_count': batch.accepted_count, 'passed': True}, indent=2), encoding='utf-8')
print(f'PASS real Celery failure: batch {batch.pk} is FAILED with a visible sanitized error.')
