import sqlite3
from dataclasses import dataclass

from cohorts.freezes import get_cohort_freeze

from .repository import SamplingRepository
from .restricted import RestrictedPairPlan, get_restricted_plan


@dataclass(frozen=True, slots=True)
class FullPairPlan:
    plan_id: int
    freeze_id: int
    batch_id: str


def create_plan(db: sqlite3.Connection, freeze_id: int) -> int:
    freeze = get_cohort_freeze(db, freeze_id)
    return SamplingRepository(db).insert_plan(freeze.freeze_id, freeze.batch_id)


def get_plan(
    db: sqlite3.Connection, plan_id: int,
) -> FullPairPlan | RestrictedPairPlan:
    repository = SamplingRepository(db)
    freeze_id, batch_id = repository.load_plan(plan_id)
    if repository.is_restricted_plan(plan_id):
        probabilities = repository.load_restricted_probabilities(plan_id)
        return RestrictedPairPlan(plan_id, freeze_id, batch_id, probabilities)
    return FullPairPlan(plan_id, freeze_id, batch_id)
