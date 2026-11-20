import sqlite3
from dataclasses import dataclass

from measurements.pairs import load_reading_pair
from measurements.readings import Reading
from sampling.draws import Draw, get_draw
from sampling.plans import FullPairPlan, get_plan


@dataclass(frozen=True, slots=True)
class IssueEvidence:
    plan: FullPairPlan
    draw: Draw
    left: Reading
    right: Reading


def require_complete_draw(db: sqlite3.Connection, draw_id: int) -> IssueEvidence:
    draw = get_draw(db, draw_id)
    plan = get_plan(db, draw.plan_id)
    pair = load_reading_pair(db, draw.draw_id)
    if pair.left is None or pair.right is None:
        raise ValueError(f'draw {draw_id} is missing a selected reading')
    return IssueEvidence(plan, draw, pair.left, pair.right)
