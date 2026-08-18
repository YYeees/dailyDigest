import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from new_flags import load_prev_items, mark_new  # noqa: E402


def item(link):
    return {"link": link, "title": link}


class TestMarkNew(unittest.TestCase):
    def test_only_newly_appeared_items_are_new(self):
        prev = [item("a"), item("b")]
        items = [item("c"), item("a"), item("b")]
        mark_new(items, prev)
        self.assertEqual([i["is_new"] for i in items], [True, False, False])

    def test_first_export_marks_everything_new(self):
        items = [item("a"), item("b")]
        mark_new(items, [])
        self.assertTrue(all(i["is_new"] for i in items))

    def test_no_additions_preserves_previous_highlight(self):
        # 手动重跑一遍export(或者抓取没抓到新东西)不该让刚上站的内容失去高亮
        prev = [dict(item("a"), is_new=True), dict(item("b"), is_new=False)]
        items = [item("a"), item("b")]
        mark_new(items, prev)
        self.assertEqual([i["is_new"] for i in items], [True, False])

    def test_dropping_items_alone_does_not_relight_everything(self):
        # 条目滑出7天窗口被删掉，但没有新增——高亮保持不变
        prev = [dict(item("a"), is_new=True), dict(item("b"), is_new=False)]
        items = [item("b")]
        mark_new(items, prev)
        self.assertEqual([i["is_new"] for i in items], [False])

    def test_additions_clear_stale_highlight(self):
        # 上一轮的高亮不会跨到这一轮：这次一有新增，旧的高亮就该灭
        prev = [dict(item("a"), is_new=True)]
        items = [item("a"), item("b")]
        mark_new(items, prev)
        self.assertEqual([i["is_new"] for i in items], [False, True])


class TestLoadPrevItems(unittest.TestCase):
    def test_missing_file_is_empty(self):
        self.assertEqual(load_prev_items(Path("/nonexistent/recent.json")), [])

    def test_corrupt_file_is_empty(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
        self.assertEqual(load_prev_items(Path(f.name)), [])

    def test_reads_items_field(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"items": [item("a")]}, f)
        self.assertEqual(load_prev_items(Path(f.name)), [item("a")])


if __name__ == "__main__":
    unittest.main()
