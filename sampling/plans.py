import sqlite3
from dataclasses import dataclass

from cohorts.freezes import get_cohort_freeze

from .repository import SamplingRepository


@dataclass(frozen=True, slots=True)
class FullPairPlan:
    plan_id: int
    freeze_id: int
    batch_id: str


def create_plan(db: sqlite3.Connection, freeze_id: int) -> int:
    freeze = get_cohort_freeze(db, freeze_id)
    return SamplingRepository(db).insert_plan(freeze.freeze_id, freeze.batch_id)


def get_plan(db: sqlite3.Connection, plan_id: int) -> FullPairPlan:
    freeze_id, batch_id = SamplingRepository(db).load_plan(plan_id)
    return FullPairPlan(plan_id, freeze_id, batch_id)
