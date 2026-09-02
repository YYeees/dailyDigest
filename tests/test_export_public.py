"""export_public.py的过滤逻辑——这是"什么能公开"的唯一闸门，改坏了就是把用户的锚点
判断理由发到公网上，所以逐条钉住。"""
import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from export_public import public_item, public_items, PUBLIC_ITEM_FIELDS  # noqa: E402


def item(**kw):
    base = {
        "person": "Simon Willison", "title": "T", "link": "https://x/1", "date": "2026-09-01",
        "first_seen": "2026-09-01T00:00:00+00:00", "source_type": "blog",
        "summary": "摘要", "is_new": True, "tracks": [],
    }
    base.update(kw)
    return base


class TestPublicItem(unittest.TestCase):
    def test_ai_only_item_kept(self):
        out = public_item(item(tracks=[{"track": "ai", "tier": "high", "reason": "命中AI趋势"}]))
        self.assertEqual(out["tracks"], [{"track": "ai", "tier": "high", "reason": "命中AI趋势"}])

    def test_anchor_only_item_dropped(self):
        self.assertIsNone(public_item(item(tracks=[{"track": "anchor", "tier": "high", "reason": "命中母题"}])))

    def test_dual_track_keeps_item_but_strips_anchor(self):
        """两个track都命中时条目照常公开，但anchor那条(含reason)必须摘掉。"""
        out = public_item(item(tracks=[
            {"track": "ai", "tier": "high", "reason": "AI理由"},
            {"track": "anchor", "tier": "high", "reason": "精准命中护城河在harness这条母题"},
        ]))
        self.assertEqual([t["track"] for t in out["tracks"]], ["ai"])
        self.assertNotIn("母题", repr(out))

    def test_no_tracks_dropped(self):
        self.assertIsNone(public_item(item(tracks=[])))

    def test_field_whitelist_drops_unknown_fields(self):
        """白名单的意义:以后往导出里加字段，默认不外传。"""
        out = public_item(item(tracks=[{"track": "ai", "tier": "high", "reason": "r"}],
                               anchor_reason="不该出现", 内部字段="也不该出现"))
        self.assertNotIn("anchor_reason", out)
        self.assertNotIn("内部字段", out)
        self.assertEqual(set(out) - {"tracks"}, set(PUBLIC_ITEM_FIELDS))

    def test_first_seen_not_public(self):
        out = public_item(item(tracks=[{"track": "ai", "tier": "medium", "reason": "r"}]))
        self.assertNotIn("first_seen", out)

    def test_public_items_filters_and_preserves_order(self):
        items = [
            item(title="A", tracks=[{"track": "ai", "tier": "high", "reason": "r"}]),
            item(title="B", tracks=[{"track": "anchor", "tier": "high", "reason": "r"}]),
            item(title="C", tracks=[{"track": "ai", "tier": "medium", "reason": "r"}]),
        ]
        self.assertEqual([i["title"] for i in public_items(items)], ["A", "C"])


if __name__ == "__main__":
    unittest.main()
