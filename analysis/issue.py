import sqlite3
from collections.abc import Callable

from archive.reports import save_report
from archive.schema import SignedReport

from .eligibility import require_complete_draw
from .report import build_report_draft


def issue_report(
    db: sqlite3.Connection,
    draw_id: int,
    *,
    before_commit: Callable[[], None] | None = None,
) -> SignedReport:
    evidence = require_complete_draw(db, draw_id)
    return save_report(db, build_report_draft(evidence), before_commit=before_commit)
