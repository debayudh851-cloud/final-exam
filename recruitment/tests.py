import csv
import io
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, override_settings, Client
from django.test.utils import CaptureQueriesContext
from django.db import connection
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.urls import reverse
from django.core.cache import cache, caches
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User
from .models import JobRole, Candidate, ApplicationBatch, InterviewSlot, ScreeningResult
from .serializers import CandidateSerializer
from .services import assign_slot
from ingestion.service import read_upload, process_batch
from ingestion.validators import FIELDS, CandidateValidator, InputFileError, RowValidationError, DEFAULT_VALIDATION_POLICY
from screening.nlp import analyze_resume

LOCAL_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
               'throttle': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'test-throttle'}}


def row(**updates):
    base = dict(zip(FIELDS, [' Alice Example ', 'ALICE@example.test', '+91 (98765) 43210', 'Demo College',
        'PYTHON', ' Python; SQL; python ', '6', '30', '400000.00', '', '', 'selected']))
    return {**base, **updates}


def csv_upload(rows, name='test.csv'):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return SimpleUploadedFile(name, stream.getvalue().encode(), content_type='text/csv')


@override_settings(CACHES=LOCAL_CACHE)
class PortalTests(TestCase):
    def setUp(self):
        cache.clear()
        caches['throttle'].clear()
        self.hr = User.objects.create_user('testhr', 'testhr@example.test', 'TestPassword!2026', role='HR', email_verified=True)
        self.interviewer = User.objects.create_user('testinterviewer', 'i@example.test', 'TestPassword!2026', role='INTERVIEWER', email_verified=True)
        self.role = JobRole.objects.create(name='Python Developer', code='PYTHON', required_skills=['python', 'sql'])
        self.candidate = Candidate.objects.create(candidate_name='Alice', email='alice@example.test', phone='9876543210',
            applied_role=self.role, skills='python, sql', experience_months=6, notice_period_days=30, expected_salary=400000)
        self.client.force_login(self.hr)
        self.api = APIClient()
        self.api.force_authenticate(self.hr)

    def test_validator_normalizes_and_collects_errors(self):
        valid = CandidateValidator().validate(row(), {'python': self.role})
        self.assertEqual(valid['email'], 'alice@example.test')
        self.assertEqual(valid['skills'], 'python, sql')
        self.assertEqual(valid['phone'], '+919876543210')
        zero = CandidateValidator().validate(row(experience_months=0, notice_period_days=0, expected_salary=0), {'python': self.role})
        self.assertEqual(zero['experience_months'], 0)
        with self.assertRaises(RowValidationError) as caught:
            CandidateValidator().validate(row(email='bad', phone='bad', experience_months='nan', expected_salary='-1'), {'python': self.role})
        self.assertGreaterEqual(len(caught.exception.errors), 4)

    def test_bad_files_and_empty_input(self):
        for file in [SimpleUploadedFile('bad.pdf', b'%PDF'), SimpleUploadedFile('empty.csv', b''),
                     SimpleUploadedFile('columns.csv', b'email\na@example.test\n'), csv_upload([]),
                     SimpleUploadedFile('bad.xlsx', b'not excel')]:
            with self.assertRaises(InputFileError):
                read_upload(file)

    def test_validation_policy_isolation_and_international_phone_normalization(self):
        strict, normal = CandidateValidator(), CandidateValidator()
        strict.policy['text_limits']['candidate_name'] = 3
        self.assertEqual(DEFAULT_VALIDATION_POLICY['text_limits']['candidate_name'], 150)
        self.assertEqual(normal.policy['text_limits']['candidate_name'], 150)
        with self.assertRaises(RowValidationError):
            strict.validate(row(), {'python': self.role})
        for phone in ('0091 (98765) 43210', '＋91 (98765) 43210'):
            original = row(phone=phone)
            clean = normal.validate(original, {'python': self.role})
            self.assertEqual(clean['phone'], '+919876543210')
            self.assertEqual(original['phone'], phone)

    def test_candidate_json_includes_all_rows_and_rejected_candidates(self):
        Candidate.objects.bulk_create([Candidate(candidate_name=f'Candidate {number:03d}',
            email=f'all{number}@example.test', phone='9876543210', applied_role=self.role, skills='python',
            experience_months=0, notice_period_days=0, expected_salary=300000,
            status='REJECTED' if number % 2 else 'NEW') for number in range(121)])
        response = self.client.get('/dashboard/json/candidates/')
        self.assertEqual(response.status_code, 200)
        returned = response.json()['candidates']
        self.assertEqual(len(returned), 122)
        self.assertEqual({item['id'] for item in returned}, set(Candidate.objects.values_list('id', flat=True)))
        self.assertTrue(any(item['status'] == 'REJECTED' for item in returned))
        rejected = Candidate.objects.filter(status='REJECTED').first()
        detail = self.client.get(f'/dashboard/json/candidates/{rejected.pk}/')
        self.assertEqual(detail.json()['status'], 'REJECTED')
        self.assertEqual(Client().get('/dashboard/json/candidates/').status_code, 302)

    def test_dashboard_salary_aggregates_and_role_threshold(self):
        second_role = JobRole.objects.create(name='Django Developer', code='DJANGO')
        Candidate.objects.create(candidate_name='Bob', email='bob@example.test', phone='9876543211',
            applied_role=self.role, skills='python', experience_months=0, notice_period_days=0, expected_salary=200000)
        Candidate.objects.create(candidate_name='Carol', email='carol@example.test', phone='9876543212',
            applied_role=second_role, skills='django', experience_months=0, notice_period_days=0, expected_salary=600000)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/dashboard/?min_candidates=2')
        self.assertEqual(response.status_code, 200)
        summary = response.context['summary']
        self.assertEqual((summary['total'], summary['salary_sum'], summary['salary_min'], summary['salary_max'], summary['salary_avg']),
                         (3, Decimal('1200000'), Decimal('200000'), Decimal('600000'), Decimal('400000')))
        roles = response.context['by_role']
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]['applied_role__name'], self.role.name)
        self.assertEqual((roles[0]['total'], roles[0]['salary_sum'], roles[0]['salary_min'], roles[0]['salary_max'], roles[0]['avg_salary']),
                         (2, Decimal('600000'), Decimal('200000'), Decimal('400000'), Decimal('300000')))
        self.assertTrue(any('HAVING' in entry['sql'].upper() for entry in queries.captured_queries))
        for label in ('Total expectations', 'Minimum expectation', 'Maximum expectation', 'Total salary', 'Minimum salary', 'Maximum salary', 'Average salary'):
            self.assertContains(response, label)
        self.assertContains(response, '₹1200000')
        self.assertContains(response, 'Showing roles with at least 2 applications')
        self.assertContains(self.client.get('/dashboard/?min_candidates=4'), 'No roles meet this application threshold.')
        for invalid in ('bad', '0', '-1', '99999999999999999999999999999999999'):
            response = self.client.get('/dashboard/', {'min_candidates': invalid})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['report_form'].errors)
            self.assertEqual(response.context['minimum_candidates'], 1)

    def test_optional_and_punctuation_resume(self):
        self.assertEqual(analyze_resume('', ['python'])['keyword_score'], 0)
        result = analyze_resume('... !!!', ['python'], include_pos=False)
        self.assertEqual(result['vector'], {})

    def test_pages_render_and_cookie_session(self):
        self.assertEqual(reverse('candidate-list'), '/dashboard/candidates/')
        self.assertEqual(reverse('candidate-detail', kwargs={'pk': self.candidate.pk}), f'/dashboard/candidates/{self.candidate.pk}/')
        for url in ['/dashboard/', '/dashboard/candidates/', f'/dashboard/candidates/{self.candidate.pk}/',
                    '/dashboard/candidates/add/', '/dashboard/upload/', '/dashboard/interviews/', '/admin/login/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        response = self.client.get(f'/dashboard/candidates/?role={self.role.pk}&batch=42')
        self.assertEqual(response.cookies['last_role'].value, str(self.role.pk))
        self.assertEqual(self.client.session['current_batch'], 42)
        self.client.get('/dashboard/candidates/?batch=')
        self.assertIsNone(self.client.session['current_batch'])

    def test_access_and_csrf(self):
        self.assertEqual(Client().get('/dashboard/').status_code, 302)
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get('/api/candidates/').status_code, 401)
        self.api.credentials(HTTP_AUTHORIZATION='Bearer bad')
        self.assertEqual(self.api.get('/api/candidates/').status_code, 401)
        self.api.credentials()
        self.api.force_authenticate(self.interviewer)
        self.assertEqual(self.api.get('/api/candidates/').status_code, 403)
        unverified = User.objects.create_user('unverified', 'unverified@example.test', 'TestPassword!2026')
        self.api.force_authenticate(unverified)
        self.assertEqual(self.api.get('/api/candidates/').status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.hr)
        self.assertEqual(csrf_client.post('/dashboard/ajax/email/', {'email': 'alice@example.test'}).status_code, 403)
        response = csrf_client.get('/dashboard/candidates/add/')
        token = response.cookies['csrftoken'].value
        response = csrf_client.post('/dashboard/ajax/email/', {'email': 'alice@example.test'}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.json(), {'exists': True})

    def test_expired_token_and_logout_blacklist(self):
        refresh = RefreshToken.for_user(self.hr)
        access = refresh.access_token
        access.set_exp(from_time=timezone.now() - timedelta(hours=1), lifetime=timedelta(seconds=1))
        self.api.force_authenticate(None)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(self.api.get('/api/candidates/').status_code, 401)
        self.api.credentials()
        self.api.force_authenticate(self.hr)
        self.assertEqual(self.api.post('/api/auth/logout/', {'refresh': str(refresh)}).status_code, 200)
        self.api.force_authenticate(None)
        self.assertEqual(self.api.post('/api/auth/refresh/', {'refresh': str(refresh)}).status_code, 401)

    def test_registration_verification_and_role_escalation(self):
        self.api.force_authenticate(None)
        with patch('accounts.serializers.send_mail') as mail:
            response = self.api.post('/api/auth/register/', {'username': 'newhr', 'email': 'new@example.test',
                                     'password': 'TestPassword!2026', 'role': 'ADMIN'})
            self.assertEqual(response.status_code, 201, response.data)
            code = mail.call_args.args[1].split('code is ')[1][:6]
        new = User.objects.get(username='newhr')
        self.assertEqual(new.role, 'HR')
        self.assertNotEqual(new.otp_hash, code)
        self.assertEqual(self.api.post('/api/auth/login/', {'username': 'newhr', 'password': 'TestPassword!2026'}).status_code, 400)
        self.assertEqual(self.api.post('/api/auth/verify/', {'email': new.email, 'code': code}).status_code, 200)
        self.assertEqual(self.api.post('/api/auth/login/', {'username': 'newhr', 'password': 'TestPassword!2026'}).status_code, 200)
        self.assertEqual(self.api.post('/api/auth/verify/', {'email': new.email, 'code': code}).status_code, 400)

    def test_candidate_api_crud_and_validation(self):
        payload = row(email='fresh@example.test', applied_role=self.role.pk)
        created = self.api.post('/api/candidates/', payload, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        pk = created.data['id']
        self.assertEqual(self.api.get(f'/api/candidates/{pk}/').status_code, 200)
        invalid = self.api.patch(f'/api/candidates/{pk}/', {'experience_months': -1}, format='json')
        self.assertEqual(invalid.status_code, 400)
        updated = self.api.put(f'/api/candidates/{pk}/', {**payload, 'skills': 'python, django'}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(self.api.delete(f'/api/candidates/{pk}/').status_code, 204)

    def test_otp_expiry_and_attempt_limit(self):
        self.api.force_authenticate(None)
        user = User.objects.create_user('otpuser', 'otp@example.test', 'TestPassword!2026', otp_hash=make_password('123456'),
                                        otp_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.api.post('/api/auth/verify/', {'email': user.email, 'code': '123456'}).status_code, 400)
        user.otp_expires_at = timezone.now() + timedelta(minutes=10)
        user.save()
        for _ in range(5):
            self.assertEqual(self.api.post('/api/auth/verify/', {'email': user.email, 'code': '000000'}).status_code, 400)
        self.assertEqual(self.api.post('/api/auth/verify/', {'email': user.email, 'code': '123456'}).status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)
        self.assertEqual(user.otp_attempts, 5)

    def test_slot_assignment_and_feedback_permissions(self):
        start = timezone.now() + timedelta(days=2)
        slot = InterviewSlot.objects.create(role=self.role, interviewer=self.interviewer, starts_at=start, ends_at=start + timedelta(hours=1))
        assign_slot(self.candidate, slot.pk)
        with self.assertRaises(ValueError):
            assign_slot(self.candidate, slot.pk)
        self.api.force_authenticate(self.interviewer)
        response = self.api.post('/api/interview-feedback/', {'slot': slot.pk, 'rating': 4, 'comments': 'Good fundamentals', 'recommendation': 'SELECTED'})
        self.assertEqual(response.status_code, 201, response.data)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, 'SELECTED')
        self.assertEqual(self.api.post('/api/interview-feedback/', {'slot': slot.pk, 'rating': 4, 'comments': 'duplicate', 'recommendation': 'SELECTED'}).status_code, 400)
        other = User.objects.create_user('other', 'other@example.test', 'TestPassword!2026', role='INTERVIEWER', email_verified=True)
        self.api.force_authenticate(other)
        self.assertEqual(self.api.get('/api/interview-slots/').data['count'], 0)

    def test_model_prediction_does_not_mutate_records(self):
        payload = {'experience_months': 6, 'notice_period_days': 30, 'expected_salary': 400000,
                   'skills': 'python, sql', 'applied_role': self.role.name}
        before = list(Candidate.objects.values())
        for _ in range(2):
            response = self.api.post('/api/screening/predict/', payload, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertGreaterEqual(response.data['probability'], 0)
            self.assertLessEqual(response.data['probability'], 1)
        self.assertEqual(list(Candidate.objects.values()), before)


@override_settings(CACHES=LOCAL_CACHE)
class IngestionTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user('hr', 'hr@example.test', 'TestPassword!2026', email_verified=True)
        self.role = JobRole.objects.create(name='Python Developer', code='PYTHON', required_skills=['python'])

    def test_accepted_rejected_and_repeatable_batch(self):
        batch = ApplicationBatch.objects.create(uploaded_by=self.user,
            source_file=csv_upload([row(), row(), row(email='bad', phone='123'), row(email='optional@example.test')]))
        process_batch(batch.pk)
        batch.refresh_from_db()
        self.assertEqual((batch.status, batch.accepted_count, batch.rejected_count), ('COMPLETED', 2, 2))
        self.assertEqual(Candidate.objects.count(), 2)
        process_batch(batch.pk)
        self.assertEqual(Candidate.objects.count(), 2)
        with batch.rejected_file.open('rb') as file:
            content = file.read().decode('utf-8-sig')
        self.assertIn('duplicate', content)
        self.assertIn('email: invalid format', content)

    def test_task_failure_is_visible_and_rolls_back(self):
        batch = ApplicationBatch.objects.create(uploaded_by=self.user, source_file=csv_upload([row(), row(email='second@example.test')]))
        with patch('screening.services.screen_candidate', side_effect=RuntimeError('deliberate test failure')):
            with self.assertRaises(RuntimeError):
                process_batch(batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'FAILED')
        self.assertEqual(Candidate.objects.count(), 0)
        self.assertTrue(batch.error)

    def test_broker_failure_is_visible(self):
        from recruitment.services import submit_upload
        with patch('recruitment.services.process_upload.delay', side_effect=ConnectionError('deliberate broker outage')):
            batch = submit_upload(self.user, csv_upload([row()]), 1, background=True)
        self.assertEqual(batch.status, 'FAILED')
        self.assertTrue(batch.error)
        self.assertEqual(Candidate.objects.count(), 0)

    def test_progress_visible_after_chunk_and_completes(self):
        batch = ApplicationBatch.objects.create(uploaded_by=self.user,
            source_file=csv_upload([row(email=f'batch{i}@example.test') for i in range(30)]))
        process_batch(batch.pk)
        batch.refresh_from_db()
        self.assertEqual((batch.processed_rows, batch.accepted_count), (30, 30))

    def test_rejected_rows_preserve_source_values_and_progress(self):
        batch = ApplicationBatch.objects.create(uploaded_by=self.user,
            source_file=csv_upload([row(candidate_name=' original NAME ', email=f'invalid{index}',
                phone='123', expected_salary='-1') for index in range(30)]))
        with patch('ingestion.service.record_progress') as publish:
            process_batch(batch.pk)
        publish.assert_called_once_with(batch.pk, 25)
        batch.refresh_from_db()
        self.assertEqual((batch.processed_rows, batch.accepted_count, batch.rejected_count), (30, 0, 30))
        with batch.rejected_file.open('rb') as file:
            exported = list(csv.DictReader(io.StringIO(file.read().decode('utf-8-sig'))))
        self.assertEqual((exported[0]['row_number'], exported[-1]['row_number']), ('2', '31'))
        self.assertEqual(exported[0]['candidate_name'], ' original NAME ')
        for reason in ('email: invalid format', 'phone: use', 'expected_salary: invalid'):
            self.assertIn(reason, exported[0]['errors'])
