from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


Side = Literal['left', 'right']


@dataclass(frozen=True, slots=True)
class Specimen:
    piece_id: str
    side: Side


@dataclass(frozen=True, slots=True)
class BatchRoster:
    batch_id: str
    specimens: tuple[Specimen, ...]

    def side_of(self, piece_id: str) -> Side:
        for specimen in self.specimens:
            if specimen.piece_id == piece_id:
                return specimen.side
        raise KeyError(piece_id)


def ordered_piece_ids(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError('supply an ordered sequence of specimen identifiers')
    identifiers = tuple(values)
    if any(not isinstance(piece_id, str) or not piece_id.strip() for piece_id in identifiers):
        raise ValueError('specimen identifiers must be nonblank text')
    return identifiers
