import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from cohorts.freezes import get_cohort_freeze

from .distribution import build_restricted_distribution
from .repository import SamplingRepository


@dataclass(frozen=True, slots=True)
class RestrictedPairPlan:
    plan_id: int
    freeze_id: int
    batch_id: str
    probabilities: dict[tuple[str, str], Fraction]


def _validate_allowed_pairs(
    allowed_pairs: Sequence[Sequence[str]],
    left: tuple[str, ...],
    right: tuple[str, ...],
) -> list[tuple[str, str]]:
    if isinstance(allowed_pairs, (str, bytes, bytearray)) or not isinstance(allowed_pairs, Sequence):
        raise ValueError('allowed pairs must be a nonempty ordered sequence')
    pairs: list[tuple[str, str]] = []
    for pair in allowed_pairs:
        if isinstance(pair, (str, bytes, bytearray)) or not isinstance(pair, Sequence) or len(pair) != 2:
            raise ValueError('each allowed pair must name exactly two specimens, left then right')
        left_piece, right_piece = pair
        if not isinstance(left_piece, str) or not isinstance(right_piece, str):
            raise ValueError('pair specimen identifiers must be text')
        if left_piece not in left:
            raise ValueError(f'left specimen {left_piece!r} is outside the frozen left group')
        if right_piece not in right:
            raise ValueError(f'right specimen {right_piece!r} is outside the frozen right group')
        ordered = (left_piece, right_piece)
        if ordered in pairs:
            raise ValueError(f'allowed pair {ordered!r} is duplicated')
        pairs.append(ordered)
    if not pairs:
        raise ValueError('at least one allowed pair is required')
    return pairs


def create_restricted_plan(
    db: sqlite3.Connection,
    freeze_id: int,
    allowed_pairs: Sequence[Sequence[str]],
) -> int | None:
    freeze = get_cohort_freeze(db, freeze_id)
    size = len(freeze.left)
    pairs = _validate_allowed_pairs(allowed_pairs, freeze.left, freeze.right)
    left_position = {piece: position for position, piece in enumerate(freeze.left)}
    right_position = {piece: position for position, piece in enumerate(freeze.right)}
    edges = [(left_position[left_piece], right_position[right_piece])
             for left_piece, right_piece in pairs]

    edge_distribution = build_restricted_distribution(edges, size)
    if edge_distribution is None:
        return None

    probabilities = {
        pair: edge_distribution[edge]
        for pair, edge in zip(pairs, edges, strict=True)
    }
    return SamplingRepository(db).insert_restricted_plan(
        freeze.freeze_id, freeze.batch_id, probabilities,
    )


def get_restricted_plan(db: sqlite3.Connection, plan_id: int) -> RestrictedPairPlan:
    freeze_id, batch_id = SamplingRepository(db).load_plan(plan_id)
    probabilities = SamplingRepository(db).load_restricted_probabilities(plan_id)
    return RestrictedPairPlan(plan_id, freeze_id, batch_id, probabilities)
