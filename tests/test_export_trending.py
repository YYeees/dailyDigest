"""
锁住trending板块的两条排序规则(2026-08-21加)。

这块地方出过一次问题：原来按`stars_total`(历史累计star)排，板子变成"AI仓库历史人气总榜"，
新仓库除非自带十几万star否则永远挤不进来，用户看到的是一块几乎不动的板。改成按"这一期
涨了多少"排之后，又多出一个新的冻结风险——掉出榜单的仓库会带着上一期的旧涨幅继续参赛。
两条规则都用测试焊住，避免以后再改回去。
"""

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import export_trending  # noqa: E402


def build_db(path, repos, snapshots):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE repos (full_name TEXT PRIMARY KEY, url TEXT, description TEXT,
        primary_language TEXT, first_seen_date TEXT, last_seen_date TEXT, ai_related INTEGER,
        difficulty TEXT, worth_tier TEXT, recommend_reason TEXT, evaluated_at TEXT)""")
    conn.execute("""CREATE TABLE daily_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL, snapshot_date TEXT NOT NULL, trending_page TEXT NOT NULL,
        rank INTEGER, stars_total INTEGER, stars_today INTEGER)""")
    for name, tier in repos:
        conn.execute("INSERT INTO repos (full_name, ai_related, worth_tier) VALUES (?,1,?)", (name, tier))
    for name, date, rank, total, today in snapshots:
        conn.execute("INSERT INTO daily_snapshots (full_name, snapshot_date, trending_page, rank, "
                     "stars_total, stars_today) VALUES (?,?,'all',?,?,?)", (name, date, rank, total, today))
    conn.commit()
    conn.close()


class TestTrendingOrder(unittest.TestCase):
    def run_export(self, repos, snapshots, limit=6):
        tmp = Path(tempfile.mkdtemp())
        build_db(tmp / "t.db", repos, snapshots)
        orig = (export_trending.DB_PATH, export_trending.OUT_PATH, export_trending.TRENDING_DAILY_LIMIT)
        export_trending.DB_PATH = str(tmp / "t.db")
        export_trending.OUT_PATH = tmp / "out.json"
        export_trending.TRENDING_DAILY_LIMIT = limit
        try:
            export_trending.export()
            return json.loads((tmp / "out.json").read_text(encoding="utf-8"))["items"]
        finally:
            (export_trending.DB_PATH, export_trending.OUT_PATH,
             export_trending.TRENDING_DAILY_LIMIT) = orig

    def test_sorts_by_period_gain_not_total_stars(self):
        # 常驻大仓库(20万star但这期只涨40)不该压过这期真的在涨的新仓库
        items = self.run_export(
            repos=[("old/giant", "high"), ("new/hot", "high")],
            snapshots=[("old/giant", "2026-08-16", 20, 200000, 40),
                       ("new/hot", "2026-08-16", 1, 5000, 9000)],
        )
        self.assertEqual([i["full_name"] for i in items], ["new/hot", "old/giant"])

    def test_tier_still_wins_over_gain(self):
        # tier优先那层不能动：medium涨得再多也排在high后面
        items = self.run_export(
            repos=[("a/high", "high"), ("b/medium", "medium")],
            snapshots=[("a/high", "2026-08-16", 30, 100, 10),
                       ("b/medium", "2026-08-16", 1, 100, 99999)],
        )
        self.assertEqual([i["full_name"] for i in items], ["a/high", "b/medium"])

    def test_repo_absent_from_latest_crawl_is_dropped(self):
        # 掉出榜单的仓库不能带着上一期的旧涨幅继续占位
        items = self.run_export(
            repos=[("stale/wasHot", "high"), ("fresh/nowHot", "high")],
            snapshots=[("stale/wasHot", "2026-08-09", 1, 5000, 20000),
                       ("fresh/nowHot", "2026-08-16", 3, 5000, 500)],
        )
        self.assertEqual([i["full_name"] for i in items], ["fresh/nowHot"])

    def test_exports_period_gain_for_frontend(self):
        # 排序依据要导出给前端显示，否则页面顺序没有可见理由
        items = self.run_export(
            repos=[("a/b", "high")],
            snapshots=[("a/b", "2026-08-16", 1, 5000, 777)],
        )
        self.assertEqual(items[0]["stars_period"], 777)
