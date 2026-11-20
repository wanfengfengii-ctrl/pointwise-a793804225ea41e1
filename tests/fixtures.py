import json
import unittest
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis import issue_report
from archive import open_database, read_report
from cohorts import freeze_cohorts, register_batch
from measurements import record_reading
from sampling import create_plan, draw_pair


BATCH_ID = 'QINGTING-17'
LEFT = ('L1', 'L2')
RIGHT = ('R1', 'R2')
ALL_LEFT = LEFT + ('L3',)
ALL_RIGHT = RIGHT + ('R3',)


class FixedPositions:
    def __init__(self, *positions):
        self._positions = iter(positions)
        self.bounds = []

    def randbelow(self, upper):
        self.bounds.append(upper)
        return next(self._positions)


def register_fixture(db):
    return register_batch(db, BATCH_ID, ALL_LEFT, ALL_RIGHT)


def prepare_fixture(db):
    register_fixture(db)
    freeze_id = freeze_cohorts(db, BATCH_ID, LEFT, RIGHT)
    return freeze_id, create_plan(db, freeze_id)


def report_count(db):
    return db.execute('SELECT COUNT(*) FROM signed_reports').fetchone()[0]


def emit_scenario(*, case_id, input, expected, actual, downstream_expected, downstream_actual, code_paths, oracle):
    evidence = {
        'case_id': case_id,
        'input': input,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': code_paths,
        'oracle': oracle,
    }
    print('POINTWISE_SCENARIO ' + json.dumps(evidence, ensure_ascii=False, default=str))


class DatabaseCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='qingting-test-')
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'laboratory.sqlite3'
        self.db = open_database(self.path)
        self.addCleanup(self.db.close)


def main():
    with TemporaryDirectory(prefix='qingting-demo-') as directory:
        path = Path(directory) / 'laboratory.sqlite3'
        with closing(open_database(path)) as day_shift:
            freeze_id, plan_id = prepare_fixture(day_shift)
            source = FixedPositions(1, 0)
            draw = draw_pair(day_shift, plan_id, source)
            right = record_reading(day_shift, draw.draw_id, draw.right_piece, '1/2', '炉台-右')
            left = record_reading(day_shift, draw.draw_id, draw.left_piece, 0, '炉台-左')
            report = issue_report(day_shift, draw.draw_id)
            freeze_cohorts(day_shift, BATCH_ID, ('L3', 'L1'), ('R3', 'R2'))
        with closing(open_database(path)) as next_shift:
            received = read_report(next_shift, report.report_id)

    expected = {
        'batch_id': BATCH_ID,
        'freeze_id': freeze_id,
        'plan_id': plan_id,
        'draw_id': draw.draw_id,
        'pieces': ['L2', 'R1'],
        'values': [Fraction(0), Fraction(1, 2)],
        'instruments': ['炉台-左', '炉台-右'],
        'estimate': Fraction(1, 4),
        'basis': 'v1/full-pair-mean-squared-color-difference',
    }
    snapshot = report.snapshot
    actual = {
        'batch_id': snapshot.batch_id,
        'freeze_id': snapshot.freeze_id,
        'plan_id': snapshot.plan_id,
        'draw_id': snapshot.draw_id,
        'pieces': [snapshot.left.piece_id, snapshot.right.piece_id],
        'values': [snapshot.left.value, snapshot.right.value],
        'instruments': [snapshot.left.instrument_ref, snapshot.right.instrument_ref],
        'estimate': snapshot.estimate,
        'basis': snapshot.basis,
    }
    if actual != expected or received != report or source.bounds != [2, 2]:
        raise RuntimeError('demo did not reproduce the hand-calculated result and archive')
    emit_scenario(
        case_id='exact_readback',
        input={'left_group': LEFT, 'right_group': RIGHT, 'positions': [1, 0], 'arrival': [right.value, left.value]},
        expected=expected,
        actual=actual,
        downstream_expected={'report_id': report.report_id, 'freeze_id': freeze_id, 'estimate': Fraction(1, 4)},
        downstream_actual={'report_id': received.report_id, 'freeze_id': received.snapshot.freeze_id,
                           'estimate': received.snapshot.estimate},
        code_paths=['cohorts/freezes.py', 'sampling/draws.py', 'measurements/record.py',
                    'analysis/contrast.py', 'archive/readback.py'],
        oracle='Positions 1 and 0 choose L2 and R1. Hand calculation: (0 - 1/2)^2 = 1/4.',
    )


if __name__ == '__main__':
    main()
