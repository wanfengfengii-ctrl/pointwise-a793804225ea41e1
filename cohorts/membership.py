from collections.abc import Sequence

from .specimens import BatchRoster, ordered_piece_ids


def validate_frozen_groups(
    roster: BatchRoster,
    left: Sequence[str],
    right: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    left_ids = ordered_piece_ids(left)
    right_ids = ordered_piece_ids(right)
    if not left_ids or len(left_ids) != len(right_ids):
        raise ValueError('frozen groups must be nonempty and have equal size')
    all_ids = left_ids + right_ids
    if len(set(all_ids)) != len(all_ids):
        raise ValueError('a specimen can appear only once in a frozen version')

    for side, identifiers in (('left', left_ids), ('right', right_ids)):
        for piece_id in identifiers:
            try:
                registered_side = roster.side_of(piece_id)
            except KeyError:
                raise ValueError(f'specimen {piece_id!r} is outside batch {roster.batch_id!r}') from None
            if registered_side != side:
                raise ValueError(f'specimen {piece_id!r} is registered on the {registered_side} side')
    return left_ids, right_ids
