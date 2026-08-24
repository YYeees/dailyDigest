"""
把写作收件箱(~/uxye/writing-inbox)里的临时笔记匹配回digest.db,接上"排序判断 → 我是否
真的用上"这条反馈回路。

设计前提(2026-08-24定):
- 用户对digest是**全覆盖读**的(每条都读或粗扫),所以"这条没有笔记"真的等于"当时对我
  没用",不是"漏读了"。这让只记正面信号(写了笔记=有用)的做法成立——一般系统不敢这么做,
  因为分不清"不喜欢"和"没看到"。
- "有用"是**非平稳**的:同一条内容今天没用、三个月后可能正好用上,变的是读者不是内容。
  所以判断带时间戳、允许同一条内容以后再被记一次,不做"虚警"这种一次性定论。
- **不往digest.db写任何东西**。digest.db每天commit进public repo,而"我觉得哪些文章有用"
  是私人信号。索引只写inbox目录下的`.scan_index.json`(在仓库外,且Obsidian隐藏dotfile)。
  以后如果确认可以公开,再搬进库里也不迟——反过来搬不回来。

用法:
    python scripts/scan_inbox.py            扫描 + 报告匹配情况
    python scripts/scan_inbox.py --eval     再算一次eval:排序判的档位 vs 你实际记了笔记的
    python scripts/scan_inbox.py --unmatched  只列出没匹配上的笔记(排查用)
    --inbox PATH 覆盖收件箱位置(默认 $WRITING_INBOX 或 ~/uxye/writing-inbox)
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH  # noqa: E402

DEFAULT_INBOX = Path(os.environ.get("WRITING_INBOX", "~/uxye/writing-inbox")).expanduser()
INDEX_NAME = ".scan_index.json"
SKIP_FILES = {"README.md"}

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
# 正文里第一个指向http(s)的markdown链接 —— `[文章标题](链接)`
MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")


def parse_note(path):
    """取一条笔记的来源URL和日期。

    URL优先从正文第一个markdown链接里取——`[文章标题](链接)`,digest页面「记一笔」就是
    这么生成的。用它而不是在frontmatter里塞一行裸URL,是因为笔记是给人读的:三个月后翻
    回来看见的该是标题,点一下能回去重读原文(2026-08-24用户提的)。
    frontmatter里的`url:`作为退路保留,手工建的笔记两种写法都认。

    frontmatter里的`source`是**信息来源名**(人或刊物,如"Simon Willison"/"Latent Space"),
    不是URL——2026-08-24之前它装的是URL,所以这里对`source:`额外留一手:值看起来像URL就
    仍当URL收下,不像就当来源名。

    只扫开头4000字符、只取这几个字段,**不读也不保留正文内容**——正文是私人的,这个脚本
    没有任何理由把它读进内存或写到别处去。
    """
    head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    fields = {}
    m = FRONTMATTER_RE.match(head)
    body = head
    if m:
        body = head[m.end():]
        for line in m.group(1).splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip().strip("\"'")
            if key == "date":
                fields["date"] = value
            elif key == "url":
                fields["url"] = value
            elif key == "source":
                # 旧格式(source装URL)和新格式(source装来源名)都认
                fields["url" if value.startswith(("http://", "https://")) else "person"] = value
    link = MD_LINK_RE.search(body)
    if link:
        fields["url"] = link.group(1).strip()
    return fields


# 只剥掉确定是追踪用的query参数。**不能整段剥掉query**——2026-08-24第一版就是这么写的,
# 结果 https://www.youtube.com/watch?v=XXX 全部归一化成同一个key,一条笔记匹配上了库里
# 全部17条YouTube内容,eval数字直接判歪。lexfridman的 ?p=6494 同理,query里装的是主键。
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm",
    "ref", "ref_src", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid",
}

# 一个归一化key正常只该对应1~2条(同一篇从两个feed进来过,见nav.al那两个源)。超过这个数
# 说明归一化又把不同URL压成一个key了,宁可判成"没匹配上"让人来查,也不要静默算出错的eval。
LOOSE_MATCH_CAP = 3


def norm_url(url):
    """宽松匹配用。digest页面「记一笔」生成的source跟库里link逐字节相同,精确匹配就够;
    这一层只给手工粘链接的条目兜底(http/https、www、尾斜杠、追踪参数)。"""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    if not parts.netloc:
        return url.strip().rstrip("/")
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = urlencode([
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ])
    # path大小写保留:simonwillison.net/2026/Aug/20/... 这类路径是区分大小写的。
    return urlunsplit(("https", netloc, parts.path.rstrip("/"), query, ""))


def load_items(conn):
    exact, loose = {}, {}
    for row in conn.execute(
        "SELECT guid, link, title, person, published, ai_tier, anchor_tier, ranked_at FROM items"
    ):
        item = dict(zip(
            ["guid", "link", "title", "person", "published", "ai_tier", "anchor_tier", "ranked_at"], row
        ))
        exact.setdefault(item["link"], []).append(item)
        loose.setdefault(norm_url(item["link"]), []).append(item)
    return exact, loose


def scan(inbox, conn):
    exact, loose = load_items(conn)
    notes = []
    for path in sorted(inbox.rglob("*.md")):
        if path.name in SKIP_FILES or path.name.startswith("."):
            continue
        fm = parse_note(path)
        source = fm.get("url", "")
        rel = str(path.relative_to(inbox))
        matched = exact.get(source)
        if matched is None and source:
            candidates = loose.get(norm_url(source))
            # 命中太多 = 归一化把不同URL压成了一个key,是bug不是巧合。判成未匹配让人来查。
            matched = candidates if candidates and len(candidates) <= LOOSE_MATCH_CAP else None
        notes.append({
            "note": rel,
            "date": fm.get("date", ""),
            "person": fm.get("person", ""),
            "url": source,
            # 同一个link可能对应多条记录(同一篇文章从两个feed进来过,见nav.al那两个源),
            # 全部记上——它们各自被独立判过tier,eval时两条都该算。
            "guids": [m["guid"] for m in matched] if matched else [],
            "status": "matched" if matched else ("no_source" if not source else "unmatched"),
        })
    return notes


def write_index(inbox, notes):
    index = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "inbox": str(inbox),
        "notes": notes,
    }
    (inbox / INDEX_NAME).write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def report(notes):
    counts = Counter(n["status"] for n in notes)
    print(f"收件箱条目: {len(notes)}")
    print(f"  匹配上digest: {counts['matched']}")
    print(f"  有source但没匹配上: {counts['unmatched']}")
    print(f"  没有链接(不参与eval): {counts['no_source']}")


def report_unmatched(notes):
    rows = [n for n in notes if n["status"] == "unmatched"]
    if not rows:
        print("没有匹配失败的条目。")
        return
    print(f"匹配失败 {len(rows)} 条:")
    for n in rows:
        print(f"  {n['note']}\n    url: {n['url']}")


def report_eval(notes, conn):
    """在"已排过序"的条目上算:系统判的档位,跟你实际记了笔记的重合度。

    只统计ranked_at不为空的条目——没排过序的(启用日期之前的历史存档)不是这套标准判的,
    算进来会污染结果。
    """
    noted = {g for n in notes for g in n["guids"]}
    rows = conn.execute(
        "SELECT guid, ai_tier, anchor_tier, title, person FROM items WHERE ranked_at IS NOT NULL"
    ).fetchall()
    if not rows:
        print("\n库里还没有排过序的条目,eval跳过。")
        return

    best = {"high": 0, "medium": 1, "low": 2}
    buckets = {"high": [], "medium": [], "low": []}
    for guid, ai, anchor, title, person in rows:
        tiers = [t for t in (ai, anchor) if t in best]
        tier = min(tiers, key=lambda t: best[t]) if tiers else "low"
        buckets[tier].append((guid, person, title))

    print("\n=== eval:排序档位 vs 你记了笔记的 ===")
    print(f"(样本:{len(rows)}条已排序内容, 其中{len(noted & {r[0] for r in rows})}条有笔记)")
    for tier in ("high", "medium", "low"):
        items = buckets[tier]
        hit = [i for i in items if i[0] in noted]
        rate = f"{len(hit)/len(items)*100:.0f}%" if items else "—"
        print(f"  判 {tier:6} {len(items):4} 条 → 你记了 {len(hit):3} 条 ({rate})")

    missed = [i for i in buckets["low"] if i[0] in noted]
    if missed:
        print(f"\n漏判(判low但你记了笔记) {len(missed)} 条 —— 这批最值得看:")
        for _, person, title in missed[:15]:
            print(f"  {person} | {title[:60]}")
    print("\n注意:'判high但你没记'不等于判错。你自己说过有用是随时间变的——")
    print("这批是以后回访的对象(三个月后重推一次,看你那时的判断变没变),不是虚警。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    ap.add_argument("--eval", action="store_true", help="额外算一次排序档位 vs 实际记笔记的重合度")
    ap.add_argument("--unmatched", action="store_true", help="只列出没匹配上的笔记")
    args = ap.parse_args()

    inbox = args.inbox.expanduser()
    if not inbox.is_dir():
        sys.exit(f"收件箱目录不存在: {inbox}")

    db = Path(__file__).resolve().parent.parent / DB_PATH
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)  # 只读打开,杜绝误写
    try:
        notes = scan(inbox, conn)
        write_index(inbox, notes)
        if args.unmatched:
            report_unmatched(notes)
        else:
            report(notes)
            if args.eval:
                report_eval(notes, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
