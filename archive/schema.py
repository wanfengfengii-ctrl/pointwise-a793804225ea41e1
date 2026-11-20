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
    pair_count: int | None = None
    probability: Fraction | None = None


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
    if snapshot.pair_count is not None:
        payload['pair_count'] = snapshot.pair_count
    if snapshot.probability is not None:
        payload['probability'] = encode_rational(snapshot.probability)
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def decode_snapshot(content: str) -> ReportSnapshot:
    payload = json.loads(content)
    probability = payload.get('probability')
    return ReportSnapshot(
        payload['basis'],
        payload['batch_id'],
        payload['freeze_id'],
        payload['plan_id'],
        payload['draw_id'],
        _decode_observation(payload['left']),
        _decode_observation(payload['right']),
        decode_rational(*payload['estimate']),
        payload.get('pair_count'),
        decode_rational(*probability) if probability is not None else None,
    )
