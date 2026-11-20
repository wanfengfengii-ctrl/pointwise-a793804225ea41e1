from cohorts import freeze_cohorts, get_cohort_freeze, register_batch
from sampling import create_plan, get_plan

from tests.fixtures import BATCH_ID, LEFT, RIGHT, DatabaseCase, register_fixture


class CohortTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        register_fixture(self.db)

    def freeze_count(self):
        return self.db.execute('SELECT COUNT(*) FROM cohort_freezes').fetchone()[0]

    def test_plan_keeps_freeze(self):
        first = freeze_cohorts(self.db, BATCH_ID, LEFT, RIGHT)
        plan_id = create_plan(self.db, first)
        second = freeze_cohorts(self.db, BATCH_ID, ('L3', 'L1'), ('R3', 'R1'))
        self.assertNotEqual(first, second)
        plan = get_plan(self.db, plan_id)
        self.assertEqual((plan.batch_id, plan.freeze_id), (BATCH_ID, first))
        original = get_cohort_freeze(self.db, plan.freeze_id)
        self.assertEqual((original.left, original.right), (LEFT, RIGHT))
        revised = get_cohort_freeze(self.db, second)
        self.assertEqual((revised.left, revised.right), (('L3', 'L1'), ('R3', 'R1')))

    def test_explicit_old_freeze(self):
        first = freeze_cohorts(self.db, BATCH_ID, LEFT, RIGHT)
        second = freeze_cohorts(self.db, BATCH_ID, ('L2', 'L1'), ('R2', 'R1'))
        old_plan = get_plan(self.db, create_plan(self.db, first))
        new_plan = get_plan(self.db, create_plan(self.db, second))
        self.assertEqual((old_plan.freeze_id, new_plan.freeze_id), (first, second))
        self.assertEqual(get_cohort_freeze(self.db, old_plan.freeze_id).left, LEFT)

    def test_unknown_freeze(self):
        with self.assertRaises(KeyError):
            create_plan(self.db, 999)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM plans').fetchone()[0], 0)

    def test_rejects_invalid_groups(self):
        cases = [
            ('repeated left', ('L1', 'L1'), RIGHT),
            ('shared between sides', LEFT, ('L1', 'R2')),
            ('unequal nonempty', LEFT, ('R1',)),
            ('empty groups', (), ()),
        ]
        for label, left, right in cases:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    freeze_cohorts(self.db, BATCH_ID, left, right)
                self.assertEqual(self.freeze_count(), 0)
        valid = freeze_cohorts(self.db, BATCH_ID, LEFT, RIGHT)
        self.assertEqual(get_cohort_freeze(self.db, valid).right, RIGHT)
        self.assertEqual(self.freeze_count(), 1)

    def test_membership(self):
        register_batch(self.db, 'OTHER', ('X1',), ('Y1',))
        for candidate in ('X1', 'R2', 'unregistered'):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    freeze_cohorts(self.db, BATCH_ID, (candidate,), ('R1',))
                self.assertEqual(self.freeze_count(), 0)
        own_version = freeze_cohorts(self.db, 'OTHER', ('X1',), ('Y1',))
        self.assertEqual(get_cohort_freeze(self.db, own_version).batch_id, 'OTHER')

    def test_unknown_batch(self):
        with self.assertRaises(KeyError):
            freeze_cohorts(self.db, 'MISSING', LEFT, RIGHT)
        self.assertEqual(self.freeze_count(), 0)
