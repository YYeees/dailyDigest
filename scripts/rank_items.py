"""
排序流程的读写接口,给Claude Code(手动跑或/schedule云端agent)调用,不做判断本身——
判断标准见RANKING_CRITERIA.md,由读这份文档的Claude Code现场推理产出。

用法:
    python scripts/rank_items.py pending [--limit N] [--source-type blog]
        列出digest.db里ranked_at IS NULL的条目(JSON数组,写到stdout)。每条额外带三个
        路由标记(规则定义在config.py,不用去记RANKING_CRITERIA.md里的文字规则):
        - body_source: 这条内容的正文从哪来,决定走哪条路径(三选一):
            "rss"   正文已经在库里(fetch时从RSS存的),`content`字段直接给,**不用WebFetch**
            "fetch" 库里没有或被源截断,且source_type允许深读 → 初筛medium/high时WebFetch原文
            "none"  没有全文可用(podcast/youtube/x) → 基于summary轻提炼
        - always_summarize: 不管tier判成什么都要写digest_summary
        - content_chars: 库里存的正文有多长(0=这个源的RSS没给正文)。正文在write时被清空。

    python scripts/rank_items.py write results.json
        把判断结果写回digest.db。results.json是数组,每个元素:
        {"guid": "...", "ai_tier": "high|medium|low", "ai_reason": "...",
         "anchor_tier": "high|medium|low", "anchor_reason": "...",
         "digest_summary": "..." 或 null,
         "excluded_reason": "..." 或 null(可选,不传等价于null)}
        ranked_at自动写当前时间,同时把content清空——正文只在排序那一次用得上,排完留着
        只会让digest.db(每天提交进git)无限膨胀。要留的是digest_summary,不是原文。
        excluded_reason不为空时,不管tier判成什么,导出时都不展示
        (内容主题层面的排除,标准见RANKING_CRITERIA.md，比如某人重复的口水话题/无关个人生活)。
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (  # noqa: E402
    ALWAYS_ARCHIVE_TITLE_PREFIXES, ALWAYS_SUMMARIZE_TYPES, DB_PATH, DEEP_READ_ELIGIBLE_TYPES,
    DIGEST_START_DATE, PENDING_CONTENT_BUDGET, VALID_TIERS,
)
from content_extract import is_truncated  # noqa: E402


def cmd_pending(args):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = (
        "SELECT guid, person, source_name, source_type, title, link, published, summary, content "
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
    budget, spent, over_budget = args.content_budget, 0, 0
    for row in conn.execute(query, params):
        item = dict(row)
        item["always_summarize"] = (
            item["source_type"] in ALWAYS_SUMMARIZE_TYPES
            or any(item["title"].startswith(p) for p in ALWAYS_ARCHIVE_TITLE_PREFIXES)
        )
        body = item.pop("content", None)
        item["content_chars"] = len(body or "")

        # 正文已经在库里(fetch时从RSS存的)就直接给，不用再去WebFetch同一个链接下载一遍。
        # 超出本次预算的退回"fetch"走老路径——多抓一次总比把上下文撑爆强。
        have_body = args.with_content and not is_truncated(body)
        give_body = have_body and spent + len(body) <= budget
        over_budget += have_body and not give_body
        if give_body:
            item["body_source"] = "rss"
            item["content"] = body
            spent += len(body)
        elif item["source_type"] in DEEP_READ_ELIGIBLE_TYPES:
            item["body_source"] = "fetch"
        else:
            item["body_source"] = "none"
        rows.append(item)
    conn.close()
    json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
    kinds = Counter(r["body_source"] for r in rows)
    print(f"\n共{len(rows)}条待排序 (正文来源: "
          f"rss={kinds['rss']} fetch={kinds['fetch']} none={kinds['none']}, "
          f"已用正文预算{spent:,}/{budget:,}字符)", file=sys.stderr)
    if over_budget:
        print(f"警告:正文预算不够,{over_budget}条明明库里有正文却退回了fetch。"
              "配合--limit分批,或调大--content-budget。", file=sys.stderr)


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
               digest_summary=?, excluded_reason=?, ranked_at=?, content=NULL WHERE guid=?""",
            (
                r["ai_tier"], r.get("ai_reason", ""),
                r["anchor_tier"], r.get("anchor_reason", ""),
                r.get("digest_summary"), r.get("excluded_reason"), now, r["guid"],
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
    p_pending.add_argument("--with-content", action="store_true",
                           help="连RSS正文一起吐出来(默认只给content_chars,正文可能很大)")
    p_pending.add_argument("--content-budget", type=int, default=PENDING_CONTENT_BUDGET,
                           help="本次最多吐多少字符的正文,超出的条目退回body_source=fetch")
    p_pending.set_defaults(func=cmd_pending)

    p_write = sub.add_parser("write", help="写回排序结果")
    p_write.add_argument("results_file")
    p_write.set_defaults(func=cmd_write)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
