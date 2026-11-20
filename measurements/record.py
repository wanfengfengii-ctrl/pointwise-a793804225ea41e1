import sqlite3
from fractions import Fraction

from sampling.draws import get_draw

from .readings import Reading, make_reading
from .repository import ReadingRepository


def record_reading(
    db: sqlite3.Connection,
    draw_id: int,
    piece_id: str,
    value: Fraction | int | str,
    instrument_ref: str,
) -> Reading:
    draw = get_draw(db, draw_id)
    if piece_id not in (draw.left_piece, draw.right_piece):
        raise ValueError(f'specimen {piece_id!r} was not selected in draw {draw_id}')
    reading = make_reading(draw.draw_id, piece_id, value, instrument_ref)
    ReadingRepository(db).insert_reading(reading)
    return reading
