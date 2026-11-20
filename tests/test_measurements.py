from fractions import Fraction

from measurements import load_reading_pair, record_reading
from measurements.repository import ReadingRepository
from sampling import draw_pair

from tests.fixtures import DatabaseCase, FixedPositions, prepare_fixture


class MeasurementTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        _, plan_id = prepare_fixture(self.db)
        self.draw = draw_pair(self.db, plan_id, FixedPositions(1, 0))

    def test_wrong_piece_then_actual_piece(self):
        with self.assertRaises(ValueError):
            record_reading(self.db, self.draw.draw_id, 'L1', '1/9', 'wrong-piece')
        self.assertEqual(ReadingRepository(self.db).load_draw_readings(self.draw.draw_id), {})
        recorded = record_reading(self.db, self.draw.draw_id, 'L2', '1/3', 'left-1')
        pair = load_reading_pair(self.db, self.draw.draw_id)
        self.assertEqual(pair.left, recorded)
        self.assertIsNone(pair.right)
        self.assertEqual((recorded.value, recorded.instrument_ref), (Fraction(1, 3), 'left-1'))

    def test_duplicate_keeps_original(self):
        original = record_reading(self.db, self.draw.draw_id, 'L2', '1/3', 'I1')
        with self.assertRaises(ValueError):
            record_reading(self.db, self.draw.draw_id, 'L2', '2/3', 'I2')
        record_reading(self.db, self.draw.draw_id, 'R1', -1, 'I3')
        pair = load_reading_pair(self.db, self.draw.draw_id)
        self.assertTrue(pair.is_complete())
        self.assertEqual(pair.left, original)
        self.assertEqual((pair.left.value, pair.left.instrument_ref), (Fraction(1, 3), 'I1'))
        self.assertEqual((pair.right.value, pair.right.instrument_ref), (Fraction(-1), 'I3'))

    def test_invalid_value_then_valid(self):
        for value in ('1/0', 'no reading', 0.5, False, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    record_reading(self.db, self.draw.draw_id, 'L2', value, 'left-1')
                self.assertIsNone(load_reading_pair(self.db, self.draw.draw_id).left)
        with self.assertRaises(ValueError):
            record_reading(self.db, self.draw.draw_id, 'L2', '-3/5', ' ')
        record_reading(self.db, self.draw.draw_id, 'L2', '-3/5', 'left-1')
        self.assertEqual(load_reading_pair(self.db, self.draw.draw_id).left.value, Fraction(-3, 5))

    def test_unknown_draw(self):
        with self.assertRaises(KeyError):
            record_reading(self.db, 999, 'L2', 0, 'left-1')
        with self.assertRaises(KeyError):
            load_reading_pair(self.db, 999)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM readings').fetchone()[0], 0)

    def test_right_then_left_zero(self):
        record_reading(self.db, self.draw.draw_id, 'R1', '1/2', 'right-1')
        partial = load_reading_pair(self.db, self.draw.draw_id)
        self.assertFalse(partial.is_complete())
        self.assertIsNone(partial.left)
        self.assertEqual(partial.right.value, Fraction(1, 2))
        record_reading(self.db, self.draw.draw_id, 'L2', 0, 'left-zero')
        complete = load_reading_pair(self.db, self.draw.draw_id)
        self.assertTrue(complete.is_complete())
        self.assertIsInstance(complete.left.value, Fraction)
        self.assertEqual((complete.left.value, complete.left.instrument_ref), (Fraction(0), 'left-zero'))
        self.assertEqual(complete.right, partial.right)

    def test_left_then_right(self):
        record_reading(self.db, self.draw.draw_id, 'L2', Fraction(1, 3), 'left-first')
        partial = load_reading_pair(self.db, self.draw.draw_id)
        self.assertFalse(partial.is_complete())
        self.assertIsNone(partial.right)
        record_reading(self.db, self.draw.draw_id, 'R1', '0', 'right-zero')
        pair = load_reading_pair(self.db, self.draw.draw_id)
        self.assertTrue(pair.is_complete())
        self.assertEqual(pair.left, partial.left)
        self.assertEqual((pair.right.value, pair.right.instrument_ref), (Fraction(0), 'right-zero'))
