import logging
from django.core.cache import cache
from django.db import transaction
from recruitment.models import Candidate, ScreeningResult
from .ml import predict, ModelUnavailable
from .nlp import analyze_resume

logger = logging.getLogger('portal.audit')


def invalidate_role_cache(role_id):
    try:
        cache.delete(f'top_candidates:{role_id}')
    except Exception:
        logger.warning('Redis unavailable during cache invalidation')


def top_candidates(role_id):
    key = f'top_candidates:{role_id}'
    try:
        cached = cache.get(key)
        if cached is not None:
            return cached
    except Exception:
        logger.warning('Redis cache unavailable; reading database')
    result = list(Candidate.objects.filter(applied_role_id=role_id, status='SHORTLISTED')
                  .order_by('-screening__ml_probability', '-screening__keyword_score')
                  .values('id', 'candidate_name', 'screening__ml_probability')[:10])
    try:
        cache.set(key, result, timeout=300)
    except Exception:
        pass
    return result


def screen_candidate(candidate):
    role = candidate.applied_role
    reasons = []
    if candidate.experience_months < role.min_experience_months:
        reasons.append('Experience below role minimum')
    if candidate.notice_period_days > role.max_notice_period_days:
        reasons.append('Notice period exceeds role limit')
    if candidate.expected_salary > role.max_salary:
        reasons.append('Expected salary exceeds role budget')
    nlp = analyze_resume(candidate.resume_text, role.required_skills)
    try:
        prediction = predict({'experience_months': candidate.experience_months, 'notice_period_days': candidate.notice_period_days,
                              'expected_salary': candidate.expected_salary, 'skills': candidate.skills, 'applied_role': role.name})
    except ModelUnavailable:
        prediction = {'probability': None, 'model_version': ''}
    result, _ = ScreeningResult.objects.update_or_create(candidate=candidate, defaults={
        'rule_passed': not reasons, 'rule_reasons': reasons, 'ml_probability': prediction['probability'],
        'model_version': prediction['model_version'], 'keyword_score': nlp['keyword_score'],
        'matched_skills': nlp['matched_skills'], 'pos_tags': nlp['pos_tags']})
    transaction.on_commit(lambda: invalidate_role_cache(candidate.applied_role_id))
    return result
