import json
import random
import unittest
from contextlib import closing
from fractions import Fraction
from pathlib import Path

from analysis import issue_report
from archive import open_database, read_report
from archive.schema import ReportObservation, ReportSnapshot
from cohorts import freeze_cohorts, register_batch
from measurements import load_reading_pair, record_reading
from sampling import (
    RestrictedDraw, RestrictedPairPlan, create_plan, create_restricted_plan,
    draw_pair, get_draw, get_plan,
)
from sampling.distribution import _find_perfect_matching, build_restricted_distribution
from sampling.select import cumulative_weights

from tests.fixtures import (
    BATCH_ID, DatabaseCase, FixedPositions, emit_scenario, report_count,
)


EXAMPLE_PATH = Path(__file__).resolve().parent.parent / 'examples' / 'restricted_pairing.json'
RESTRICTED_BASIS = 'v2/restricted-pair-mean-squared-color-difference'


def load_example():
    return json.loads(EXAMPLE_PATH.read_text(encoding='utf-8'))


class RestrictedPlanCase(DatabaseCase):
    def register_five_pairs(self):
        example = load_example()['five_pairs']
        register_batch(self.db, example['batch_id'], example['left'], example['right'])
        freeze_id = freeze_cohorts(
            self.db, example['batch_id'], example['left'], example['right'],
        )
        return example, freeze_id

    def make_five_pair_plan(self):
        example, freeze_id = self.register_five_pairs()
        plan_id = create_restricted_plan(self.db, freeze_id, example['allowed_pairs'])
        self.assertIsNotNone(plan_id)
        return example, freeze_id, plan_id


class RestrictedDistributionTests(RestrictedPlanCase):
    def test_exact_marginals_and_support(self):
        example, freeze_id, plan_id = self.make_five_pair_plan()
        plan = get_plan(self.db, plan_id)
        self.assertIsInstance(plan, RestrictedPairPlan)
        self.assertEqual(plan.plan_id, plan_id)
        self.assertEqual(plan.freeze_id, freeze_id)

        probabilities = plan.probabilities
        self.assertEqual(
            set(probabilities), {tuple(pair) for pair in example['allowed_pairs']},
        )
        self.assertTrue(all(isinstance(p, Fraction) and p > 0 for p in probabilities.values()))
        self.assertEqual(sum(probabilities.values(), Fraction(0)), Fraction(1))

        for side, pieces in (('left', example['left']), ('right', example['right'])):
            for piece in pieces:
                marginal = sum(
                    (p for pair, p in probabilities.items() if piece in pair), Fraction(0),
                )
                self.assertEqual(marginal, Fraction(1, 3), f'{side} marginal for {piece}')

    def test_third_piece_pair_is_forced_to_one_third(self):
        _, _, plan_id = self.make_five_pair_plan()
        probabilities = get_plan(self.db, plan_id).probabilities
        self.assertEqual(probabilities[('A3', 'B3')], Fraction(1, 3))

    def test_distribution_frozen_and_stable_on_reread(self):
        _, _, plan_id = self.make_five_pair_plan()
        first = get_plan(self.db, plan_id).probabilities
        second = get_plan(self.db, plan_id).probabilities
        self.assertEqual(second, first)
        self.assertEqual(list(second), list(first))

    def test_impossible_manifest_returns_none_without_writes(self):
        example = load_example()['three_pairs']
        register_batch(self.db, example['batch_id'], example['left'], example['right'])
        freeze_id = freeze_cohorts(
            self.db, example['batch_id'], example['left'], example['right'],
        )
        self.assertIsNone(create_restricted_plan(self.db, freeze_id, example['allowed_pairs']))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM plans').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM restricted_plans').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM draws').fetchone()[0], 0)
        # A legal plan on the same freeze remains possible afterwards.
        fallback = create_plan(self.db, freeze_id)
        self.assertEqual(get_plan(self.db, fallback).freeze_id, freeze_id)

    def test_edge_outside_every_matching_returns_none(self):
        _, freeze_id = self.register_five_pairs()
        # A3 only pairs with B3, so A1-B3 can never belong to a perfect matching.
        dead_edge = [
            ['A1', 'B1'], ['A1', 'B2'], ['A2', 'B1'], ['A2', 'B2'], ['A3', 'B3'], ['A1', 'B3'],
        ]
        self.assertIsNone(create_restricted_plan(self.db, freeze_id, dead_edge))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM plans').fetchone()[0], 0)

    def test_invalid_manifests_raise_value_error_without_writes(self):
        _, freeze_id = self.register_five_pairs()
        invalid_manifests = [
            [],
            'A1B1',
            [['A1']],
            [['A1', 'B1', 'B2']],
            [[1, 'B1']],
            [['A9', 'B1']],
            [['A1', 'B9']],
            [['B1', 'B2']],
            [['A1', 'A2']],
            [['A1', 'B1'], ['A1', 'B1']],
        ]
        for manifest in invalid_manifests:
            with self.subTest(manifest=manifest):
                with self.assertRaises(ValueError):
                    create_restricted_plan(self.db, freeze_id, manifest)
                self.assertEqual(self.db.execute('SELECT COUNT(*) FROM plans').fetchone()[0], 0)

    def test_unknown_freeze_raises_key_error(self):
        with self.assertRaises(KeyError):
            create_restricted_plan(self.db, 999, [['A1', 'B1']])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM plans').fetchone()[0], 0)

    def test_single_pair_group(self):
        register_batch(self.db, 'SOLO', ['X1'], ['Y1'])
        freeze_id = freeze_cohorts(self.db, 'SOLO', ['X1'], ['Y1'])
        plan_id = create_restricted_plan(self.db, freeze_id, [['X1', 'Y1']])
        self.assertEqual(
            get_plan(self.db, plan_id).probabilities,
            {('X1', 'Y1'): Fraction(1)},
        )


class DistributionEngineTests(unittest.TestCase):
    def test_random_graphs_keep_exact_marginals(self):
        rng = random.Random(20261120)
        for _ in range(200):
            size = rng.randint(1, 6)
            edges = list({
                (rng.randrange(size), rng.randrange(size))
                for _ in range(rng.randint(1, size * size))
            })
            adjacency = [[] for _ in range(size)]
            for left, right in edges:
                adjacency[left].append(right)
            every_edge_coverable = all(
                _find_perfect_matching(adjacency, size, forced=edge) is not None for edge in edges
            )
            distribution = build_restricted_distribution(edges, size)
            if not every_edge_coverable:
                self.assertIsNone(distribution)
                continue
            self.assertIsNotNone(distribution)
            self.assertEqual(set(distribution), set(edges))
            self.assertEqual(sum(distribution.values(), Fraction(0)), Fraction(1))
            left_marginals = [Fraction(0)] * size
            right_marginals = [Fraction(0)] * size
            for (left, right), probability in distribution.items():
                self.assertGreater(probability, 0)
                left_marginals[left] += probability
                right_marginals[right] += probability
            self.assertEqual(set(left_marginals + right_marginals), {Fraction(1, size)})

    def test_forced_edge_search_keeps_preassigned_match(self):
        # Regression: an augmenting search must treat the preassigned forced
        # right node as occupied; otherwise it can be stolen and produce either
        # a duplicated right node or a wrong "no matching" answer.
        from sampling.distribution import _find_perfect_matching

        adjacency = [[4], [1], [0, 3, 4], [0, 4], [2, 3]]
        # Left 0 can only take right 4, so forcing left 2 onto right 4 is
        # infeasible: the forced assignment must not be overwritten.
        self.assertIsNone(_find_perfect_matching(adjacency, 5, forced=(2, 4)))

        feasible = [[0, 1], [0, 2], [1, 3], [3]]
        matching = _find_perfect_matching(feasible, 4, forced=(2, 1))
        self.assertIsNotNone(matching)
        self.assertEqual(matching[2], 1)
        self.assertEqual(sorted(matching), list(range(4)))
        self.assertEqual(len(set(matching)), 4)


class RestrictedDrawTests(RestrictedPlanCase):
    def slot_source_for(self, probabilities, target):
        cumulative = cumulative_weights(probabilities)
        start = 0
        for pair, boundary in zip(probabilities, cumulative):
            if pair == target:
                return FixedPositions(start)
            start = boundary
        raise KeyError(target)

    def test_draws_follow_published_distribution(self):
        _, _, plan_id = self.make_five_pair_plan()
        probabilities = get_plan(self.db, plan_id).probabilities
        total = cumulative_weights(probabilities)[-1]
        for pair, probability in probabilities.items():
            with self.subTest(pair=pair):
                source = self.slot_source_for(probabilities, pair)
                draw = draw_pair(self.db, plan_id, source)
                self.assertIsInstance(draw, RestrictedDraw)
                self.assertEqual((draw.left_piece, draw.right_piece), pair)
                self.assertEqual(draw.probability, probability)
                self.assertEqual(source.bounds, [total])
                stored = get_draw(self.db, draw.draw_id)
                self.assertEqual(stored, draw)

    def test_every_slot_maps_to_an_allowed_pair(self):
        _, _, plan_id = self.make_five_pair_plan()
        plan = get_plan(self.db, plan_id)
        total = cumulative_weights(plan.probabilities)[-1]
        counts = {pair: 0 for pair in plan.probabilities}
        for slot in range(total):
            draw = draw_pair(self.db, plan_id, FixedPositions(slot))
            pair = (draw.left_piece, draw.right_piece)
            self.assertIn(pair, counts)
            self.assertEqual(draw.probability, plan.probabilities[pair])
            counts[pair] += 1
        for pair, probability in plan.probabilities.items():
            self.assertEqual(counts[pair], (probability * total).numerator)

    def test_port_failure_leaves_no_draw(self):
        _, _, plan_id = self.make_five_pair_plan()

        class Broken:
            def randbelow(self, upper):
                raise RuntimeError('entropy unavailable')

        with self.assertRaises(RuntimeError):
            draw_pair(self.db, plan_id, Broken())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM draws').fetchone()[0], 0)

        class OutOfRange:
            def randbelow(self, upper):
                return upper

        with self.assertRaises(ValueError):
            draw_pair(self.db, plan_id, OutOfRange())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM draws').fetchone()[0], 0)

    def test_unknown_plan_raises_key_error(self):
        source = FixedPositions(0)
        with self.assertRaises(KeyError):
            draw_pair(self.db, 999, source)
        self.assertEqual(source.bounds, [])


class RestrictedReportTests(RestrictedPlanCase):
    def slot_for(self, probabilities, target):
        cumulative = cumulative_weights(probabilities)
        start = 0
        for pair, boundary in zip(probabilities, cumulative):
            if pair == target:
                return start
            start = boundary
        raise KeyError(target)

    def issue_pair_readings(self, example, plan_id, target):
        probabilities = get_plan(self.db, plan_id).probabilities
        slot = self.slot_for(probabilities, target)
        draw = draw_pair(self.db, plan_id, FixedPositions(slot))
        readings = {piece: Fraction(value) for piece, value in example['readings'].items()}
        record_reading(
            self.db, draw.draw_id, draw.left_piece,
            readings[draw.left_piece], f'炉台-{draw.left_piece}',
        )
        record_reading(
            self.db, draw.draw_id, draw.right_piece,
            readings[draw.right_piece], f'炉台-{draw.right_piece}',
        )
        return draw

    def issue_for_pair(self, example, plan_id, target):
        draw = self.issue_pair_readings(example, plan_id, target)
        return draw, issue_report(self.db, draw.draw_id)

    def test_estimate_uses_pair_count_and_joint_probability(self):
        example, freeze_id, plan_id = self.make_five_pair_plan()
        draw, report = self.issue_for_pair(example, plan_id, ('A3', 'B3'))
        snapshot = report.snapshot
        self.assertEqual(snapshot.basis, RESTRICTED_BASIS)
        self.assertEqual(snapshot.pair_count, 5)
        self.assertEqual(snapshot.probability, Fraction(1, 3))
        self.assertEqual(snapshot.estimate, Fraction(12, 5))
        self.assertEqual(
            (snapshot.left.piece_id, snapshot.right.piece_id), (draw.left_piece, draw.right_piece),
        )
        self.assertEqual(snapshot.freeze_id, freeze_id)

    def test_frozen_probability_weighted_expectation(self):
        example, _, plan_id = self.make_five_pair_plan()
        probabilities = get_plan(self.db, plan_id).probabilities
        readings = {piece: Fraction(value) for piece, value in example['readings'].items()}
        expectation = Fraction(0)
        for pair, probability in probabilities.items():
            left_piece, right_piece = pair
            squared = (readings[left_piece] - readings[right_piece]) ** 2
            estimate = squared / (5 * probability)
            expectation += probability * estimate
        self.assertEqual(expectation, Fraction(7, 2))

    def test_wrong_piece_and_missing_reading_raise_value_error(self):
        example, _, plan_id = self.make_five_pair_plan()
        draw = draw_pair(self.db, plan_id, FixedPositions(0))
        with self.assertRaises(ValueError):
            record_reading(self.db, draw.draw_id, 'A3', example['readings']['A3'], 'wrong-piece')
        record_reading(
            self.db, draw.draw_id, draw.left_piece,
            example['readings'][draw.left_piece], 'left-instrument',
        )
        with self.assertRaises(ValueError):
            issue_report(self.db, draw.draw_id)
        self.assertEqual(report_count(self.db), 0)
        self.assertIsNone(load_reading_pair(self.db, draw.draw_id).right)

    def test_failed_commit_can_retry(self):
        example, _, plan_id = self.make_five_pair_plan()
        draw = self.issue_pair_readings(example, plan_id, ('A1', 'B1'))

        def fail_before_commit():
            raise OSError('commit interrupted at the furnace desk')

        with self.assertRaises(OSError):
            issue_report(self.db, draw.draw_id, before_commit=fail_before_commit)
        self.assertEqual(report_count(self.db), 0)
        report = issue_report(self.db, draw.draw_id)
        self.assertEqual(report_count(self.db), 1)
        self.assertEqual(report.snapshot.draw_id, draw.draw_id)

    def test_report_survives_reopen_and_other_plans(self):
        example, _, plan_id = self.make_five_pair_plan()
        draw, report = self.issue_for_pair(example, plan_id, ('A3', 'B3'))
        expected_snapshot = ReportSnapshot(
            basis=RESTRICTED_BASIS,
            batch_id=example['batch_id'],
            freeze_id=report.snapshot.freeze_id,
            plan_id=plan_id,
            draw_id=draw.draw_id,
            left=ReportObservation('A3', Fraction(2), '炉台-A3'),
            right=ReportObservation('B3', Fraction(0), '炉台-B3'),
            estimate=Fraction(12, 5),
            pair_count=5,
            probability=Fraction(1, 3),
        )
        self.assertEqual(report.snapshot, expected_snapshot)

        # Another plan for the same batch must not disturb the original numbering.
        sibling = create_restricted_plan(
            self.db, report.snapshot.freeze_id, example['allowed_pairs'],
        )
        self.assertNotEqual(sibling, plan_id)
        frozen_probabilities = get_plan(self.db, plan_id).probabilities
        self.db.close()
        with closing(open_database(self.path)) as reopened:
            received = read_report(reopened, report.report_id)
            self.assertEqual(received, report)
            self.assertEqual(received.snapshot, expected_snapshot)
            self.assertEqual(get_draw(reopened, draw.draw_id), draw)
            reopened_plan = get_plan(reopened, plan_id)
            self.assertIsInstance(reopened_plan, RestrictedPairPlan)
            self.assertEqual(reopened_plan.probabilities, frozen_probabilities)
            self.assertEqual(reopened_plan.plan_id, plan_id)
            with self.assertRaises(KeyError):
                read_report(reopened, report.report_id + 100)
        emit_scenario(
            case_id='restricted_readback',
            input={'allowed_pairs': example['allowed_pairs'], 'target': ['A3', 'B3']},
            expected=Fraction(12, 5),
            actual=report.snapshot.estimate,
            downstream_expected={'report_id': report.report_id, 'probability': Fraction(1, 3)},
            downstream_actual={'report_id': received.report_id,
                               'probability': received.snapshot.probability},
            code_paths=['sampling/distribution.py', 'sampling/select.py',
                        'analysis/report.py', 'archive/readback.py'],
            oracle='(2-0)^2 / (5 * 1/3) = 12/5; A3 appears in only A3-B3, so p = 1/3.',
        )

    def test_unknown_numbers_raise_key_error(self):
        example, _, plan_id = self.make_five_pair_plan()
        with self.assertRaises(KeyError):
            get_draw(self.db, 999)
        with self.assertRaises(KeyError):
            issue_report(self.db, 999)
        with self.assertRaises(KeyError):
            read_report(self.db, 999)


class RestrictedInteropTests(RestrictedPlanCase):
    def test_v1_plan_remains_full_pair(self):
        register_batch(self.db, BATCH_ID, ('L1', 'L2'), ('R1', 'R2'))
        freeze_id = freeze_cohorts(self.db, BATCH_ID, ('L1', 'L2'), ('R1', 'R2'))
        full_plan_id = create_plan(self.db, freeze_id)
        plan = get_plan(self.db, full_plan_id)
        self.assertFalse(hasattr(plan, 'probabilities'))
        draw = draw_pair(self.db, full_plan_id, FixedPositions(1, 0))
        self.assertEqual(type(draw).__name__, 'Draw')
        self.assertFalse(hasattr(draw, 'probability'))
        record_reading(self.db, draw.draw_id, draw.right_piece, '1/2', 'right-1')
        record_reading(self.db, draw.draw_id, draw.left_piece, 0, 'left-1')
        report = issue_report(self.db, draw.draw_id)
        self.assertEqual(report.snapshot.basis, 'v1/full-pair-mean-squared-color-difference')
        self.assertIsNone(report.snapshot.pair_count)
        self.assertIsNone(report.snapshot.probability)
        self.assertEqual(report.snapshot.estimate, Fraction(1, 4))
