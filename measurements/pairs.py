import sqlite3
from dataclasses import dataclass

from sampling.draws import get_draw

from .readings import Reading
from .repository import ReadingRepository


@dataclass(frozen=True, slots=True)
class ReadingPair:
    left: Reading | None
    right: Reading | None

    def is_complete(self) -> bool:
        return self.left is not None and self.right is not None


def load_reading_pair(db: sqlite3.Connection, draw_id: int) -> ReadingPair:
    draw = get_draw(db, draw_id)
    readings = ReadingRepository(db).load_draw_readings(draw.draw_id)
    return ReadingPair(readings.get(draw.left_piece), readings.get(draw.right_piece))
