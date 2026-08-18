"""回归测试:防止fetch.py/fetch_x.py的建表语句再次跟真实digest.db结构脱节
(2026-08-15代码审计发现过一次:两处内联CREATE TABLE都缺排序用的6个列,
空库首次跑fetch.py会建出残缺表,后面rank_items.py写入时报"no such column")。
"""
import sqlite3
import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch  # noqa: E402
import fetch_x  # noqa: E402

EXPECTED_ITEMS_COLUMNS = {
    "guid", "person", "source_name", "source_type", "title", "link", "published",
    "summary", "has_full_text", "first_seen_at",
    "ai_tier", "ai_reason", "anchor_tier", "anchor_reason", "digest_summary", "ranked_at",
    "excluded_reason", "content",
}


def table_columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


class TestFreshDbSchema(unittest.TestCase):
    def test_fetch_init_db_creates_full_schema(self):
        conn = sqlite3.connect(":memory:")
        fetch.init_db(conn)
        self.assertEqual(table_columns(conn, "items"), EXPECTED_ITEMS_COLUMNS)
        conn.close()

    def test_fetch_x_init_db_creates_full_schema(self):
        conn = sqlite3.connect(":memory:")
        fetch_x.init_db(conn)
        self.assertEqual(table_columns(conn, "items"), EXPECTED_ITEMS_COLUMNS)
        conn.close()

    def test_fetch_and_fetch_x_agree_on_schema(self):
        conn_a = sqlite3.connect(":memory:")
        fetch.init_db(conn_a)
        conn_b = sqlite3.connect(":memory:")
        fetch_x.init_db(conn_b)
        self.assertEqual(table_columns(conn_a, "items"), table_columns(conn_b, "items"))
        conn_a.close()
        conn_b.close()


if __name__ == "__main__":
    unittest.main()
