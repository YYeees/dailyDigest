"""
排序流程的读写接口,给Claude Code(手动跑或/schedule云端agent)调用,不做判断本身——
判断标准见RANKING_CRITERIA.md,由读这份文档的Claude Code现场推理产出。

用法:
    python scripts/rank_items.py pending [--limit N] [--source-type blog]
        列出digest.db里ranked_at IS NULL的条目(JSON数组,写到stdout)。

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

DB_PATH = "digest.db"
VALID_TIERS = {"high", "medium", "low"}
# 月份选择器起始范围从七月开始(2026-08-13定案),更早的历史归档内容(比如部分blog feed
# 暴露的全量历史文章)永远不会展示,不需要排序,查询时直接排除。
DIGEST_START_DATE = "2026-07-01"


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

    rows = [dict(row) for row in conn.execute(query, params)]
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
    p_pending.add_argument("--source-type", default=None, choices=["blog", "podcast", "youtube"])
    p_pending.set_defaults(func=cmd_pending)

    p_write = sub.add_parser("write", help="写回排序结果")
    p_write.add_argument("results_file")
    p_write.set_defaults(func=cmd_write)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
