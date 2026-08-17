"""
把digest.db按发布月份分桶,导出成docs/data/digest_YYYY-MM.json供前端fetch。
月份桶用published字段判断(不是first_seen_at——见memory里的决定:有了月份选择器,
内容按自己真实发布月份归类,用户随时能翻回任意月份看,不存在"被排除"的问题)。

2026-08-15定案的统一归档规则(替代之前的flow/feature分类)：**只有high档进月度归档，
不管来源是谁**。medium档不管来源一律不归档，只在"7日内关注"页面的7天窗口内展示
(见export_recent.py)——这样不用再判断"这个人算不算flow"，规则对所有来源一致。

`items`字段是去重后的单一列表——同一条内容如果AI/锚点两个track都命中high，只出现一次，
`tracks`字段里带两条(而不是像之前那样`ai_track`/`anchor_track`两个独立结构里各出现一次)，
前端用这个字段在卡片右上角画track徽章。

`github_track`字段：repos表里worth_tier='high'的仓库，按`first_seen_date`的月份归档
(同样的道理：只归档high，medium只在Trending板块展示)。GitHub Trending本身是周期性快照
(2026-08-15起每周跑一次)、不是增量流(同一仓库可能连续好几周都在榜上)，但"我们第一次发现它"
这个时刻对用户来说仍然是真实的一次性事件，所以用`first_seen_date`分月份是合理的——不代表
"这个项目这个月诞生"，代表"这个月被收进清单"。这份月度导出没有"3次覆盖"之类的特殊机制，
每次跑(现在是每周)都是从数据库当前状态全量重新生成，天然就是最新状态。
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from config import ALWAYS_ARCHIVE_TITLE_PREFIXES, DB_PATH, DIGEST_START_DATE, TRENDING_MONTHLY_LIMIT
from export_recent import to_beijing_date


def always_archive(title):
    return any(title.startswith(p) for p in ALWAYS_ARCHIVE_TITLE_PREFIXES)

OUT_DIR = Path("docs/data")


def item_dict(row):
    return {
        "person": row["person"],
        "title": row["title"],
        "link": row["link"],
        "date": row["published"][:10] if row["published"] else None,
        "first_seen": to_beijing_date(row["first_seen_at"]),
        "source_type": row["source_type"],
    }


def latest_stars(conn, full_name):
    snapshot = conn.execute("""
        SELECT stars_total FROM daily_snapshots
        WHERE full_name = ?
        ORDER BY snapshot_date DESC, rank ASC
        LIMIT 1
    """, (full_name,)).fetchone()
    return snapshot["stars_total"] if snapshot else None


def repo_dict(conn, row):
    return {
        "full_name": row["full_name"],
        "url": row["url"],
        "description": row["description"],
        "language": row["primary_language"],
        "difficulty": row["difficulty"],
        "recommend_reason": row["recommend_reason"],
        "stars_total": latest_stars(conn, row["full_name"]),
    }


TRACKS = (("ai", "ai_tier", "ai_reason"), ("anchor", "anchor_tier", "anchor_reason"))


def export():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    months = defaultdict(lambda: {"items": [], "github_track": []})

    for row in conn.execute("""
        SELECT * FROM items
        WHERE published IS NOT NULL AND published >= ? AND excluded_reason IS NULL
          AND (ai_tier = 'high' OR anchor_tier = 'high' OR digest_summary IS NOT NULL)
        ORDER BY published DESC
    """, (DIGEST_START_DATE,)):
        if not (row["ai_tier"] == "high" or row["anchor_tier"] == "high" or always_archive(row["title"])):
            continue
        month = row["published"][:7]  # YYYY-MM

        tracks = []
        for track_name, tier_field, reason_field in TRACKS:
            if row[tier_field] == "high":
                tracks.append({"track": track_name, "tier": "high", "reason": row[reason_field] or ""})

        if not tracks and always_archive(row["title"]):
            # Ridgeline没到high档也被强制归档——锚点track保底显示成medium(不覆盖真实判断结果)。
            tracks.append({
                "track": "anchor", "tier": "medium",
                "reason": row["anchor_reason"] or "Craig Mod Ridgeline，用户偏好锚点内容",
            })

        entry = item_dict(row)
        entry["summary"] = row["digest_summary"]
        entry["tracks"] = tracks
        months[month]["items"].append(entry)

    for row in conn.execute("""
        SELECT * FROM repos
        WHERE ai_related = 1 AND worth_tier = 'high' AND first_seen_date >= ?
        ORDER BY first_seen_date DESC
    """, (DIGEST_START_DATE,)):
        month = row["first_seen_date"][:7]
        months[month]["github_track"].append(repo_dict(conn, row))

    # 不用展示太多，每个月只留综合最值得推荐的前TRENDING_MONTHLY_LIMIT个(按star数排序)
    for data in months.values():
        data["github_track"].sort(key=lambda r: -(r["stars_total"] or 0))
        data["github_track"] = data["github_track"][:TRENDING_MONTHLY_LIMIT]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for month, data in months.items():
        path = OUT_DIR / f"digest_{month}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] {path} — {len(data['items'])}条内容 github:{len(data['github_track'])}个")

    months_list = sorted(months.keys(), reverse=True)
    (OUT_DIR / "months.json").write_text(
        json.dumps({"months": months_list}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] months.json — {months_list}")

    conn.close()


if __name__ == "__main__":
    export()
