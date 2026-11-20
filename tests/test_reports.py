from contextlib import closing
from fractions import Fraction

from analysis import issue_report
from archive import open_database, read_report
from archive.schema import ReportObservation, ReportSnapshot
from cohorts import freeze_cohorts, get_cohort_freeze
from cohorts.repository import CohortRepository
from measurements import load_reading_pair, record_reading
from sampling import create_plan, draw_pair, get_draw, get_plan

from tests.fixtures import (
    ALL_LEFT, ALL_RIGHT, BATCH_ID, LEFT, RIGHT, DatabaseCase, FixedPositions,
    emit_scenario, prepare_fixture, report_count,
)


class ReportTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        self.freeze_id, self.plan_id = prepare_fixture(self.db)

    def complete_draw(self):
        draw = draw_pair(self.db, self.plan_id, FixedPositions(1, 0))
        record_reading(self.db, draw.draw_id, draw.right_piece, '1/2', 'right-1')
        record_reading(self.db, draw.draw_id, draw.left_piece, 0, 'left-1')
        return draw

    def expected_snapshot(self, draw_id):
        return ReportSnapshot(
            basis='v1/full-pair-mean-squared-color-difference',
            batch_id=BATCH_ID,
            freeze_id=self.freeze_id,
            plan_id=self.plan_id,
            draw_id=draw_id,
            left=ReportObservation('L2', Fraction(0), 'left-1'),
            right=ReportObservation('R1', Fraction(1, 2), 'right-1'),
            estimate=Fraction(1, 4),
        )

    def test_no_report_from_one_reading(self):
        for piece_id in ('R1', 'L2'):
            with self.subTest(piece_id=piece_id):
                draw = draw_pair(self.db, self.plan_id, FixedPositions(1, 0))
                record_reading(self.db, draw.draw_id, piece_id, '1/2', 'one-instrument')
                with self.assertRaises(ValueError):
                    issue_report(self.db, draw.draw_id)
                self.assertEqual(report_count(self.db), 0)

    def test_isolated_draws(self):
        earlier = self.complete_draw()
        later = draw_pair(self.db, self.plan_id, FixedPositions(1, 0))
        self.assertNotEqual(earlier.draw_id, later.draw_id)
        self.assertEqual((earlier.left_piece, earlier.right_piece), (later.left_piece, later.right_piece))
        record_reading(self.db, later.draw_id, later.right_piece, 3, 'later-right')
        with self.assertRaises(ValueError):
            issue_report(self.db, later.draw_id)
        self.assertEqual(report_count(self.db), 0)
        record_reading(self.db, later.draw_id, later.left_piece, 1, 'later-left')
        report = issue_report(self.db, later.draw_id)
        self.assertEqual((report.snapshot.draw_id, report.snapshot.estimate), (later.draw_id, Fraction(4)))
        self.assertEqual(report.snapshot.left.instrument_ref, 'later-left')
        self.assertEqual(issue_report(self.db, earlier.draw_id).snapshot.estimate, Fraction(1, 4))

    def test_unknown_draw(self):
        with self.assertRaises(KeyError):
            issue_report(self.db, 999)
        self.assertEqual(report_count(self.db), 0)

    def test_exact_report_survives_reopen(self):
        draw = self.complete_draw()
        expected = self.expected_snapshot(draw.draw_id)
        signed = issue_report(self.db, draw.draw_id)
        self.assertEqual(signed.snapshot, expected)
        revision = freeze_cohorts(self.db, BATCH_ID, ('L3', 'L1'), ('R3', 'R2'))
        create_plan(self.db, revision)
        self.db.close()
        with closing(open_database(self.path)) as reopened:
            received = read_report(reopened, signed.report_id)
            self.assertEqual(received, signed)
            self.assertEqual(received.snapshot, expected)
            self.assertEqual(get_draw(reopened, received.snapshot.draw_id), draw)
            self.assertEqual(get_plan(reopened, received.snapshot.plan_id).freeze_id, self.freeze_id)
        emit_scenario(
            case_id='exact_readback',
            input={'positions': [1, 0], 'values': [Fraction(0), Fraction(1, 2)], 'revision': revision},
            expected=expected.estimate,
            actual=signed.snapshot.estimate,
            downstream_expected={'freeze_id': self.freeze_id, 'draw_id': draw.draw_id, 'estimate': expected.estimate},
            downstream_actual={'freeze_id': received.snapshot.freeze_id, 'draw_id': received.snapshot.draw_id,
                               'estimate': received.snapshot.estimate},
            code_paths=['analysis/eligibility.py', 'analysis/contrast.py', 'archive/reports.py', 'archive/readback.py'],
            oracle='The selected L2 and R1 readings are 0 and 1/2, whose squared difference is 1/4.',
        )

    def test_fixed_report_number(self):
        old_draw = self.complete_draw()
        old = issue_report(self.db, old_draw.draw_id)
        revision = freeze_cohorts(self.db, BATCH_ID, ('L3',), ('R3',))
        new_plan = create_plan(self.db, revision)
        new_draw = draw_pair(self.db, new_plan, FixedPositions(0, 0))
        record_reading(self.db, new_draw.draw_id, 'L3', 3, 'new-left')
        record_reading(self.db, new_draw.draw_id, 'R3', 1, 'new-right')
        new = issue_report(self.db, new_draw.draw_id)
        self.assertNotEqual(new.report_id, old.report_id)
        self.db.close()
        expected_new = ReportSnapshot(
            'v1/full-pair-mean-squared-color-difference', BATCH_ID, revision, new_plan, new_draw.draw_id,
            ReportObservation('L3', Fraction(3), 'new-left'),
            ReportObservation('R3', Fraction(1), 'new-right'), Fraction(4),
        )
        with closing(open_database(self.path)) as reopened:
            self.assertEqual(read_report(reopened, old.report_id), old)
            self.assertEqual(old.snapshot, self.expected_snapshot(old_draw.draw_id))
            self.assertEqual(read_report(reopened, new.report_id), new)
            self.assertEqual(new.snapshot, expected_new)

    def test_unknown_report(self):
        draw = self.complete_draw()
        report = issue_report(self.db, draw.draw_id)
        with self.assertRaises(KeyError):
            read_report(self.db, report.report_id + 1)
        self.assertEqual(report_count(self.db), 1)

    def test_failed_commit_can_retry(self):
        draw = self.complete_draw()
        with closing(open_database(self.path)) as observer:
            def fail_before_commit():
                self.assertTrue(self.db.in_transaction)
                self.assertEqual(report_count(self.db), 1)
                self.assertEqual(report_count(observer), 0)
                raise OSError('commit interrupted at the furnace desk')

            with self.assertRaisesRegex(OSError, 'commit interrupted'):
                issue_report(self.db, draw.draw_id, before_commit=fail_before_commit)
            self.assertFalse(self.db.in_transaction)
            self.assertEqual(report_count(self.db), 0)
            self.assertEqual(report_count(observer), 0)
            self.assertTrue(load_reading_pair(observer, draw.draw_id).is_complete())
            report = issue_report(self.db, draw.draw_id)
            self.assertEqual(report_count(observer), 1)
            self.assertEqual(read_report(observer, report.report_id), report)
        self.db.close()
        with closing(open_database(self.path)) as reopened:
            self.assertEqual(report_count(reopened), 1)
            self.assertEqual(read_report(reopened, report.report_id).snapshot, self.expected_snapshot(draw.draw_id))

    def test_repeat_initialization(self):
        draw = self.complete_draw()
        report = issue_report(self.db, draw.draw_id)
        self.db.close()
        for reopening in range(2):
            with self.subTest(reopening=reopening), closing(open_database(self.path)) as reopened:
                self.assertEqual(reopened.execute('PRAGMA foreign_keys').fetchone(), (1,))
                roster = CohortRepository(reopened).get_roster(BATCH_ID)
                self.assertEqual(tuple(piece.piece_id for piece in roster.specimens), ALL_LEFT + ALL_RIGHT)
                freeze = get_cohort_freeze(reopened, self.freeze_id)
                self.assertEqual((freeze.left, freeze.right), (LEFT, RIGHT))
                self.assertEqual(get_plan(reopened, self.plan_id).freeze_id, self.freeze_id)
                self.assertEqual(get_draw(reopened, draw.draw_id), draw)
                pair = load_reading_pair(reopened, draw.draw_id)
                self.assertEqual((pair.left.value, pair.right.value), (Fraction(0), Fraction(1, 2)))
                self.assertEqual(read_report(reopened, report.report_id), report)
        with closing(open_database(self.path)) as reopened:
            following_draw = draw_pair(reopened, self.plan_id, FixedPositions(0, 1))
            record_reading(reopened, following_draw.draw_id, 'L1', '1/3', 'second-left')
            record_reading(reopened, following_draw.draw_id, 'R2', 0, 'second-right')
            following_report = issue_report(reopened, following_draw.draw_id)
            self.assertEqual(following_report.snapshot.estimate, Fraction(1, 9))
            self.assertEqual(report_count(reopened), 2)
            self.assertEqual(read_report(reopened, report.report_id), report)

    def test_all_pairs_mean(self):
        values = {'L1': Fraction(1, 3), 'L2': Fraction(0), 'R1': Fraction(1, 2), 'R2': Fraction(0)}
        cases = (
            ((0, 0), ('L1', 'R1'), Fraction(1, 36)),
            ((0, 1), ('L1', 'R2'), Fraction(1, 9)),
            ((1, 0), ('L2', 'R1'), Fraction(1, 4)),
            ((1, 1), ('L2', 'R2'), Fraction(0)),
        )
        reports = []
        for positions, pieces, estimate in cases:
            with self.subTest(positions=positions):
                draw = draw_pair(self.db, self.plan_id, FixedPositions(*positions))
                self.assertEqual((draw.left_piece, draw.right_piece), pieces)
                record_reading(self.db, draw.draw_id, draw.left_piece, values[draw.left_piece], 'grid-left')
                record_reading(self.db, draw.draw_id, draw.right_piece, values[draw.right_piece], 'grid-right')
                report = issue_report(self.db, draw.draw_id)
                self.assertEqual(report.snapshot.estimate, estimate)
                reports.append(report)
        with closing(open_database(self.path)) as reopened:
            downstream = [read_report(reopened, report.report_id) for report in reports]
        self.assertEqual(downstream, reports)
        issued = [report.snapshot.estimate for report in reports]
        received = [report.snapshot.estimate for report in downstream]
        expected = [estimate for _, _, estimate in cases]
        mean = sum(received) / len(received)
        self.assertEqual(mean, Fraction(7, 72))
        emit_scenario(
            case_id='exact_readback.all_pairs_mean',
            input={'values': values, 'positions': [positions for positions, _, _ in cases]},
            expected=expected,
            actual=issued,
            downstream_expected={'estimates': expected, 'mean': Fraction(7, 72)},
            downstream_actual={'estimates': received, 'mean': mean},
            code_paths=['sampling/uniform.py', 'measurements/pairs.py', 'analysis/contrast.py', 'archive/readback.py'],
            oracle='The four hand-computed squared differences sum to 7/18. Each has probability 1/4.',
        )

    def test_wide_rationals_survive_reopen(self):
        large_odd = 10**80 + 1
        draw = draw_pair(self.db, self.plan_id, FixedPositions(0, 0))
        record_reading(self.db, draw.draw_id, 'L1', Fraction(large_odd, 2), 'wide-left')
        record_reading(self.db, draw.draw_id, 'R1', 0, 'wide-right')
        signed = issue_report(self.db, draw.draw_id)
        self.db.close()
        with closing(open_database(self.path)) as reopened:
            received = read_report(reopened, signed.report_id)
            pair = load_reading_pair(reopened, draw.draw_id)
        self.assertEqual(pair.left.value, Fraction(large_odd, 2))
        self.assertEqual(received.snapshot.left.value, Fraction(large_odd, 2))
        self.assertEqual(received.snapshot.estimate, Fraction(large_odd**2, 4))
