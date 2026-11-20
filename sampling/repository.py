import sqlite3


def initialize_sampling_tables(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS plans (
            plan_id INTEGER PRIMARY KEY,
            freeze_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            FOREIGN KEY (freeze_id, batch_id) REFERENCES cohort_freezes(freeze_id, batch_id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS draws (
            draw_id INTEGER PRIMARY KEY,
            plan_id INTEGER NOT NULL REFERENCES plans(plan_id),
            left_piece TEXT NOT NULL,
            right_piece TEXT NOT NULL,
            CHECK (left_piece <> right_piece)
        )
    ''')


def _load_row(db: sqlite3.Connection, query: str, fixed_id: int) -> tuple:
    if type(fixed_id) is not int or not 0 < fixed_id <= 2**63 - 1:
        raise KeyError(fixed_id)
    row = db.execute(query, (fixed_id,)).fetchone()
    if row is None:
        raise KeyError(fixed_id)
    return row


class SamplingRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert_plan(self, freeze_id: int, batch_id: str) -> int:
        with self.db:
            cursor = self.db.execute(
                'INSERT INTO plans (freeze_id, batch_id) VALUES (?, ?)', (freeze_id, batch_id),
            )
        return cursor.lastrowid

    def load_plan(self, plan_id: int) -> tuple[int, str]:
        return _load_row(self.db, 'SELECT freeze_id, batch_id FROM plans WHERE plan_id = ?', plan_id)

    def insert_draw(self, plan_id: int, left_piece: str, right_piece: str) -> int:
        with self.db:
            cursor = self.db.execute(
                'INSERT INTO draws (plan_id, left_piece, right_piece) VALUES (?, ?, ?)',
                (plan_id, left_piece, right_piece),
            )
        return cursor.lastrowid

    def load_draw(self, draw_id: int) -> tuple[int, str, str]:
        return _load_row(
            self.db, 'SELECT plan_id, left_piece, right_piece FROM draws WHERE draw_id = ?', draw_id,
        )
