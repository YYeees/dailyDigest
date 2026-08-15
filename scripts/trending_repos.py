"""
GitHub Trending AI评估流程的读写接口,给Claude Code(手动跑或headless claude)调用,不做判断本身——
判断标准见GITHUB_TRENDING_CRITERIA.md,由读这份文档的Claude Code现场读README推理产出。

用法:
    python scripts/trending_repos.py pending [--limit N]
        列出repos表里evaluated_at IS NULL的仓库(JSON数组,写到stdout)。

    python scripts/trending_repos.py write results.json
        把评估结果写回digest.db。results.json是数组,每个元素:
        {"full_name": "owner/repo", "ai_related": true|false,
         "difficulty": "beginner|intermediate|advanced" 或 null(ai_related为false时留空),
         "worth_tier": "high|medium|low" 或 null,
         "recommend_reason": "..."}
        evaluated_at自动写当前时间。
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = "digest.db"
VALID_DIFFICULTY = {"beginner", "intermediate", "advanced"}
VALID_WORTH_TIER = {"high", "medium", "low"}


def cmd_pending(args):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = (
        "SELECT full_name, url, description, primary_language, first_seen_date "
        "FROM repos WHERE evaluated_at IS NULL ORDER BY first_seen_date ASC"
    )
    params = []
    if args.limit:
        query += " LIMIT ?"
        params.append(args.limit)

    rows = [dict(row) for row in conn.execute(query, params)]
    conn.close()
    json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
    print(f"\n共{len(rows)}个仓库待评估", file=sys.stderr)


def cmd_write(args):
    with open(args.results_file, encoding="utf-8") as f:
        results = json.load(f)

    for r in results:
        if "full_name" not in r:
            raise ValueError(f"缺少full_name: {r}")
        if not isinstance(r.get("ai_related"), bool):
            raise ValueError(f"ai_related必须是true/false: {r}")
        if r["ai_related"]:
            if r.get("difficulty") not in VALID_DIFFICULTY:
                raise ValueError(f"difficulty取值必须是beginner/intermediate/advanced: {r}")
            if r.get("worth_tier") not in VALID_WORTH_TIER:
                raise ValueError(f"worth_tier取值必须是high/medium/low: {r}")

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    not_found = []
    for r in results:
        cur = conn.execute(
            """UPDATE repos SET ai_related=?, difficulty=?, worth_tier=?,
               recommend_reason=?, evaluated_at=? WHERE full_name=?""",
            (
                int(r["ai_related"]), r.get("difficulty"), r.get("worth_tier"),
                r.get("recommend_reason", ""), now, r["full_name"],
            ),
        )
        if cur.rowcount:
            updated += 1
        else:
            not_found.append(r["full_name"])
    conn.commit()
    conn.close()

    print(f"写入{updated}条", file=sys.stderr)
    if not_found:
        print(f"警告:{len(not_found)}个full_name在库里找不到,未写入: {not_found}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_pending = sub.add_parser("pending", help="列出待评估仓库")
    p_pending.add_argument("--limit", type=int, default=None)
    p_pending.set_defaults(func=cmd_pending)

    p_write = sub.add_parser("write", help="写回评估结果")
    p_write.add_argument("results_file")
    p_write.set_defaults(func=cmd_write)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
