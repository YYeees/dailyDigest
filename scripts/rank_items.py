"""
排序流程的读写接口,给Claude Code(手动跑或/schedule云端agent)调用,不做判断本身——
判断标准见RANKING_CRITERIA.md,由读这份文档的Claude Code现场推理产出。

用法:
    python scripts/rank_items.py pending [--limit N] [--source-type blog]
        列出digest.db里ranked_at IS NULL的条目(JSON数组,写到stdout)。每条额外带两个
        路由标记(规则定义在config.py,不用去记RANKING_CRITERIA.md里的文字规则):
        - deep_read_eligible: 初筛medium/high后要不要WebFetch全文精判
        - always_summarize: 不管tier判成什么都要写digest_summary

    python scripts/rank_items.py write results.json
        把判断结果写回digest.db。results.json是数组,每个元素:
        {"guid": "...", "ai_tier": "high|medium|low", "ai_reason": "...",
         "anchor_tier": "high|medium|low", "anchor_reason": "...",
         "digest_summary": "..." 或 null}
        ranked_at自动写当前时间。
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (  # noqa: E402
    ALWAYS_ARCHIVE_TITLE_PREFIXES, ALWAYS_SUMMARIZE_TYPES, DB_PATH, DEEP_READ_ELIGIBLE_TYPES,
    DIGEST_START_DATE, VALID_TIERS,
)


def cmd_pending(args):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = (
        "SELECT guid, person, source_name, source_type, title, link, published, summary "
        "FROM items WHERE ranked_at IS NULL AND published >= ?"
    )
    params = [DIGEST_START_DATE]
    if args.source_type:
        query += " AND source_type = ?"
        params.append(args.source_type)
    query += " ORDER BY published ASC"
    if args.limit:
        query += " LIMIT ?"
        params.append(args.limit)

    rows = []
    for row in conn.execute(query, params):
        item = dict(row)
        item["deep_read_eligible"] = item["source_type"] in DEEP_READ_ELIGIBLE_TYPES
        item["always_summarize"] = (
            item["source_type"] in ALWAYS_SUMMARIZE_TYPES
            or any(item["title"].startswith(p) for p in ALWAYS_ARCHIVE_TITLE_PREFIXES)
        )
        rows.append(item)
    conn.close()
    json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
    print(f"\n共{len(rows)}条待排序", file=sys.stderr)


def cmd_write(args):
    with open(args.results_file, encoding="utf-8") as f:
        results = json.load(f)

    for r in results:
        if "guid" not in r:
            raise ValueError(f"缺少guid: {r}")
        if r.get("ai_tier") not in VALID_TIERS or r.get("anchor_tier") not in VALID_TIERS:
            raise ValueError(f"tier取值必须是high/medium/low: {r}")

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    not_found = []
    for r in results:
        cur = conn.execute(
            """UPDATE items SET ai_tier=?, ai_reason=?, anchor_tier=?, anchor_reason=?,
               digest_summary=?, ranked_at=? WHERE guid=?""",
            (
                r["ai_tier"], r.get("ai_reason", ""),
                r["anchor_tier"], r.get("anchor_reason", ""),
                r.get("digest_summary"), now, r["guid"],
            ),
        )
        if cur.rowcount:
            updated += 1
        else:
            not_found.append(r["guid"])
    conn.commit()
    conn.close()

    print(f"写入{updated}条", file=sys.stderr)
    if not_found:
        print(f"警告:{len(not_found)}个guid在库里找不到,未写入: {not_found}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_pending = sub.add_parser("pending", help="列出待排序条目")
    p_pending.add_argument("--limit", type=int, default=None)
    p_pending.add_argument("--source-type", default=None, choices=["blog", "podcast", "youtube", "x"])
    p_pending.set_defaults(func=cmd_pending)

    p_write = sub.add_parser("write", help="写回排序结果")
    p_write.add_argument("results_file")
    p_write.set_defaults(func=cmd_write)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
