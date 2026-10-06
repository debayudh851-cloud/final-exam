"""Check the assessment fixes through the live portal and a real Celery worker."""
import csv
import io
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

root = Path(__file__).resolve().parent.parent
base = 'http://127.0.0.1:8000'
password = os.environ['DEMO_PASSWORD']
api = requests.Session()
browser = requests.Session()
checks = []
run_id = uuid.uuid4().hex[:8]


def expect(name, response, status=200):
    assert response.status_code == status, f'{name}: unexpected HTTP {response.status_code}'
    checks.append({'check': name, 'passed': True, 'status': status})
    print(f'PASS {name}')
    return response


def upload(name, background=False):
    frame = pd.read_csv(root / 'samples' / name, keep_default_na=False, dtype=str)
    frame['email'] = frame['email'].map(lambda value: f'{run_id}.{value}' if '@' in value else value)
    if name == 'candidates.csv':
        frame.loc[[0, 12], 'candidate_name'] = ' Original NAME '
    response = api.post(base + '/api/batches/upload/', files={'file': (name, frame.to_csv(index=False).encode())},
                        data={'background': str(background).lower()}, timeout=60)
    return expect(f'Upload {name}', response, 202 if background else 201).json()


def run():
    login = expect('HR API login', api.post(base + '/api/auth/login/', json={'username': 'hr', 'password': password}, timeout=30)).json()
    api.headers['Authorization'] = 'Bearer ' + login['access']
    browser.get(base + '/accounts/login/', timeout=30)
    expect('HR browser login', browser.post(base + '/accounts/login/', data={
        'username': 'hr', 'password': password, 'csrfmiddlewaretoken': browser.cookies['csrftoken']}, timeout=30))
    role_id = api.get(base + '/api/roles/', timeout=30).json()['results'][0]['id']
    sentinel = expect('Create rejected JSON test candidate', api.post(base + '/api/candidates/', json={
        'candidate_name': 'JSON Coverage Test', 'email': f'json.{run_id}@example.test', 'phone': '9876543210',
        'applied_role': role_id, 'skills': 'python', 'experience_months': 0, 'notice_period_days': 0,
        'expected_salary': 300000, 'historical_selection_status': '', 'status': 'REJECTED'}, timeout=30), 201).json()
    try:
        all_rows = expect('All-candidate JSON response', browser.get(base + '/dashboard/json/candidates/', timeout=30)).json()['candidates']
        actual_count = api.get(base + '/api/candidates/', timeout=30).json()['count']
        assert len(all_rows) == actual_count and actual_count > 100
        assert any(row['id'] == sentinel['id'] and row['status'] == 'REJECTED' for row in all_rows)
        checks.append({'check': 'JSON includes every row and rejected candidate', 'passed': True, 'rows': actual_count})
        detail = expect('Individual rejected candidate JSON', browser.get(base + f'/dashboard/json/candidates/{sentinel["id"]}/', timeout=30)).json()
        assert detail['status'] == 'REJECTED'
        dashboard = expect('Dashboard aggregate display', browser.get(base + '/dashboard/', timeout=30)).text
        for label in ('Total expectations', 'Minimum expectation', 'Maximum expectation', 'Total salary', 'Minimum salary', 'Maximum salary', 'Average salary'):
            assert label in dashboard
        empty = expect('Grouped minimum-applications filter', browser.get(base + '/dashboard/?min_candidates=50000', timeout=30)).text
        assert 'No roles meet this application threshold.' in empty
        invalid = expect('Invalid report filter handled', browser.get(base + '/dashboard/?min_candidates=bad', timeout=30)).text
        assert 'Enter a whole number.' in invalid
        small = upload('candidates.csv')
        assert (small['status'], small['accepted_count'], small['rejected_count']) == ('COMPLETED', 13, 3)
        rejected_csv = expect('Rejected-row export', api.get(small['exports']['rejected'], timeout=30)).content.decode('utf-8-sig')
        rejected_rows = list(csv.DictReader(io.StringIO(rejected_csv)))
        duplicate = next(row for row in rejected_rows if 'duplicate' in row['errors'])
        assert duplicate['candidate_name'] == ' Original NAME '
        malformed = next(row for row in rejected_rows if row['email'] == 'invalid-email')
        for field in ('email:', 'phone:', 'experience_months:', 'expected_salary:'):
            assert field in malformed['errors']
        checks.append({'check': 'Integrated recursive errors, raw-row copy, and outcome counts', 'passed': True, 'accepted': 13, 'rejected': 3})
        large = upload('large_batch.csv', background=True)
        states = [large['status']]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            status = api.get(base + f'/api/batches/{large["id"]}/status/', timeout=15).json()
            states.append(status['status'])
            if status['status'] in ('COMPLETED', 'FAILED'):
                break
            time.sleep(.2)
        assert (status['status'], status['processed_rows'], status['accepted_count'], status['rejected_count']) == ('COMPLETED', 120, 120, 0)
        checks.append({'check': 'Integrated helpers in real Celery upload', 'passed': True,
                       'states': list(dict.fromkeys(states)), 'processed_rows': 120})
    finally:
        expect('Remove own synthetic JSON test candidate', api.delete(base + f'/api/candidates/{sentinel["id"]}/', timeout=30), 204)
    (root / 'evidence' / 'gap_checks.json').write_text(json.dumps({
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks}, indent=2), encoding='utf-8')
    print(f'All {len(checks)} targeted live checks passed.')


if __name__ == '__main__':
    run()
