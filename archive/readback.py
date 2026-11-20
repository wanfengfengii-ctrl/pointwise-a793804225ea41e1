import sqlite3

from .reports import load_report_snapshot
from .schema import SignedReport


def read_report(db: sqlite3.Connection, report_id: int) -> SignedReport:
    return SignedReport(report_id, load_report_snapshot(db, report_id))
