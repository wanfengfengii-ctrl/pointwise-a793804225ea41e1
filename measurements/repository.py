import sqlite3

from .rationals import decode_rational, encode_rational
from .readings import Reading


def initialize_reading_tables(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            draw_id INTEGER NOT NULL REFERENCES draws(draw_id),
            piece_id TEXT NOT NULL,
            numerator TEXT NOT NULL,
            denominator TEXT NOT NULL,
            instrument_ref TEXT NOT NULL,
            PRIMARY KEY (draw_id, piece_id)
        )
    ''')


class ReadingRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert_reading(self, reading: Reading) -> None:
        numerator, denominator = encode_rational(reading.value)
        with self.db:
            cursor = self.db.execute(
                '''INSERT INTO readings (draw_id, piece_id, numerator, denominator, instrument_ref)
                   VALUES (?, ?, ?, ?, ?) ON CONFLICT(draw_id, piece_id) DO NOTHING''',
                (reading.draw_id, reading.piece_id, numerator, denominator, reading.instrument_ref),
            )
            if cursor.rowcount == 0:
                raise ValueError(f'draw {reading.draw_id} already has a reading for {reading.piece_id!r}')

    def load_draw_readings(self, draw_id: int) -> dict[str, Reading]:
        rows = self.db.execute(
            'SELECT piece_id, numerator, denominator, instrument_ref FROM readings WHERE draw_id = ?',
            (draw_id,),
        )
        return {
            piece_id: Reading(draw_id, piece_id, decode_rational(numerator, denominator), instrument_ref)
            for piece_id, numerator, denominator, instrument_ref in rows
        }
