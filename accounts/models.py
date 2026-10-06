from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        HR = 'HR', 'HR'
        INTERVIEWER = 'INTERVIEWER', 'Interviewer'
        ADMIN = 'ADMIN', 'Admin'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=15, choices=Role.choices, default=Role.HR)
    email_verified = models.BooleanField(default=False)
    otp_hash = models.CharField(max_length=128, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    otp_attempts = models.PositiveSmallIntegerField(default=0)

    @property
    def is_portal_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def can_manage_candidates(self):
        return self.is_portal_admin or self.role == self.Role.HR

    @property
    def verified(self):
        return self.email_verified or self.is_superuser
