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

2026-08-16追加两条：
- HIGH_ONLY_PERSONS里的人，发布在HIGH_ONLY_RECENT_DAYS天以内的内容不分tier全部展示(哪怕
  low)，超过这个窗口才收紧回"只看high档"——用户想第一时间看到他们的动态，不想被判断结果挡住。
- `excluded_reason`不为空的条目，不管来源/tier，一律不展示——给内容主题层面的排除用(比如
  Ray Dalio重复的principles语录、跟工作无关的个人生活动态)，判断标准见RANKING_CRITERIA.md，
  由排序时的Claude Code现场判断，不是关键词硬匹配。

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

from config import (
    ALWAYS_ARCHIVE_TITLE_PREFIXES, DB_PATH, HIGH_ONLY_PERSON_LIMIT, HIGH_ONLY_PERSONS,
    HIGH_ONLY_RECENT_DAYS, RECENT_WINDOW_DAYS,
)


def always_archive(title):
    return any(title.startswith(p) for p in ALWAYS_ARCHIVE_TITLE_PREFIXES)

OUT_DIR = Path("docs/data")
TRACKS = (("ai", "ai_tier", "ai_reason"), ("anchor", "anchor_tier", "anchor_reason"))


def best_tier(ai_tier, anchor_tier):
    order = {"high": 0, "medium": 1, "low": 2}
    tiers = [t for t in (ai_tier, anchor_tier) if t]
    return min(tiers, key=lambda t: order.get(t, 9)) if tiers else "low"


def export():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENT_WINDOW_DAYS)).isoformat()
    high_only_recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=HIGH_ONLY_RECENT_DAYS)).isoformat()

    recent_items = []
    high_only_counts = defaultdict(int)  # (track_name, person) -> 已经放了几条

    for row in conn.execute("""
        SELECT * FROM items
        WHERE published >= ? AND ranked_at IS NOT NULL AND source_type != 'x'
          AND excluded_reason IS NULL
        ORDER BY published DESC
    """, (cutoff,)):
        person = row["person"]
        high_only = person in HIGH_ONLY_PERSONS
        high_only_recent = high_only and row["published"] >= high_only_recent_cutoff

        tracks = []
        for track_name, tier_field, reason_field in TRACKS:
            tier = row[tier_field]
            if high_only_recent:
                # HIGH_ONLY_RECENT_DAYS天以内：不分tier全部展示，low档保底显示成medium
                # (不覆盖数据库里真实的判断结果，只是展示层的下限)。
                tracks.append({
                    "track": track_name, "tier": tier if tier in ("high", "medium") else "medium",
                    "reason": row[reason_field] or "",
                })
                continue
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

        if not tracks and always_archive(row["title"]):
            # Ridgeline：ai/anchor两个track都没到medium，但用户明确要求不管tier全展示——
            # 归到锚点track，tier保底显示成medium(不覆盖数据库里的真实判断结果)。
            tracks.append({
                "track": "anchor", "tier": "medium",
                "reason": row["anchor_reason"] or "Craig Mod Ridgeline，用户偏好锚点内容",
            })

        if not tracks:
            continue

        recent_items.append({
            "person": row["person"],
            "title": row["title"],
            "link": row["link"],
            "date": row["published"][:10] if row["published"] else None,
            "first_seen": row["first_seen_at"][:10] if row["first_seen_at"] else None,
            "source_type": row["source_type"],
            "summary": row["digest_summary"],
            "tracks": tracks,
        })

    recent_items.sort(key=lambda i: i["date"], reverse=True)

    x_items = []
    for row in conn.execute("""
        SELECT * FROM items
        WHERE published >= ? AND ranked_at IS NOT NULL AND source_type = 'x'
          AND excluded_reason IS NULL
        ORDER BY published DESC
    """, (cutoff,)):
        x_items.append({
            "person": row["person"],
            "title": row["title"],
            "link": row["link"],
            "date": row["published"][:10] if row["published"] else None,
            "first_seen": row["first_seen_at"][:10] if row["first_seen_at"] else None,
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
