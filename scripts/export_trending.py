"""
把repos表里ai_related=1且worth_tier是high/medium的仓库导出成docs/data/trending.json供前端fetch。
(worth_tier=low的仓库留在库里，不进展示层——跟digest的low处理方式一致)
每个仓库取最新一天的daily_snapshots数据(star数)；同一天可能因为出现在多个语言榜而有多条快照，
取排名最靠前的那条。

2026-08-15定案：不用展示太多，按tier→star数排完序只取综合最值得推荐的前
config.TRENDING_DAILY_LIMIT个，不是把评估过的仓库全部展示出来。
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, TRENDING_DAILY_LIMIT  # noqa: E402

OUT_PATH = Path("docs/data/trending.json")


def export():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    repos = conn.execute("""
        SELECT * FROM repos
        WHERE ai_related = 1 AND worth_tier IN ('high', 'medium')
    """).fetchall()

    items = []
    for repo in repos:
        snapshot = conn.execute("""
            SELECT * FROM daily_snapshots
            WHERE full_name = ?
            ORDER BY snapshot_date DESC, rank ASC
            LIMIT 1
        """, (repo["full_name"],)).fetchone()

        items.append({
            "full_name": repo["full_name"],
            "url": repo["url"],
            "description": repo["description"],
            "language": repo["primary_language"],
            "difficulty": repo["difficulty"],
            "worth_tier": repo["worth_tier"],
            "recommend_reason": repo["recommend_reason"],
            "first_seen_date": repo["first_seen_date"],
            "stars_total": snapshot["stars_total"] if snapshot else None,
            "last_snapshot_date": snapshot["snapshot_date"] if snapshot else None,
        })

    tier_order = {"high": 0, "medium": 1}
    items.sort(key=lambda i: (tier_order.get(i["worth_tier"], 9), -(i["stars_total"] or 0)))
    items = items[:TRENDING_DAILY_LIMIT]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {OUT_PATH} — {len(items)}个仓库(上限{TRENDING_DAILY_LIMIT}) "
          f"(high:{sum(1 for i in items if i['worth_tier']=='high')} "
          f"medium:{sum(1 for i in items if i['worth_tier']=='medium')})")

    conn.close()


if __name__ == "__main__":
    export()
