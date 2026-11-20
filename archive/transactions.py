import sqlite3
from collections.abc import Callable
from typing import TypeVar


Result = TypeVar('Result')


def commit_report(
    db: sqlite3.Connection,
    write_report: Callable[[], Result],
    *,
    before_commit: Callable[[], None] | None = None,
) -> Result:
    """Commit a report in its own transaction and return only after commit."""
    if db.in_transaction:
        raise RuntimeError('signing requires an idle database connection')
    db.execute('BEGIN IMMEDIATE')
    with db:
        result = write_report()
        if before_commit is not None:
            before_commit()
    return result
