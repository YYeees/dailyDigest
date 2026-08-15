"""
导出"最近N天"视图，供"7日内关注"页面(docs/index.html)用：
- docs/data/recent.json   —— 去重后的单一列表，每条带`tracks`字段(命中了AI/锚点里的哪个/哪些，
  以及各自的tier)，最近RECENT_WINDOW_DAYS天
- docs/data/x_recent.json —— X来源，扁平列表，不限tier，最近RECENT_WINDOW_DAYS天

2026-08-15定案的统一规则(替代之前的flow/feature分类)：
- 不管来源是谁，high/medium都能进recent.json——不再有"这个人算不算flow"的判断。
- 例外：config.HIGH_ONLY_PERSONS里的人(目前只有Simon Willison)，medium档不展示(更新太勤，
  量太大)，且他们在每个track的high档也设了数量上限(HIGH_ONLY_PERSON_LIMIT)，避免一个人
  占满整个板块。
- X单独一份扁平列表，不限tier——用户要的是"知道更新了、大概聊了什么"，不是被优先级过滤掉
  的精选，所以X每条都要有digest_summary(哪怕low)。

2026-08-15追加：同一条内容如果AI/锚点两个track都命中，只出现一次，`tracks`字段里带两条
(而不是像之前那样在两个独立的track区块里各出现一次)——前端用这个字段在卡片右上角画track徽章。

跟export_json.py(月度归档)是互补关系：recent.json里的high档内容，同一条也会出现在月度归档里
(那边是永久归档，这里是"最近发生了什么"的快速脉冲，两者用途不同，不冲突)。
"""

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DB_PATH, HIGH_ONLY_PERSON_LIMIT, HIGH_ONLY_PERSONS, RECENT_WINDOW_DAYS

OUT_DIR = Path("docs/data")
TIER_ORDER = {"high": 0, "medium": 1}
TRACKS = (("ai", "ai_tier", "ai_reason"), ("anchor", "anchor_tier", "anchor_reason"))


def best_tier(ai_tier, anchor_tier):
    order = {"high": 0, "medium": 1, "low": 2}
    tiers = [t for t in (ai_tier, anchor_tier) if t]
    return min(tiers, key=lambda t: order.get(t, 9)) if tiers else "low"


def export():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENT_WINDOW_DAYS)).isoformat()

    recent_items = []
    high_only_counts = defaultdict(int)  # (track_name, person) -> 已经放了几条

    for row in conn.execute("""
        SELECT * FROM items
        WHERE published >= ? AND ranked_at IS NOT NULL AND source_type != 'x'
        ORDER BY published DESC
    """, (cutoff,)):
        person = row["person"]
        high_only = person in HIGH_ONLY_PERSONS

        tracks = []
        for track_name, tier_field, reason_field in TRACKS:
            tier = row[tier_field]
            if tier not in ("high", "medium"):
                continue
            if high_only and tier == "medium":
                continue
            if high_only and tier == "high":
                key = (track_name, person)
                if high_only_counts[key] >= HIGH_ONLY_PERSON_LIMIT:
                    continue
                high_only_counts[key] += 1
            tracks.append({"track": track_name, "tier": tier, "reason": row[reason_field] or ""})

        if not tracks:
            continue

        recent_items.append({
            "person": row["person"],
            "title": row["title"],
            "link": row["link"],
            "date": row["published"][:10] if row["published"] else None,
            "source_type": row["source_type"],
            "summary": row["digest_summary"],
            "tracks": tracks,
        })

    recent_items.sort(key=lambda i: i["date"], reverse=True)
    recent_items.sort(key=lambda i: min(TIER_ORDER[t["tier"]] for t in i["tracks"]))

    x_items = []
    for row in conn.execute("""
        SELECT * FROM items
        WHERE published >= ? AND ranked_at IS NOT NULL AND source_type = 'x'
        ORDER BY published DESC
    """, (cutoff,)):
        x_items.append({
            "person": row["person"],
            "title": row["title"],
            "link": row["link"],
            "date": row["published"][:10] if row["published"] else None,
            "source_type": row["source_type"],
            "summary": row["digest_summary"],
            "tier": best_tier(row["ai_tier"], row["anchor_tier"]),
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    recent_path = OUT_DIR / "recent.json"
    recent_path.write_text(json.dumps({"items": recent_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {recent_path} — {len(recent_items)}条 (最近{RECENT_WINDOW_DAYS}天)")

    x_path = OUT_DIR / "x_recent.json"
    x_path.write_text(json.dumps({"items": x_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {x_path} — {len(x_items)}条 (最近{RECENT_WINDOW_DAYS}天)")

    conn.close()


if __name__ == "__main__":
    export()
