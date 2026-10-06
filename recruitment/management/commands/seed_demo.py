import os
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.models import User
from recruitment.models import JobRole, InterviewSlot


class Command(BaseCommand):
    help = 'Idempotently create test accounts, job roles, and future interview slots.'

    def handle(self, *args, **options):
        password = os.getenv('DEMO_PASSWORD')
        if not password or len(password) < 12:
            raise CommandError('Set DEMO_PASSWORD to a test-only password of at least 12 characters.')
        users = {}
        for username, role in [('admin', 'ADMIN'), ('hr', 'HR'), ('interviewer', 'INTERVIEWER')]:
            user, created = User.objects.get_or_create(username=username,
                defaults={'email': f'{username}@example.test', 'role': role, 'email_verified': True,
                          'is_staff': username == 'admin', 'is_superuser': username == 'admin'})
            if created:
                user.set_password(password)
                user.save()
            users[username] = user
        for name, code, skills in [('Python Developer', 'PYTHON', ['python', 'sql', 'git']),
                                   ('Django Developer', 'DJANGO', ['python', 'django', 'postgresql', 'rest'])]:
            role, _ = JobRole.objects.get_or_create(code=code, defaults={'name': name, 'required_skills': skills,
                'min_experience_months': 0, 'max_notice_period_days': 60, 'max_salary': 800000})
            if not InterviewSlot.objects.filter(role=role, starts_at__gt=timezone.now()).exists():
                start = (timezone.now() + timedelta(days=2)).replace(hour=5, minute=30, second=0, microsecond=0)
                if code == 'DJANGO':
                    start += timedelta(hours=2)
                for offset in range(3):
                    slot_start = start + timedelta(hours=offset)
                    InterviewSlot.objects.get_or_create(interviewer=users['interviewer'], starts_at=slot_start,
                        defaults={'role': role, 'ends_at': slot_start + timedelta(minutes=45), 'location': 'Campus interview room'})
        self.stdout.write(self.style.SUCCESS('Demo accounts, roles, and interview slots ready.'))
