from django.contrib import admin
from .models import JobRole, Candidate, ApplicationBatch, ScreeningResult, InterviewSlot, InterviewFeedback


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('candidate_name', 'email', 'applied_role', 'status', 'expected_salary', 'created_at')
    list_filter = ('applied_role', 'status', 'batch')
    search_fields = ('candidate_name', 'email', 'skills', 'college')
    fieldsets = [('Identity', {'fields': ('candidate_name', 'email', 'phone', 'college', 'image')}),
                 ('Application', {'fields': ('applied_role', 'batch', 'skills', 'experience_months', 'notice_period_days', 'expected_salary', 'status', 'historical_selection_status')}),
                 ('Resume', {'fields': ('resume_text', 'resume_file', 'portfolio_url')})]


@admin.register(JobRole)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'min_experience_months', 'max_salary')
    search_fields = ('name', 'code')


@admin.register(ApplicationBatch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'uploaded_by', 'status', 'total_rows', 'accepted_count', 'rejected_count')
    list_filter = ('status',)
    readonly_fields = ('task_id', 'error', 'processed_rows')


@admin.register(ScreeningResult)
class ScreeningAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'rule_passed', 'ml_probability', 'keyword_score')
    list_filter = ('rule_passed',)
    search_fields = ('candidate__email',)


@admin.register(InterviewSlot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ('role', 'candidate', 'interviewer', 'starts_at')
    list_filter = ('role', 'interviewer')
    search_fields = ('candidate__email',)


@admin.register(InterviewFeedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('slot', 'submitted_by', 'rating', 'recommendation')
    list_filter = ('rating', 'recommendation')
