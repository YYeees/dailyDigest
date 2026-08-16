import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.log_usage import build_entries, RUN_LOG_KEEP  # noqa: E402


class TestBuildEntries(unittest.TestCase):
    def setUp(self):
        self.result = {
            "total_cost_usd": 0.0637,
            "duration_ms": 3263,
            "duration_api_ms": 4994,
            "num_turns": 1,
            "is_error": False,
            "usage": {
                "input_tokens": 2,
                "output_tokens": 4,
                "cache_creation_input_tokens": 9692,
                "cache_read_input_tokens": 16652,
            },
            "modelUsage": {"claude-sonnet-5": {"costUSD": 0.0632}},
        }

    def test_summary_pulls_flat_token_fields(self):
        _, summary = build_entries(self.result, "digest", "2026-08-16T22:00:00+00:00")
        self.assertEqual(summary["input_tokens"], 2)
        self.assertEqual(summary["output_tokens"], 4)
        self.assertEqual(summary["cache_creation_input_tokens"], 9692)
        self.assertEqual(summary["cache_read_input_tokens"], 16652)
        self.assertEqual(summary["total_cost_usd"], 0.0637)
        self.assertEqual(summary["label"], "digest")

    def test_detail_keeps_full_model_usage(self):
        detail, _ = build_entries(self.result, "trending", "2026-08-16T22:00:00+00:00")
        self.assertEqual(detail["model_usage"], {"claude-sonnet-5": {"costUSD": 0.0632}})
        self.assertEqual(detail["usage"], self.result["usage"])

    def test_missing_usage_defaults_to_none_fields(self):
        _, summary = build_entries({}, "digest", "2026-08-16T22:00:00+00:00")
        self.assertIsNone(summary["input_tokens"])
        self.assertIsNone(summary["total_cost_usd"])


class TestRunLogKeep(unittest.TestCase):
    def test_trims_to_keep_limit(self):
        runs = list(range(RUN_LOG_KEEP + 5))
        runs.insert(0, "newest")
        trimmed = runs[:RUN_LOG_KEEP]
        self.assertEqual(len(trimmed), RUN_LOG_KEEP)
        self.assertEqual(trimmed[0], "newest")


if __name__ == "__main__":
    unittest.main()
