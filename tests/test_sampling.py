from cohorts import freeze_cohorts
from sampling import draw_pair, get_draw

from tests.fixtures import BATCH_ID, DatabaseCase, FixedPositions, prepare_fixture


class SamplingTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        self.freeze_id, self.plan_id = prepare_fixture(self.db)

    def draw_count(self):
        return self.db.execute('SELECT COUNT(*) FROM draws').fetchone()[0]

    def test_draws_one_position_per_side(self):
        source = FixedPositions(1, 0)
        draw = draw_pair(self.db, self.plan_id, source)
        self.assertEqual(source.bounds, [2, 2])
        self.assertEqual((draw.plan_id, draw.left_piece, draw.right_piece), (self.plan_id, 'L2', 'R1'))
        self.assertEqual(get_draw(self.db, draw.draw_id), draw)

    def test_independent_positions(self):
        expected = {
            (0, 0): ('L1', 'R1'),
            (0, 1): ('L1', 'R2'),
            (1, 0): ('L2', 'R1'),
            (1, 1): ('L2', 'R2'),
        }
        draw_ids = set()
        for positions, pieces in expected.items():
            with self.subTest(positions=positions):
                source = FixedPositions(*positions)
                draw = draw_pair(self.db, self.plan_id, source)
                stored = get_draw(self.db, draw.draw_id)
                self.assertEqual(source.bounds, [2, 2])
                self.assertEqual((draw.left_piece, draw.right_piece), pieces)
                self.assertEqual(stored, draw)
                draw_ids.add(stored.draw_id)
        self.assertEqual(len(draw_ids), 4)
        self.assertEqual(self.draw_count(), 4)

    def test_frozen_order(self):
        freeze_cohorts(self.db, BATCH_ID, ('L2', 'L1'), ('R2', 'R1'))
        draw = draw_pair(self.db, self.plan_id, FixedPositions(1, 0))
        self.assertEqual((draw.left_piece, draw.right_piece), ('L2', 'R1'))
        self.assertEqual(get_draw(self.db, draw.draw_id), draw)

    def test_entropy_failure(self):
        for positions, expected_bounds in (((), [2]), ((1,), [2, 2])):
            with self.subTest(positions=positions):
                source = FixedPositions(*positions)
                with self.assertRaises(StopIteration):
                    draw_pair(self.db, self.plan_id, source)
                self.assertEqual(source.bounds, expected_bounds)
                self.assertEqual(self.draw_count(), 0)

        for positions, expected_bounds in (((2, 1), [2]), ((1, -1), [2, 2]),
                                           ((1, True), [2, 2]), ((1, '0'), [2, 2])):
            with self.subTest(positions=positions):
                source = FixedPositions(*positions)
                with self.assertRaises(ValueError):
                    draw_pair(self.db, self.plan_id, source)
                self.assertEqual(source.bounds, expected_bounds)
                self.assertEqual(self.draw_count(), 0)

        recovered = draw_pair(self.db, self.plan_id, FixedPositions(0, 1))
        self.assertEqual((recovered.left_piece, recovered.right_piece), ('L1', 'R2'))
        self.assertEqual(self.draw_count(), 1)

    def test_unknown_plan(self):
        source = FixedPositions(0, 0)
        with self.assertRaises(KeyError):
            draw_pair(self.db, 999, source)
        self.assertEqual(source.bounds, [])
        self.assertEqual(self.draw_count(), 0)
