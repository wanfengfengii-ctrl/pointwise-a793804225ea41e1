import sqlite3
from collections.abc import Callable

from .schema import ReportSnapshot, SignedReport, decode_snapshot, encode_snapshot
from .transactions import commit_report


def save_report(
    db: sqlite3.Connection,
    snapshot: ReportSnapshot,
    *,
    before_commit: Callable[[], None] | None = None,
) -> SignedReport:
    content = encode_snapshot(snapshot)

    def insert() -> int:
        cursor = db.execute(
            'INSERT INTO signed_reports (draw_id, snapshot) VALUES (?, ?)', (snapshot.draw_id, content),
        )
        return cursor.lastrowid

    report_id = commit_report(db, insert, before_commit=before_commit)
    return SignedReport(report_id, snapshot)


def load_report_snapshot(db: sqlite3.Connection, report_id: int) -> ReportSnapshot:
    if type(report_id) is not int or not 0 < report_id <= 2**63 - 1:
        raise KeyError(report_id)
    row = db.execute(
        'SELECT snapshot FROM signed_reports WHERE report_id = ?', (report_id,),
    ).fetchone()
    if row is None:
        raise KeyError(report_id)
    return decode_snapshot(row[0])
