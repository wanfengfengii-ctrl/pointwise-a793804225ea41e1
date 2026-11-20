import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from .membership import validate_frozen_groups
from .repository import CohortRepository


@dataclass(frozen=True, slots=True)
class CohortFreeze:
    freeze_id: int
    batch_id: str
    left: tuple[str, ...]
    right: tuple[str, ...]


def freeze_cohorts(
    db: sqlite3.Connection,
    batch_id: str,
    left: Sequence[str],
    right: Sequence[str],
) -> int:
    repository = CohortRepository(db)
    roster = repository.get_roster(batch_id)
    left_ids, right_ids = validate_frozen_groups(roster, left, right)
    return repository.insert_freeze(roster.batch_id, left_ids, right_ids)


def get_cohort_freeze(db: sqlite3.Connection, freeze_id: int) -> CohortFreeze:
    batch_id, left, right = CohortRepository(db).load_freeze(freeze_id)
    return CohortFreeze(freeze_id, batch_id, left, right)
