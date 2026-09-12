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


class TestEvalNotFloored(unittest.TestCase):
    """HIGH_ONLY_PERSONS的"当日内容不分tier全展示"保底，**不能把eval也抬上来**。

    eval命中与否决定条目进不进公开站(见export_public.public_item)。把真实的low抬成
    medium，等于凭空给这个人的每条当日内容编一个"这是测试内容"的判断，结果是他的当日
    内容被整批挡在公开站外——实测过，公开站当场少掉一半，而且不报任何错。
    """

    def _export_one(self, tmp, eval_tier):
        import sqlite3, json
        from datetime import datetime, timezone
        import fetch, export_recent
        from config import HIGH_ONLY_PERSONS

        db = Path(tmp) / "t.db"
        conn = sqlite3.connect(db)
        fetch.init_db(conn)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO items (guid, person, source_name, source_type, title, link,"
            " published, summary, has_full_text, first_seen_at, ai_tier, ai_reason,"
            " anchor_tier, anchor_reason, eval_tier, eval_reason, digest_summary, ranked_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("g1", sorted(HIGH_ONLY_PERSONS)[0], "s", "blog", "T", "https://x/1",
             now, "s", 1, now, "low", "", "low", "", eval_tier, "", "摘要", now),
        )
        conn.commit()
        conn.close()

        orig_db, orig_out = export_recent.DB_PATH, export_recent.OUT_DIR
        export_recent.DB_PATH = str(db)
        export_recent.OUT_DIR = Path(tmp) / "out"
        try:
            export_recent.export(pipeline_run=False)
            data = json.loads((Path(tmp) / "out" / "recent.json").read_text(encoding="utf-8"))
        finally:
            export_recent.DB_PATH, export_recent.OUT_DIR = orig_db, orig_out
        return data["items"]

    def test_low_eval_stays_absent_for_high_only_person(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            items = self._export_one(tmp, "low")
        self.assertEqual(len(items), 1, "当日内容仍应展示(ai/anchor的保底照旧生效)")
        tracks = {t["track"] for t in items[0]["tracks"]}
        self.assertNotIn("eval", tracks, "eval判的是low，不该被保底抬成medium")
        self.assertTrue({"ai", "anchor"} <= tracks, "ai/anchor的保底不该被这次改动影响")

    def test_real_high_eval_still_shows(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            items = self._export_one(tmp, "high")
        tracks = {t["track"]: t["tier"] for t in items[0]["tracks"]}
        self.assertEqual(tracks.get("eval"), "high", "真判了high的eval照常出现")
