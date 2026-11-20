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
from sampling import (
    create_plan, create_restricted_plan, draw_pair, get_draw, get_plan,
)
from sampling.select import cumulative_weights


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


def run_restricted_demo():
    example_path = Path(__file__).resolve().parent.parent / 'examples' / 'restricted_pairing.json'
    example = json.loads(example_path.read_text(encoding='utf-8'))
    five = example['five_pairs']
    readings = {piece: Fraction(value) for piece, value in five['readings'].items()}

    with TemporaryDirectory(prefix='qingting-restricted-') as directory:
        path = Path(directory) / 'restricted.sqlite3'
        with closing(open_database(path)) as day_shift:
            register_batch(day_shift, five['batch_id'], five['left'], five['right'])
            freeze_id = freeze_cohorts(day_shift, five['batch_id'], five['left'], five['right'])
            plan_id = create_restricted_plan(day_shift, freeze_id, five['allowed_pairs'])
            if plan_id is None:
                raise RuntimeError('the five-pair manifest must support a restricted plan')
            plan = get_plan(day_shift, plan_id)
            distribution = {pair: str(probability) for pair, probability in plan.probabilities.items()}
            marginals = {
                piece: str(sum(
                    (probability for pair, probability in plan.probabilities.items() if piece in pair),
                    Fraction(0),
                ))
                for piece in five['left'] + five['right']
            }

            target = ('A3', 'B3')
            cumulative = cumulative_weights(plan.probabilities)
            slot = 0
            for pair, boundary in zip(plan.probabilities, cumulative):
                if pair == target:
                    break
                slot = boundary
            source = FixedPositions(slot)
            draw = draw_pair(day_shift, plan_id, source)
            record_reading(day_shift, draw.draw_id, draw.left_piece,
                           readings[draw.left_piece], f'炉台-{draw.left_piece}')
            record_reading(day_shift, draw.draw_id, draw.right_piece,
                           readings[draw.right_piece], f'炉台-{draw.right_piece}')
            report = issue_report(day_shift, draw.draw_id)
            stored_draw = get_draw(day_shift, draw.draw_id)

            three = example['three_pairs']
            register_batch(day_shift, three['batch_id'], three['left'], three['right'])
            blocked_freeze = freeze_cohorts(
                day_shift, three['batch_id'], three['left'], three['right'],
            )
            blocked = create_restricted_plan(day_shift, blocked_freeze, three['allowed_pairs'])
            blocked_plan_rows = day_shift.execute('SELECT COUNT(*) FROM plans').fetchone()[0]

        with closing(open_database(path)) as next_shift:
            received = read_report(next_shift, report.report_id)
            received_draw = get_draw(next_shift, draw.draw_id)
            reopened_plan = get_plan(next_shift, plan_id)

    if (draw.left_piece, draw.right_piece) != target or draw.probability != Fraction(1, 3):
        raise RuntimeError('controlled port did not select the forced A3-B3 pair')
    if stored_draw != draw or received_draw != draw:
        raise RuntimeError('restricted draw record was not preserved')
    if report.snapshot.estimate != Fraction(12, 5) or received != report:
        raise RuntimeError('restricted report or reopen readback diverged from 12/5')
    if received.snapshot.basis != 'v2/restricted-pair-mean-squared-color-difference':
        raise RuntimeError('restricted report basis was not frozen')
    if (received.snapshot.pair_count, received.snapshot.probability) != (5, Fraction(1, 3)):
        raise RuntimeError('restricted report did not keep M=5 and p=1/3')
    if reopened_plan.probabilities != plan.probabilities or source.bounds != [cumulative[-1]]:
        raise RuntimeError('frozen distribution or random port bounds changed after reopen')
    if set(marginals.values()) != {'1/3'}:
        raise RuntimeError('each specimen must have marginal probability 1/3')
    if blocked is not None:
        raise RuntimeError('the three-pair manifest must be rejected with None')

    expectation = Fraction(0)
    for pair, probability in plan.probabilities.items():
        left_piece, right_piece = pair
        expectation += probability * (
            (readings[left_piece] - readings[right_piece]) ** 2 / (5 * probability)
        )
    if expectation != Fraction(7, 2):
        raise RuntimeError('probability-weighted report expectation did not equal 7/2')

    emit_scenario(
        case_id='restricted_pair_demo',
        input={'allowed_pairs': five['allowed_pairs'], 'target': list(target), 'slot': slot},
        expected={'estimate': Fraction(12, 5), 'expectation': Fraction(7, 2), 'rejected_plan': None},
        actual={'estimate': report.snapshot.estimate, 'expectation': expectation,
                'rejected_plan': blocked, 'marginals': marginals,
                'distribution': {f'{left}/{right}': probability
                                 for (left, right), probability in distribution.items()}},
        downstream_expected={'report_id': report.report_id, 'probability': Fraction(1, 3),
                             'draw_id': draw.draw_id},
        downstream_actual={'report_id': received.report_id,
                           'probability': received.snapshot.probability,
                           'draw_id': received_draw.draw_id},
        code_paths=['sampling/distribution.py', 'sampling/restricted.py', 'sampling/select.py',
                    'analysis/report.py', 'archive/readback.py'],
        oracle='A3 only appears in A3-B3, whose probability is forced to 1/3; '
               '(2-0)^2/(5*1/3)=12/5 and the weighted mean of the five reports is 7/2.',
    )
    print(f"restricted plan {plan_id}: distribution={distribution}")
    print(f"restricted draw {draw.draw_id}: {draw.left_piece}-{draw.right_piece} p={draw.probability} "
          f"report={report.snapshot.estimate} (M={report.snapshot.pair_count})")
    print(f"reopen report {received.report_id}: basis={received.snapshot.basis} "
          f"weighted expectation={expectation}; infeasible manifest -> {blocked} "
          f"(plans in db={blocked_plan_rows})")


if __name__ == '__main__':
    main()
    run_restricted_demo()
