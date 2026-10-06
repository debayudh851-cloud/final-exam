from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.db import models


class JobRole(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, validators=[RegexValidator(r'^[A-Z][A-Z0-9_-]{1,19}$', 'Use 2–20 uppercase letters, digits, hyphens, or underscores; start with a letter.')])
    required_skills = models.JSONField(default=list)
    min_experience_months = models.PositiveIntegerField(default=0)
    max_notice_period_days = models.PositiveIntegerField(default=90)
    max_salary = models.DecimalField(max_digits=12, decimal_places=2, default=800000)

    def __str__(self):
        return self.name

    def clean(self):
        if not isinstance(self.required_skills, list) or not all(isinstance(value, str) and value.strip() for value in self.required_skills):
            raise ValidationError({'required_skills': 'Enter a JSON list of nonempty skill strings.'})


class ApplicationBatch(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'QUEUED', 'Queued'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source_file = models.FileField(upload_to='batches/source/')
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.QUEUED)
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    accepted_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    accepted_file = models.FileField(upload_to='batches/results/', blank=True)
    rejected_file = models.FileField(upload_to='batches/results/', blank=True)
    error = models.TextField(blank=True)
    task_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Candidate(models.Model):
    class Stage(models.TextChoices):
        NEW = 'NEW', 'New'
        SHORTLISTED = 'SHORTLISTED', 'Shortlisted'
        INTERVIEW = 'INTERVIEW', 'Interview'
        SELECTED = 'SELECTED', 'Selected'
        WAITLISTED = 'WAITLISTED', 'Waitlisted'
        REJECTED = 'REJECTED', 'Rejected'

    candidate_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    college = models.CharField(max_length=200, blank=True)
    applied_role = models.ForeignKey(JobRole, on_delete=models.PROTECT, related_name='candidates')
    batch = models.ForeignKey(ApplicationBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    skills = models.TextField()
    experience_months = models.PositiveIntegerField(validators=[MaxValueValidator(600)])
    notice_period_days = models.PositiveIntegerField(validators=[MaxValueValidator(365)])
    expected_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    resume_text = models.TextField(blank=True)
    portfolio_url = models.URLField(blank=True)
    historical_selection_status = models.CharField(max_length=15, blank=True)
    status = models.CharField(max_length=15, choices=Stage.choices, default=Stage.NEW)
    resume_file = models.FileField(upload_to='resumes/', blank=True,
                                  validators=[FileExtensionValidator(['pdf', 'txt', 'docx'])])
    image = models.ImageField(upload_to='photos/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['applied_role', 'status'])]
        constraints = [models.CheckConstraint(condition=models.Q(expected_salary__gte=0), name='salary_nonnegative')]

    def __str__(self):
        return self.candidate_name


class ScreeningResult(models.Model):
    candidate = models.OneToOneField(Candidate, on_delete=models.CASCADE, related_name='screening')
    rule_passed = models.BooleanField(default=False)
    rule_reasons = models.JSONField(default=list)
    ml_probability = models.FloatField(null=True, blank=True)
    keyword_score = models.FloatField(default=0)
    matched_skills = models.JSONField(default=list)
    pos_tags = models.JSONField(default=list)
    model_version = models.CharField(max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class InterviewSlot(models.Model):
    role = models.ForeignKey(JobRole, on_delete=models.PROTECT)
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='interview_slots')
    candidate = models.ForeignKey(Candidate, on_delete=models.SET_NULL, null=True, blank=True, related_name='interview_slots')
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=200, default='Office')

    class Meta:
        ordering = ['starts_at']
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='slot_end_after_start'),
                       models.UniqueConstraint(fields=['interviewer', 'starts_at'], name='unique_interviewer_start')]

    def __str__(self):
        return f'{self.role} — {self.starts_at:%d %b %H:%M}'


class InterviewFeedback(models.Model):
    slot = models.OneToOneField(InterviewSlot, on_delete=models.CASCADE, related_name='feedback')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comments = models.TextField()
    recommendation = models.CharField(max_length=15, choices=[('SELECTED', 'Selected'), ('WAITLISTED', 'Waitlisted'), ('REJECTED', 'Rejected')])
    created_at = models.DateTimeField(auto_now_add=True)
