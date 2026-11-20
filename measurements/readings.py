from dataclasses import dataclass
from fractions import Fraction

from .rationals import parse_color_value


@dataclass(frozen=True, slots=True)
class Reading:
    draw_id: int
    piece_id: str
    value: Fraction
    instrument_ref: str


def make_reading(
    draw_id: int,
    piece_id: str,
    value: Fraction | int | str,
    instrument_ref: str,
) -> Reading:
    if not isinstance(instrument_ref, str) or not instrument_ref.strip():
        raise ValueError('instrument reference must be nonblank text')
    return Reading(draw_id, piece_id, parse_color_value(value), instrument_ref)
