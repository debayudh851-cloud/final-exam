"""Viva walkthrough of helpers already used in ingestion; no separate implementations."""
from .processing import BatchCounts, flatten_errors, iter_records, progress_counter, rejected_record
from .validators import CandidateValidator, DEFAULT_VALIDATION_POLICY


def demonstrate():
    first, second = CandidateValidator(), CandidateValidator()
    first.policy['text_limits']['candidate_name'] = 80
    assert second.policy['text_limits']['candidate_name'] == DEFAULT_VALIDATION_POLICY['text_limits']['candidate_name'] == 150
    raw = {'email': 'INVALID', 'candidate_name': 'Original Name'}
    rejected = rejected_record(raw, 2, {'email': ['invalid format']})
    assert 'errors' not in raw and rejected['email'] == raw['email']
    advance = progress_counter()
    counts = BatchCounts(accepted=2) + BatchCounts(rejected=1)
    print({'batch_counts': {'accepted': counts.accepted, 'rejected': counts.rejected},
           'nested_errors': list(flatten_errors({'numeric': {'salary': ['negative']}})),
           'records': list(iter_records(['email'], [('a@example.test',), ('b@example.test',)])),
           'progress': [advance(), advance()], 'rejected_export': rejected,
           'validator_policy_isolated': True})


if __name__ == '__main__':
    demonstrate()
