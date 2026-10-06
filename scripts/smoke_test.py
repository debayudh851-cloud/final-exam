"""Run real HTTP/API/Redis/Celery checks against the local demonstration server."""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
import requests
import redis
import pandas as pd
import io
import uuid

root = Path(__file__).resolve().parent.parent
base = 'http://127.0.0.1:8000'
password = os.environ['DEMO_PASSWORD']
report = []
run_id = uuid.uuid4().hex[:8]


def check(label, response, status):
    if response.status_code != status:
        raise AssertionError(f'{label}: expected {status}, got {response.status_code}: {response.text[:1000]}')
    report.append({'check': label, 'status': response.status_code, 'passed': True})
    print(f'PASS {label}: {response.status_code}')
    return response


def login(username):
    response = check(f'{username} JWT login', requests.post(base + '/api/auth/login/',
        json={'username': username, 'password': password}, timeout=30), 200)
    data = response.json()
    session = requests.Session()
    session.headers['Authorization'] = f'Bearer {data["access"]}'
    return session, data['refresh']


def upload(api, name, background=False):
    # Fresh addresses make rerunning this demonstration safe without deleting existing data.
    frame = pd.read_excel(root / 'samples' / name, keep_default_na=False) if name.endswith('.xlsx') else pd.read_csv(root / 'samples' / name, keep_default_na=False)
    frame['email'] = frame['email'].map(lambda email: f'{run_id}.{email}' if '@' in email else email)
    file = io.BytesIO()
    if name.endswith('.xlsx'):
        frame.to_excel(file, index=False)
    else:
        file.write(frame.to_csv(index=False).encode())
    file.seek(0)
    response = api.post(base + '/api/batches/upload/', files={'file': (name, file)},
                        data={'background': str(background).lower()}, timeout=60)
    check(f'Upload {name}', response, 202 if background else 201)
    return response.json()


def run():
    redis_client = redis.Redis(host='127.0.0.1', port=6379, socket_timeout=3)
    assert redis_client.ping()
    report.append({'check': 'Redis ping', 'passed': True})
    check('Unauthenticated candidate access', requests.get(base + '/api/candidates/', timeout=30), 401)
    hr, refresh = login('hr')
    roles = check('Hyperlinked role list', hr.get(base + '/api/roles/', timeout=30), 200).json()['results']
    role = roles[0]
    small = upload(hr, 'candidates.csv')
    assert small['status'] == 'COMPLETED'
    assert (small['accepted_count'], small['rejected_count']) == (13, 3), small
    for kind in ('accepted', 'rejected'):
        response = check(f'Download {kind} rows', hr.get(small['exports'][kind], timeout=30), 200)
        assert 'text/csv' in response.headers.get('Content-Type', '') or response.content.startswith(b'\xef\xbb\xbf')
    excel = upload(hr, 'candidates.xlsx')
    assert (excel['accepted_count'], excel['rejected_count']) == (0, 16), excel
    large = upload(hr, 'large_batch.csv', background=True)
    observed = [large['status']]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        state = hr.get(base + f'/api/batches/{large["id"]}/status/', timeout=15).json()
        observed.append(state['status'])
        if state['status'] in ('COMPLETED', 'FAILED'):
            break
        time.sleep(.25)
    assert state['status'] == 'COMPLETED', state
    assert state['accepted_count'] == 120, state
    report.append({'check': 'Real Celery upload', 'passed': True, 'states': list(dict.fromkeys(observed)), 'accepted': state['accepted_count']})
    candidates = check('Candidate list', hr.get(base + '/api/candidates/', timeout=30), 200).json()
    candidate = candidates['results'][0]
    candidate_id = candidate['id']
    # Use the small batch candidate for repeatable, role-specific interview demonstration.
    sample_list = hr.get(base + '/api/candidates/?role=' + str(role['id']), timeout=30).json()['results']
    candidate = sample_list[0]
    candidate_id = candidate['id']
    check('Set shortlist stage', hr.patch(base + f'/api/candidates/{candidate_id}/', json={'status': 'SHORTLISTED'}, timeout=30), 200)
    features = {'experience_months': 12, 'notice_period_days': 30, 'expected_salary': 500000,
                'skills': 'python, django, sql', 'applied_role': role['name']}
    before = hr.get(base + f'/api/candidates/{candidate_id}/', timeout=30).json()
    for index in range(2):
        prediction = check(f'ML prediction {index + 1}', hr.post(base + '/api/screening/predict/', json=features, timeout=30), 200).json()
        assert 0 <= prediction['probability'] <= 1
    after = hr.get(base + f'/api/candidates/{candidate_id}/', timeout=30).json()
    assert before == after
    result = check('NLTK analysis', hr.post(base + '/api/screening/nlp/', json={'resume_text': 'I build Python and Django applications with PostgreSQL.', 'role': role['id']}, timeout=30), 200).json()
    assert result['pos_tags'] and result['vector'] and result['matched_skills']
    check('Blank resume NLP', hr.post(base + '/api/screening/nlp/', json={'resume_text': '', 'role': role['id']}, timeout=30), 200)
    interviewer, _ = login('interviewer')
    check('Interviewer candidate restriction', interviewer.get(base + '/api/candidates/', timeout=30), 403)
    slots = interviewer.get(base + '/api/interview-slots/', timeout=30).json()['results']
    slot = next(s for s in slots if s['role'] == role['id'] and not s['candidate'])
    check('Assign interview', hr.post(base + '/api/interviews/assign/', json={'candidate': candidate_id, 'slot': slot['id']}, timeout=30), 200)
    check('Submit interviewer feedback', interviewer.post(base + '/api/interview-feedback/',
        json={'slot': slot['id'], 'rating': 4, 'comments': 'Good Python fundamentals in this demonstration.', 'recommendation': 'SELECTED'}, timeout=30), 201)
    assert hr.get(base + f'/api/candidates/{candidate_id}/', timeout=30).json()['status'] == 'SELECTED'
    browser = requests.Session()
    page = browser.get(base + '/accounts/login/', timeout=30)
    csrf = browser.cookies['csrftoken']
    check('Browser sign-in', browser.post(base + '/accounts/login/', data={'csrfmiddlewaretoken': csrf,
        'username': 'hr', 'password': password}, timeout=30), 200)
    for route in ['/dashboard/', '/dashboard/candidates/', f'/dashboard/candidates/{candidate_id}/',
                  f'/dashboard/batches/{small["id"]}/', '/dashboard/interviews/', '/api/docs/', '/api/schema/']:
        # API schema/docs are public; dashboard uses the logged-in browser session.
        check(f'Page {route}', browser.get(base + route, timeout=30), 200)
    filtered = browser.get(base + f'/dashboard/candidates/?role={role["id"]}&batch=', timeout=30)
    assert browser.cookies['last_role'] == str(role['id'])
    csrf = browser.cookies['csrftoken']
    check('CSRF AJAX duplicate email', browser.post(base + '/dashboard/ajax/email/',
        data={'email': candidate['email']}, headers={'X-CSRFToken': csrf}, timeout=30), 200)
    check('AJAX role slots', browser.get(base + f'/dashboard/ajax/slots/?role={role["id"]}', timeout=30), 200)
    keys = redis_client.keys('*top_candidates*')
    assert keys, 'Expected Redis shortlist cache key after candidate list.'
    report.append({'check': 'Redis shortlist caching', 'passed': True})
    check('JWT logout', hr.post(base + '/api/auth/logout/', json={'refresh': refresh}, timeout=30), 200)
    check('Revoked refresh rejected', requests.post(base + '/api/auth/refresh/', json={'refresh': refresh}, timeout=30), 401)
    return report


if __name__ == '__main__':
    result = run()
    output = root / 'evidence'
    output.mkdir(exist_ok=True)
    (output / 'http_smoke.json').write_text(json.dumps({'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'checks': result}, indent=2), encoding='utf-8')
    print(f'All {len(result)} HTTP and service checks passed.')
