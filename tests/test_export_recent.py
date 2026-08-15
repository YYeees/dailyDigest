import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from export_recent import best_tier  # noqa: E402


class TestBestTier(unittest.TestCase):
    def test_high_beats_medium(self):
        self.assertEqual(best_tier("medium", "high"), "high")

    def test_medium_beats_low(self):
        self.assertEqual(best_tier("low", "medium"), "medium")

    def test_none_values_ignored(self):
        self.assertEqual(best_tier(None, "medium"), "medium")

    def test_both_none_defaults_to_low(self):
        self.assertEqual(best_tier(None, None), "low")

    def test_both_high(self):
        self.assertEqual(best_tier("high", "high"), "high")


if __name__ == "__main__":
    unittest.main()
