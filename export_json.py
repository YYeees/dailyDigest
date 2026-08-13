"""
把digest.db按发布月份分桶,导出成docs/data/digest_YYYY-MM.json供前端fetch。
月份桶用published字段判断(不是first_seen_at——见memory里的决定:有了月份选择器,
内容按自己真实发布月份归类,用户随时能翻回任意月份看,不存在"被排除"的问题)。
只导出low以外的条目(low的还留在数据库里,只是不进呈现层)。
同时维护一份 docs/data/months.json,列出当前有哪些月份可选(供月份选择器用)。
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH = "digest.db"
OUT_DIR = Path("docs/data")


def item_dict(row):
    return {
        "person": row["person"],
        "title": row["title"],
        "link": row["link"],
        "date": row["published"][:10] if row["published"] else None,
        "source_type": row["source_type"],
    }


def export():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    months = defaultdict(lambda: {
        "ai_track": {"high": [], "medium": []},
        "anchor_track": {"high": [], "medium": []},
    })

    for row in conn.execute("""
        SELECT * FROM items
        WHERE published IS NOT NULL AND published >= '2026-07-01'
          AND (ai_tier IN ('high','medium') OR anchor_tier IN ('high','medium'))
        ORDER BY published DESC
    """):
        month = row["published"][:7]  # YYYY-MM
        bucket = months[month]

        if row["ai_tier"] in ("high", "medium"):
            entry = item_dict(row)
            entry["reason"] = row["ai_reason"] or ""
            entry["summary"] = row["digest_summary"]  # None if not generated yet
            bucket["ai_track"][row["ai_tier"]].append(entry)

        if row["anchor_tier"] in ("high", "medium"):
            entry = item_dict(row)
            entry["reason"] = row["anchor_reason"] or ""
            entry["summary"] = row["digest_summary"]
            bucket["anchor_track"][row["anchor_tier"]].append(entry)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for month, data in months.items():
        path = OUT_DIR / f"digest_{month}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] {path} — ai:{len(data['ai_track']['high'])+len(data['ai_track']['medium'])}条 "
              f"anchor:{len(data['anchor_track']['high'])+len(data['anchor_track']['medium'])}条")

    months_list = sorted(months.keys(), reverse=True)
    (OUT_DIR / "months.json").write_text(
        json.dumps({"months": months_list}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] months.json — {months_list}")

    conn.close()


if __name__ == "__main__":
    export()
