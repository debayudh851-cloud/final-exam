"""Verify the packaged source using a fresh project database and supplied runtime dependencies."""
import os
import re
import json
import secrets
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile
import psycopg
from psycopg import sql
from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
load_dotenv(root / '.env')
identifier = secrets.token_hex(6)
database = 'talentdesk_verify_' + identifier
assert re.fullmatch(r'talentdesk_verify_[0-9a-f]{12}', database)
destination = root / '.tmp' / ('checkout_' + identifier)
destination.mkdir(parents=True)
with ZipFile(root / 'recruitment_portal_submission.zip') as archive:
    assert all(name.startswith('recruitment_portal/') and '..' not in Path(name).parts for name in archive.namelist())
    archive.extractall(destination)
checkout = destination / 'recruitment_portal'
environment = dict(os.environ)
environment.update(DB_NAME=database, DJANGO_SECRET_KEY=secrets.token_urlsafe(48), DEMO_PASSWORD='CleanCheckoutDemo!2026',
                   REDIS_URL='redis://127.0.0.1:6379/14', DEBUG='true')
steps = []


def run(*args):
    result = subprocess.run([sys.executable, *args], cwd=checkout, env=environment, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f'Clean checkout command {args[0]} failed: {result.stderr[-1500:]}')
    steps.append({'command': list(args[:3]), 'passed': True})
    print(f'PASS clean checkout: {args[0]} {args[1] if len(args) > 1 else ""}')


connection = psycopg.connect(dbname='postgres', user=os.getenv('DB_USER', 'postgres'), password=os.getenv('DB_PASSWORD', ''),
    host=os.getenv('DB_HOST', '127.0.0.1'), port=os.getenv('DB_PORT', '5432'), autocommit=True)
connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
try:
    run('manage.py', 'migrate', '--noinput')
    run('manage.py', 'makemigrations', '--check', '--dry-run')
    run('manage.py', 'seed_demo')
    run('manage.py', 'setup_nlp')
    run('manage.py', 'check')
    code = """
from django.core.files import File
from accounts.models import User
from recruitment.services import submit_upload
from recruitment.models import Candidate
from screening.ml import predict
from django.test import Client
with open('samples/candidates.csv', 'rb') as source:
    batch = submit_upload(User.objects.get(username='hr'), File(source, name='candidates.csv'), 16)
assert (batch.status, batch.accepted_count, batch.rejected_count) == ('COMPLETED', 13, 3)
client = Client()
client.force_login(User.objects.get(username='hr'))
assert client.get('/dashboard/').status_code == 200
assert client.get('/dashboard/candidates/').status_code == 200
candidate = Candidate.objects.first()
assert client.get(f'/dashboard/candidates/{candidate.pk}/').status_code == 200
result = predict({'experience_months': 12, 'notice_period_days': 30, 'expected_salary': 500000, 'skills': 'python, sql', 'applied_role': 'Python Developer'})
assert 0 <= result['probability'] <= 1
print('Fresh database upload and packaged-model inference passed.')
"""
    run('manage.py', 'shell', '--command', code)
    run('scripts/check_sql.py')
    report = {'source': 'Verified submission ZIP extraction', 'runtime': 'Existing verified virtual environment; fresh source and database',
              'checks': steps, 'upload_accepted': 13, 'upload_rejected': 3, 'passed': True}
    (root / 'evidence' / 'clean_checkout.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
finally:
    # This exact random database was created above solely for this verification.
    connection.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))
    connection.close()
