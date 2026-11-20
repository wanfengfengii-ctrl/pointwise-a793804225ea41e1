import sqlite3
from collections.abc import Sequence

from .repository import CohortRepository
from .specimens import BatchRoster, Specimen, ordered_piece_ids


def register_batch(
    db: sqlite3.Connection,
    batch_id: str,
    left: Sequence[str],
    right: Sequence[str],
) -> BatchRoster:
    if not isinstance(batch_id, str) or not batch_id.strip():
        raise ValueError('batch identifier must be nonblank text')
    left_ids = ordered_piece_ids(left)
    right_ids = ordered_piece_ids(right)
    if not left_ids or not right_ids:
        raise ValueError('the batch roster must name candidates on both sides')
    all_ids = left_ids + right_ids
    if len(set(all_ids)) != len(all_ids):
        raise ValueError('a specimen can appear only once in a batch roster')
    specimens = (
        tuple(Specimen(piece_id, 'left') for piece_id in left_ids)
        + tuple(Specimen(piece_id, 'right') for piece_id in right_ids)
    )
    roster = BatchRoster(batch_id, specimens)
    CohortRepository(db).insert_batch(roster)
    return roster
