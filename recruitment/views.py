import json
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Sum, Min, Max, Avg, Q
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, DeleteView
from .models import JobRole, Candidate, ApplicationBatch, InterviewSlot
from .forms import UploadForm, CandidateForm, ScreeningStatusForm, AssignSlotForm, FeedbackForm, RoleReportFilterForm
from .services import submit_upload, assign_slot
from screening.services import screen_candidate, invalidate_role_cache, top_candidates


def manager_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.verified or not request.user.can_manage_candidates:
            return HttpResponseForbidden('Verified HR or Admin access required.')
        return view(request, *args, **kwargs)
    return wrapper


class ManagerMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and (not request.user.verified or not request.user.can_manage_candidates):
            return HttpResponseForbidden('Verified HR or Admin access required.')
        return super().dispatch(request, *args, **kwargs)


@login_required
def dashboard(request):
    if not request.user.can_manage_candidates:
        return redirect('interviews')
    query = Candidate.objects.all()
    summary = query.aggregate(total=Count('id'), salary_sum=Sum('expected_salary'), salary_min=Min('expected_salary'),
                              salary_max=Max('expected_salary'), salary_avg=Avg('expected_salary'),
                              shortlisted=Count('id', filter=Q(status='SHORTLISTED')), selected=Count('id', filter=Q(status='SELECTED')))
    report_form = RoleReportFilterForm(request.GET or None, initial={'min_candidates': 1})
    minimum = report_form.cleaned_data['min_candidates'] if report_form.is_bound and report_form.is_valid() else 1
    # Filtering an annotated aggregate produces SQL HAVING after GROUP BY.
    by_role = list(query.values('applied_role_id', 'applied_role__name').annotate(
        total=Count('id'), salary_sum=Sum('expected_salary'), salary_min=Min('expected_salary'),
        salary_max=Max('expected_salary'), avg_salary=Avg('expected_salary')
    ).filter(total__gte=minimum).order_by('-total', 'applied_role__name'))
    by_status = list(query.values('status').annotate(total=Count('id')).order_by('status'))
    return render(request, 'recruitment/dashboard.html', {'summary': summary, 'by_role': by_role,
        'report_form': report_form, 'minimum_candidates': minimum,
        'by_status': by_status, 'batches': ApplicationBatch.objects.select_related('uploaded_by').order_by('-created_at')[:5]})


class CandidateList(ManagerMixin, ListView):
    template_name = 'recruitment/candidate_list.html'
    context_object_name = 'candidates'
    paginate_by = 20

    def get_queryset(self):
        query = Candidate.objects.select_related('applied_role', 'screening').all()
        role_value = self.request.GET.get('role', self.request.COOKIES.get('last_role', ''))
        self.role_value = role_value if role_value.isdigit() else ''
        if self.role_value:
            query = query.filter(applied_role_id=self.role_value)
        if self.request.GET.get('status') in Candidate.Stage.values:
            query = query.filter(status=self.request.GET['status'])
        if self.request.GET.get('q'):
            query = query.filter(Q(candidate_name__icontains=self.request.GET['q']) | Q(email__icontains=self.request.GET['q']))
        batch = self.request.GET.get('batch')
        if batch is not None:
            self.request.session['current_batch'] = int(batch) if batch.isdigit() else None
        current_batch = self.request.session.get('current_batch')
        if current_batch:
            query = query.filter(batch_id=current_batch)
        return query

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(roles=JobRole.objects.all(), statuses=Candidate.Stage.choices,
                       selected_role=self.role_value, selected_status=self.request.GET.get('status', ''),
                       current_batch=self.request.session.get('current_batch'),
                       top=top_candidates(int(self.role_value)) if self.role_value else [])
        return context

    def render_to_response(self, context, **kwargs):
        response = super().render_to_response(context, **kwargs)
        response.set_cookie('last_role', self.role_value, max_age=30 * 86400, samesite='Lax', httponly=True)
        return response


class CandidateDetail(ManagerMixin, DetailView):
    queryset = Candidate.objects.select_related('applied_role', 'screening')
    template_name = 'recruitment/candidate_detail.html'
    context_object_name = 'candidate'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(status_form=ScreeningStatusForm(instance=self.object),
                       slot_form=AssignSlotForm(candidate=self.object),
                       interviews=self.object.interview_slots.select_related('interviewer').all())
        return context


@manager_required
def candidate_edit(request, pk=None):
    candidate = get_object_or_404(Candidate, pk=pk) if pk else None
    old_role_id = candidate.applied_role_id if candidate else None
    form = CandidateForm(request.POST or None, request.FILES or None, instance=candidate)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save()
                screen_candidate(saved)
        except RuntimeError as exc:
            form.add_error(None, str(exc))
        else:
            if old_role_id:
                invalidate_role_cache(old_role_id)
            messages.success(request, 'Candidate saved and screening scores refreshed.')
            return redirect('candidate-detail', pk=saved.pk)
    return render(request, 'recruitment/form.html', {'form': form, 'title': 'Edit candidate' if pk else 'Add candidate', 'candidate_form': True})


@manager_required
@require_POST
def status_edit(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    form = ScreeningStatusForm(request.POST, instance=candidate)
    if form.is_valid():
        form.save()
        invalidate_role_cache(candidate.applied_role_id)
        messages.success(request, 'Screening stage updated.')
    else:
        messages.error(request, 'Invalid screening stage.')
    return redirect('candidate-detail', pk=pk)


@manager_required
@require_POST
def rescreen(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    try:
        screen_candidate(candidate)
        messages.success(request, 'Scores recalculated. HR screening stage retained.')
    except RuntimeError as exc:
        messages.error(request, str(exc))
    return redirect('candidate-detail', pk=pk)


class CandidateDelete(ManagerMixin, DeleteView):
    model = Candidate
    template_name = 'recruitment/confirm_delete.html'
    success_url = reverse_lazy('candidate-list')

    def form_valid(self, form):
        role_id = self.object.applied_role_id
        response = super().form_valid(form)
        invalidate_role_cache(role_id)
        return response


@manager_required
def upload(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        batch = submit_upload(request.user, form.cleaned_data['file'], len(form.frame), form.cleaned_data['background'])
        request.session['current_batch'] = batch.pk
        return redirect('batch-detail', pk=batch.pk)
    return render(request, 'recruitment/form.html', {'form': form, 'title': 'Import candidates'})


@manager_required
def batch_detail(request, pk):
    batch = get_object_or_404(ApplicationBatch, pk=pk)
    return render(request, 'recruitment/batch_detail.html', {'batch': batch})


@manager_required
def batch_status(request, pk):
    batch = get_object_or_404(ApplicationBatch, pk=pk)
    return JsonResponse({field: getattr(batch, field) for field in ['status', 'total_rows', 'processed_rows', 'accepted_count', 'rejected_count', 'error']})


@manager_required
@require_POST
def retry_batch(request, pk):
    batch = get_object_or_404(ApplicationBatch, pk=pk)
    if batch.status != 'FAILED':
        return JsonResponse({'detail': 'Only failed batches can be retried.'}, status=400)
    from .tasks import process_upload
    try:
        with transaction.atomic():
            batch = ApplicationBatch.objects.select_for_update().get(pk=pk)
            if batch.status != 'FAILED':
                return JsonResponse({'detail': 'Batch already retried.'}, status=409)
            batch.status = 'QUEUED'
            batch.error = ''
            task = process_upload.delay(batch.pk)
            batch.task_id = task.id
            batch.save()
    except Exception:
        messages.error(request, 'Could not queue retry. Check Redis and Celery.')
    return redirect('batch-detail', pk=pk)


@manager_required
def batch_download(request, pk, kind):
    batch = get_object_or_404(ApplicationBatch, pk=pk)
    if kind not in ('accepted', 'rejected'):
        raise Http404
    field = getattr(batch, f'{kind}_file')
    if not field:
        raise Http404
    return FileResponse(field.open('rb'), as_attachment=True, filename=f'{kind}_rows.csv')


@manager_required
def candidate_media(request, pk, kind):
    candidate = get_object_or_404(Candidate, pk=pk)
    if kind not in ('image', 'resume_file'):
        raise Http404
    field = getattr(candidate, kind)
    if not field:
        raise Http404
    return FileResponse(field.open('rb'), as_attachment=kind != 'image')


@manager_required
@require_POST
def email_check(request):
    email = request.POST.get('email', '').strip().lower()
    from ingestion.validators import EMAIL_PATTERN
    if not EMAIL_PATTERN.fullmatch(email):
        return JsonResponse({'error': 'Enter a valid email.'}, status=400)
    query = Candidate.objects.filter(email=email)
    exclude = request.POST.get('exclude', '')
    if exclude.isdigit():
        query = query.exclude(pk=int(exclude))
    return JsonResponse({'exists': query.exists()})


@manager_required
def role_slots(request):
    role = request.GET.get('role', '')
    if not role.isdigit():
        return JsonResponse({'error': 'Choose a role.'}, status=400)
    slots = InterviewSlot.objects.filter(role_id=role, candidate__isnull=True, starts_at__gt=timezone.now()).select_related('interviewer')
    return JsonResponse({'slots': [{'id': s.pk, 'label': f'{timezone.localtime(s.starts_at):%d %b %Y %H:%M} — {s.interviewer.username}'} for s in slots]})


@manager_required
@require_POST
def assign_interview(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    form = AssignSlotForm(request.POST, candidate=candidate)
    if form.is_valid():
        try:
            assign_slot(candidate, form.cleaned_data['slot'].pk)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, 'Interview assigned.')
    else:
        messages.error(request, 'Choose an available interview slot.')
    return redirect('candidate-detail', pk=pk)


@login_required
def interviews(request):
    slots = InterviewSlot.objects.select_related('candidate', 'role', 'interviewer')
    if not request.user.can_manage_candidates:
        slots = slots.filter(interviewer=request.user)
    return render(request, 'recruitment/interviews.html', {'slots': slots})


@login_required
def feedback(request, pk):
    slot = get_object_or_404(InterviewSlot.objects.select_related('candidate', 'role'), pk=pk)
    if not request.user.is_portal_admin and (request.user.role != 'INTERVIEWER' or slot.interviewer_id != request.user.pk):
        return HttpResponseForbidden('Assigned interviewer or Admin access required.')
    if not slot.candidate_id or hasattr(slot, 'feedback'):
        messages.error(request, 'Feedback needs an assigned candidate and can only be submitted once.')
        return redirect('interviews')
    form = FeedbackForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.slot, obj.submitted_by = slot, request.user
            obj.save()
            Candidate.objects.filter(pk=slot.candidate_id).update(status=obj.recommendation)
            transaction.on_commit(lambda: invalidate_role_cache(slot.candidate.applied_role_id))
        messages.success(request, 'Feedback saved and candidate stage updated.')
        return redirect('interviews')
    return render(request, 'recruitment/form.html', {'form': form, 'title': f'Feedback for {slot.candidate.candidate_name}'})


@manager_required
def candidate_json(request, pk=None):
    if pk:
        obj = get_object_or_404(Candidate.objects.select_related('applied_role'), pk=pk)
        return JsonResponse({'id': obj.pk, 'name': obj.candidate_name, 'role': obj.applied_role.name, 'status': obj.status})
    data = list(Candidate.objects.order_by('candidate_name', 'id').values('id', 'candidate_name', 'status'))
    return JsonResponse({'candidates': data})
