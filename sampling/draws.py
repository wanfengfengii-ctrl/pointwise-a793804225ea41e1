import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from cohorts.freezes import get_cohort_freeze

from .plans import get_plan
from .random_port import IntegerRandomSource
from .repository import SamplingRepository
from .restricted import RestrictedPairPlan
from .select import choose_restricted_pair
from .uniform import choose_uniform_pair


@dataclass(frozen=True, slots=True)
class Draw:
    draw_id: int
    plan_id: int
    left_piece: str
    right_piece: str


@dataclass(frozen=True, slots=True)
class RestrictedDraw:
    draw_id: int
    plan_id: int
    left_piece: str
    right_piece: str
    probability: Fraction


def draw_pair(db: sqlite3.Connection, plan_id: int, random_source: IntegerRandomSource):
    plan = get_plan(db, plan_id)
    if isinstance(plan, RestrictedPairPlan):
        left_piece, right_piece, probability = choose_restricted_pair(
            plan.probabilities, random_source,
        )
        draw_id = SamplingRepository(db).insert_draw(plan.plan_id, left_piece, right_piece)
        return RestrictedDraw(draw_id, plan.plan_id, left_piece, right_piece, probability)

    freeze = get_cohort_freeze(db, plan.freeze_id)
    left_piece, right_piece = choose_uniform_pair(freeze.left, freeze.right, random_source)
    draw_id = SamplingRepository(db).insert_draw(plan.plan_id, left_piece, right_piece)
    return Draw(draw_id, plan.plan_id, left_piece, right_piece)


def get_draw(db: sqlite3.Connection, draw_id: int):
    plan_id, left_piece, right_piece = SamplingRepository(db).load_draw(draw_id)
    repository = SamplingRepository(db)
    if repository.is_restricted_plan(plan_id):
        probability = repository.load_restricted_probabilities(plan_id)[(left_piece, right_piece)]
        return RestrictedDraw(draw_id, plan_id, left_piece, right_piece, probability)
    return Draw(draw_id, plan_id, left_piece, right_piece)
