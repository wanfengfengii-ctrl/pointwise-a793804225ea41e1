import json
import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from measurements.rationals import decode_rational, encode_rational


@dataclass(frozen=True, slots=True)
class ReportObservation:
    piece_id: str
    value: Fraction
    instrument_ref: str


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    basis: str
    batch_id: str
    freeze_id: int
    plan_id: int
    draw_id: int
    left: ReportObservation
    right: ReportObservation
    estimate: Fraction


@dataclass(frozen=True, slots=True)
class SignedReport:
    report_id: int
    snapshot: ReportSnapshot


def initialize_report_tables(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS signed_reports (
            report_id INTEGER PRIMARY KEY,
            draw_id INTEGER NOT NULL REFERENCES draws(draw_id),
            snapshot TEXT NOT NULL
        )
    ''')


def _encode_observation(observation: ReportObservation) -> dict:
    return {
        'piece_id': observation.piece_id,
        'value': encode_rational(observation.value),
        'instrument_ref': observation.instrument_ref,
    }


def _decode_observation(payload: dict) -> ReportObservation:
    return ReportObservation(
        payload['piece_id'], decode_rational(*payload['value']), payload['instrument_ref'],
    )


def encode_snapshot(snapshot: ReportSnapshot) -> str:
    payload = {
        'basis': snapshot.basis,
        'batch_id': snapshot.batch_id,
        'freeze_id': snapshot.freeze_id,
        'plan_id': snapshot.plan_id,
        'draw_id': snapshot.draw_id,
        'left': _encode_observation(snapshot.left),
        'right': _encode_observation(snapshot.right),
        'estimate': encode_rational(snapshot.estimate),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def decode_snapshot(content: str) -> ReportSnapshot:
    payload = json.loads(content)
    return ReportSnapshot(
        basis=payload['basis'],
        batch_id=payload['batch_id'],
        freeze_id=payload['freeze_id'],
        plan_id=payload['plan_id'],
        draw_id=payload['draw_id'],
        left=_decode_observation(payload['left']),
        right=_decode_observation(payload['right']),
        estimate=decode_rational(*payload['estimate']),
    )
