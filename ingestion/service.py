import csv
import io
import logging
from functools import wraps
from pathlib import Path
from time import perf_counter
import pandas as pd
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.conf import settings
import psycopg
from recruitment.models import JobRole, Candidate, ApplicationBatch
from .validators import FIELDS, REQUIRED_COLUMNS, CandidateValidator, InputFileError, RowValidationError
from .processing import BatchCounts, iter_records, progress_counter, rejected_record

logger = logging.getLogger('portal.audit')


def timed(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        start = perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            logger.info('operation=%s duration_ms=%.2f', function.__name__, (perf_counter() - start) * 1000)
    return wrapper


def read_upload(file):
    suffix = Path(file.name).suffix.lower()
    if suffix not in ('.csv', '.xlsx'):
        raise InputFileError('Supported formats: UTF-8 CSV and .xlsx Excel.')
    if getattr(file, 'size', 0) > 20 * 1024 * 1024:
        raise InputFileError('Maximum upload size is 20 MB.')
    try:
        file.seek(0)
        frame = pd.read_csv(file, dtype=str, keep_default_na=False, encoding='utf-8-sig') if suffix == '.csv' else pd.read_excel(file, dtype=str, keep_default_na=False, engine='openpyxl')
    except Exception as exc:
        raise InputFileError('Cannot read file. Check its format, encoding, and content.') from exc
    finally:
        file.seek(0)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if len(set(frame.columns)) != len(frame.columns):
        raise InputFileError('Duplicate column names are not supported.')
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise InputFileError('Missing columns: ' + ', '.join(sorted(missing)))
    if frame.empty:
        raise InputFileError('The file contains no candidate rows.')
    if len(frame) > 50000:
        raise InputFileError('Maximum batch size is 50,000 rows.')
    return frame.fillna('')


def export_csv(rows, fields):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    # Prevent formula execution when an HR user opens exports in a spreadsheet.
    for row in rows:
        writer.writerow({k: "'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else v for k, v in row.items()})
    return ContentFile(output.getvalue().encode('utf-8-sig'))


def record_progress(batch_id, index):
    """Independent transaction makes progress visible while candidate inserts are atomic."""
    db = settings.DATABASES['default']
    with psycopg.connect(dbname=db['NAME'], user=db['USER'], password=db['PASSWORD'],
                         host=db['HOST'], port=db['PORT'], autocommit=True) as connection:
        connection.execute('UPDATE recruitment_applicationbatch SET processed_rows = %s WHERE id = %s', [index, batch_id])


@timed
def process_batch(batch_id):
    with transaction.atomic():
        batch = ApplicationBatch.objects.select_for_update().get(pk=batch_id)
        if batch.status in (ApplicationBatch.Status.COMPLETED, ApplicationBatch.Status.PROCESSING):
            return batch.status
        batch.status = ApplicationBatch.Status.PROCESSING
        batch.error = ''
        batch.processed_rows = batch.accepted_count = batch.rejected_count = 0
        batch.save()
    touched_roles = set()
    try:
        with batch.source_file.open('rb') as source:
            frame = read_upload(source)
        batch.total_rows = len(frame)
        batch.save(update_fields=['total_rows', 'updated_at'])
        roles = {key.casefold(): role for role in JobRole.objects.all() for key in (role.name, role.code)}
        existing = set(Candidate.objects.values_list('email', flat=True))
        accepted, rejected, seen = [], [], set()
        counts = BatchCounts()
        advance = progress_counter()
        validator = CandidateValidator()
        from screening.services import screen_candidate
        # All candidate inserts roll back on an unexpected batch failure.
        with transaction.atomic():
            for raw in iter_records(frame.columns, frame.itertuples(index=False, name=None)):
                index = advance()
                errors = []
                email = str(raw.get('email', '')).strip().lower().removeprefix('mailto:')
                if email in seen or email in existing:
                    errors.append('email: duplicate within upload or already stored')
                seen.add(email)
                try:
                    clean = validator.validate(raw, roles)
                except RowValidationError as exc:
                    errors.extend(exc.errors)
                if errors:
                    rejected.append(rejected_record(raw, index + 1, errors))
                    counts += BatchCounts(rejected=1)
                    if index % 25 == 0:
                        record_progress(batch.pk, index)
                    continue  # Invalid rows must never reach database insertion.
                try:
                    with transaction.atomic():
                        candidate = Candidate.objects.create(**clean, batch=batch)
                        screen_candidate(candidate)
                except IntegrityError:
                    rejected.append(rejected_record(raw, index + 1, ['email: duplicate from concurrent upload']))
                    counts += BatchCounts(rejected=1)
                else:
                    touched_roles.add(candidate.applied_role_id)
                    accepted.append({**clean, 'applied_role': candidate.applied_role.name})
                    existing.add(email)
                    counts += BatchCounts(accepted=1)
                if index % 25 == 0:
                    record_progress(batch.pk, index)
            batch.accepted_file.save('accepted_rows.csv', export_csv(accepted, FIELDS), save=False)
            batch.rejected_file.save('rejected_rows.csv', export_csv(rejected, (*FIELDS, 'row_number', 'errors')), save=False)
            batch.accepted_count, batch.rejected_count = counts.accepted, counts.rejected
            batch.processed_rows = len(frame)
            batch.status = ApplicationBatch.Status.COMPLETED
            batch.save()
        from screening.services import invalidate_role_cache
        for role_id in touched_roles:
            invalidate_role_cache(role_id)
        return batch.status
    except Exception:
        logger.exception('Batch %s failed', batch_id)
        ApplicationBatch.objects.filter(pk=batch_id).update(status='FAILED', processed_rows=0, accepted_count=0,
            rejected_count=0, error='Processing failed. Check the worker log; retry the batch after fixing the cause.')
        raise
