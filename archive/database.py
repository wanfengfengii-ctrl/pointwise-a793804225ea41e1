import sqlite3
from os import PathLike

from cohorts.repository import initialize_cohort_tables
from measurements.repository import initialize_reading_tables
from sampling.repository import initialize_sampling_tables

from .schema import initialize_report_tables


def open_database(path: str | PathLike[str]) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    try:
        db.execute('PRAGMA foreign_keys = ON')
        with db:
            db.execute('BEGIN')
            initialize_cohort_tables(db)
            initialize_sampling_tables(db)
            initialize_reading_tables(db)
            initialize_report_tables(db)
    except BaseException:
        db.close()
        raise
    return db
