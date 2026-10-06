"""Shared CSV/API validators: normalize first, collect all useful row errors."""
import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from .processing import flatten_errors

FIELDS = ('candidate_name', 'email', 'phone', 'college', 'applied_role', 'skills',
          'experience_months', 'notice_period_days', 'expected_salary', 'resume_text',
          'portfolio_url', 'historical_selection_status')
REQUIRED_COLUMNS = frozenset(FIELDS) - {'resume_text', 'portfolio_url'}
HISTORY = frozenset({'', 'SELECTED', 'REJECTED', 'WAITLISTED', 'SHORTLISTED', 'NEW'})
EMAIL_PATTERN = re.compile(r'^[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$')
PHONE_PATTERN = re.compile(r'^\+?[1-9][0-9]{9,14}$')
ROLE_CODE_PATTERN = re.compile(r'^[A-Z][A-Z0-9_-]{1,19}$')
# Global configuration is read, never modified, by each validator instance.
DEFAULT_VALIDATION_POLICY = {
    'text_limits': {'candidate_name': 150, 'college': 200, 'portfolio_url': 200},
    'numeric_limits': {'experience_months': 600, 'notice_period_days': 365, 'expected_salary': '9999999999.99'},
}


class InputFileError(ValueError):
    pass


class RowValidationError(ValueError):
    def __init__(self, errors):
        self.errors = list(flatten_errors(errors))
        super().__init__('; '.join(self.errors))


def normalize_skills(value):
    return ', '.join(sorted({s.strip().lower() for s in re.split(r'[,;|]', str(value)) if s.strip()}))


class BaseValidator:
    def clean_text(self, value):
        return ' '.join(str('' if value is None else value).strip().split())


class CandidateValidator(BaseValidator):
    def __init__(self, policy=None):
        # Isolate nested configuration for every upload/API/form validator.
        self.policy = deepcopy(DEFAULT_VALIDATION_POLICY if policy is None else policy)

    def validate(self, row, roles):
        clean = {key: self.clean_text(row.get(key, '')) for key in FIELDS}
        errors = {}

        def error(field, reason):
            errors.setdefault(field, []).append(reason)

        clean['candidate_name'] = clean['candidate_name'].title()
        clean['email'] = clean['email'].lower().removeprefix('mailto:')
        clean['phone'] = re.sub(r'[\s()-]', '', clean['phone']).removesuffix('.0')
        # Convert an international dial-out prefix into the stored + form.
        if clean['phone'][:2] == '00':
            clean['phone'] = '+' + clean['phone'][2:]
        elif clean['phone'] and clean['phone'][0] == '＋':
            clean['phone'] = '+' + clean['phone'][1:]
        clean['skills'] = normalize_skills(clean['skills'])
        clean['resume_text'] = str(row.get('resume_text', '') or '').strip()
        clean['historical_selection_status'] = clean['historical_selection_status'].upper()
        for field in ('candidate_name', 'email', 'phone', 'applied_role', 'skills'):
            if not clean[field]:
                error(field, 'required')
        if not EMAIL_PATTERN.fullmatch(clean['email']) or len(clean['email']) > 254:
            error('email', 'invalid format')
        if not PHONE_PATTERN.fullmatch(clean['phone']):
            error('phone', 'use 10–15 digits with an optional leading +')
        for field, limit in self.policy['text_limits'].items():
            if len(clean[field]) > limit:
                error(field, f'maximum {limit} characters')
        role = roles.get(clean['applied_role'].casefold())
        if role is None:
            error('applied_role', 'unknown role name or code')
        for field, max_value in self.policy['numeric_limits'].items():
            try:
                value = Decimal(clean[field])
                if not value.is_finite() or value < 0 or value > Decimal(str(max_value)):
                    raise InvalidOperation
                if field != 'expected_salary' and value != value.to_integral_value():
                    raise InvalidOperation
                if field == 'expected_salary' and value.as_tuple().exponent < -2:
                    raise InvalidOperation
                clean[field] = value if field == 'expected_salary' else int(value)
            except (InvalidOperation, ValueError):
                error(field, f'invalid nonnegative number or exceeds {max_value}')
        if clean['portfolio_url']:
            try:
                URLValidator(schemes=['https', 'http'])(clean['portfolio_url'])
            except ValidationError:
                error('portfolio_url', 'invalid HTTP(S) URL')
        if clean['historical_selection_status'] not in HISTORY:
            error('historical_selection_status', 'unsupported status')
        if errors:
            raise RowValidationError(errors)
        clean['applied_role'] = role
        return clean
