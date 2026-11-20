import sqlite3

from .specimens import BatchRoster, Specimen


def initialize_cohort_tables(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            batch_id TEXT PRIMARY KEY NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS specimens (
            batch_id TEXT NOT NULL REFERENCES batches(batch_id),
            piece_id TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('left', 'right')),
            PRIMARY KEY (batch_id, piece_id),
            UNIQUE (batch_id, piece_id, side)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS cohort_freezes (
            freeze_id INTEGER PRIMARY KEY,
            batch_id TEXT NOT NULL REFERENCES batches(batch_id),
            UNIQUE (freeze_id, batch_id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS frozen_pieces (
            freeze_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('left', 'right')),
            position INTEGER NOT NULL CHECK (position >= 0),
            piece_id TEXT NOT NULL,
            PRIMARY KEY (freeze_id, side, position),
            UNIQUE (freeze_id, piece_id),
            FOREIGN KEY (freeze_id, batch_id) REFERENCES cohort_freezes(freeze_id, batch_id),
            FOREIGN KEY (batch_id, piece_id, side) REFERENCES specimens(batch_id, piece_id, side)
        )
    ''')


class CohortRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert_batch(self, roster: BatchRoster) -> None:
        with self.db:
            insert = self.db.execute(
                'INSERT INTO batches (batch_id) VALUES (?) ON CONFLICT(batch_id) DO NOTHING',
                (roster.batch_id,),
            )
            if insert.rowcount == 0:
                raise ValueError(f'batch {roster.batch_id!r} is already registered')
            self.db.executemany(
                'INSERT INTO specimens (batch_id, piece_id, side) VALUES (?, ?, ?)',
                ((roster.batch_id, specimen.piece_id, specimen.side) for specimen in roster.specimens),
            )

    def get_roster(self, batch_id: str) -> BatchRoster:
        if not isinstance(batch_id, str):
            raise KeyError(batch_id)
        rows = self.db.execute(
            'SELECT piece_id, side FROM specimens WHERE batch_id = ? ORDER BY side, piece_id',
            (batch_id,),
        ).fetchall()
        if not rows:
            raise KeyError(batch_id)
        return BatchRoster(batch_id, tuple(Specimen(piece_id, side) for piece_id, side in rows))

    def insert_freeze(self, batch_id: str, left: tuple[str, ...], right: tuple[str, ...]) -> int:
        with self.db:
            cursor = self.db.execute('INSERT INTO cohort_freezes (batch_id) VALUES (?)', (batch_id,))
            freeze_id = cursor.lastrowid
            self.db.executemany(
                '''INSERT INTO frozen_pieces (freeze_id, batch_id, side, position, piece_id)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    (freeze_id, batch_id, side, position, piece_id)
                    for side, pieces in (('left', left), ('right', right))
                    for position, piece_id in enumerate(pieces)
                ),
            )
        return freeze_id

    def load_freeze(self, freeze_id: int) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        if type(freeze_id) is not int or not 0 < freeze_id <= 2**63 - 1:
            raise KeyError(freeze_id)
        header = self.db.execute(
            'SELECT batch_id FROM cohort_freezes WHERE freeze_id = ?', (freeze_id,),
        ).fetchone()
        if header is None:
            raise KeyError(freeze_id)
        groups = {'left': [], 'right': []}
        for side, piece_id in self.db.execute(
            'SELECT side, piece_id FROM frozen_pieces WHERE freeze_id = ? ORDER BY side, position',
            (freeze_id,),
        ):
            groups[side].append(piece_id)
        return header[0], tuple(groups['left']), tuple(groups['right'])
