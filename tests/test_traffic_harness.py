import unittest

from scripts.traffic_harness import run_scenarios


class TrafficHarnessTests(unittest.TestCase):
    def test_sustained_traffic_at_rate_is_all_forwarded(self):
        result = run_scenarios(rate=10, burst=5, seconds=3)
        self.assertEqual(result["sustained"], (30, 30, 0))

    def test_burst_capacity_excess_and_one_second_refill(self):
        result = run_scenarios(rate=3, burst=2, seconds=2)
        self.assertEqual(result["burst"], (6, 5, 1))
        self.assertEqual(result["refill"], (3, 3, 0))

    def test_zero_extra_burst(self):
        result = run_scenarios(rate=1, burst=0, seconds=2)
        self.assertEqual(result["sustained"], (2, 2, 0))
        self.assertEqual(result["burst"], (2, 1, 1))
        self.assertEqual(result["refill"], (1, 1, 0))

    def test_invalid_inputs(self):
        for args in [(0, 1, 1), (1, -1, 1), (1, 1, 0)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                run_scenarios(*args)
