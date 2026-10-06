"""Small reusable pieces used by the real candidate ingestion flow."""
from copy import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class BatchCounts:
    """Combine accepted/rejected outcomes without sharing mutable counters."""
    accepted: int = 0
    rejected: int = 0

    def __add__(self, other):
        if not isinstance(other, BatchCounts):
            return NotImplemented
        return BatchCounts(self.accepted + other.accepted, self.rejected + other.rejected)


def flatten_errors(value):
    """Flatten nested field errors into the reason strings written to rejected CSVs."""
    if isinstance(value, dict):
        for field, nested in value.items():
            for error in flatten_errors(nested):
                yield f'{field}: {error}'
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from flatten_errors(nested)
    else:
        yield str(value)


def progress_counter():
    count = 0

    def advance():
        nonlocal count
        count += 1
        return count
    return advance


def iter_records(columns, tuples):
    """Convert the Pandas tuple iterator to row dictionaries without another row list."""
    iterator = iter(tuples)
    while True:
        values = next(iterator, None)
        if values is None:
            break
        yield dict(zip(columns, values))


def rejected_record(raw, row_number, errors):
    # CSV/Excel fields are scalars: a shallow copy preserves the raw row while
    # adding export metadata. Nested validator policy requires a deep copy instead.
    record = copy(raw)
    record.update(row_number=row_number, errors='; '.join(flatten_errors(errors)))
    return record
