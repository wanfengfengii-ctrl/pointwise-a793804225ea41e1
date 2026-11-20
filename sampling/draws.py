import sqlite3
from dataclasses import dataclass

from cohorts.freezes import get_cohort_freeze

from .plans import get_plan
from .random_port import IntegerRandomSource
from .repository import SamplingRepository
from .uniform import choose_uniform_pair


@dataclass(frozen=True, slots=True)
class Draw:
    draw_id: int
    plan_id: int
    left_piece: str
    right_piece: str


def draw_pair(db: sqlite3.Connection, plan_id: int, random_source: IntegerRandomSource) -> Draw:
    plan = get_plan(db, plan_id)
    freeze = get_cohort_freeze(db, plan.freeze_id)
    left_piece, right_piece = choose_uniform_pair(freeze.left, freeze.right, random_source)
    draw_id = SamplingRepository(db).insert_draw(plan.plan_id, left_piece, right_piece)
    return Draw(draw_id, plan.plan_id, left_piece, right_piece)


def get_draw(db: sqlite3.Connection, draw_id: int) -> Draw:
    plan_id, left_piece, right_piece = SamplingRepository(db).load_draw(draw_id)
    return Draw(draw_id, plan_id, left_piece, right_piece)
