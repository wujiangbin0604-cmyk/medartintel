import unittest
from src.labels import describe, AAMI_MAP
from src.analysis import window_bounds


class RulesTests(unittest.TestCase):
    def test_explicit_mapping(self):
        self.assertEqual(len(AAMI_MAP), 15)
        self.assertEqual([AAMI_MAP[s] for s in ("N", "e", "a", "E", "F", "/", "f", "Q")],
                         ["N", "N", "S", "V", "F", "Q", "Q", "Q"])

    def test_nonbeats_never_become_q(self):
        for symbol in ("+", "~", "|", "!", "x", "[", "]"):
            self.assertEqual(describe(symbol)["annotation_kind"], "non_beat")
            self.assertEqual(describe(symbol)["aami_group"], "")

    def test_unknown_and_unmapped_stay_separate(self):
        self.assertEqual(describe("z")["annotation_kind"], "unknown")
        self.assertEqual(describe("B")["annotation_kind"], "unmapped_beat")
        self.assertEqual(describe("?")["aami_group"], "")
        self.assertNotEqual(describe("N"), describe("n"))

    def test_boundaries_include_last_sample(self):
        self.assertEqual(window_bounds(100, 263, 360), (10, 263))
        self.assertIsNone(window_bounds(100, 262, 360))
        self.assertEqual(window_bounds(90, 1000, 360), (0, 253))
        self.assertIsNone(window_bounds(89, 1000, 360))
        self.assertIsNone(window_bounds(0, 1000, 360))
        self.assertIsNone(window_bounds(999, 1000, 360))


if __name__ == "__main__":
    unittest.main()
