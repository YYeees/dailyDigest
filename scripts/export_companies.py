"""
导出「大公司」页(docs/companies.html)的数据：docs/data/companies.json。

2026-11-14加。用户的原话是：平时很少点开这些公司的消息，但常在别处看到才发现"这个我错过了"；
而每次打开公司官网，文章配图都让人很想点开。所以这一页是"补课"用的：
- 只放近WINDOW_DAYS天里判成high的(ai_tier或eval_tier)，不刷屏
- 以文章配图为主角(og:image)，前端做成杂志式大图

配图抓取：
- 每篇文章抓一次og:image，抓到的按link缓存在上一次的companies.json里，之后不再请求；
  抓不到的(超时、被限流)下次跑批再试。
- openai.com对脚本访问一律403(它的反爬)，不去绕，直接跳过；前端给OpenAI画黑底标题卡。
"""

import gzip
import json
import re
import time
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH  # noqa: E402

OUT = ROOT / "docs" / "data" / "companies.json"
WINDOW_DAYS = 60
MAX_ITEMS = 48

COMPANIES = [
    # person字段跟digest.db里的一致。2026-11-14用户说不跟DeepMind了，这页只放这两家
    {"person": "Anthropic", "name": "Anthropic", "key": "anthropic"},
    {"person": "OpenAI", "name": "OpenAI", "key": "openai"},
]
NO_FETCH_HOSTS = ("openai.com",)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
OG_RE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]*>', re.I)
CONTENT_RE = re.compile(r'content=["\']([^"\']+)["\']', re.I)


def fetch_og_image(link):
    if any(h in link for h in NO_FETCH_HOSTS):
        return None
    try:
        resp = requests.get(link, timeout=12, headers={"User-Agent": UA})
        if resp.status_code != 200:
            return None
        body = resp.content
        # 有的站返回gzip压缩的正文却不带Content-Encoding头，requests不会自动解压
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        tag = OG_RE.search(body[:400_000].decode("utf-8", "replace"))
        if not tag:
            return None
        m = CONTENT_RE.search(tag.group(0))
        url = unescape(m.group(1)) if m else None
        return url if url and url.startswith("https://") else None
    except requests.RequestException:
        return None


def load_cache():
    if not OUT.exists():
        return {}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {x["link"]: x["image"] for x in data.get("items", []) if x.get("link") and x.get("image")}


def main():
    cache = load_cache()
    since = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).isoformat()
    by_person = {c["person"]: c for c in COMPANIES}
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        f"""SELECT person, title, link, published, digest_summary
            FROM items
            WHERE person IN ({",".join("?" * len(COMPANIES))})
              AND published >= ?
              AND (ai_tier = 'high' OR eval_tier = 'high')
              AND (excluded_reason IS NULL OR excluded_reason = '')
            ORDER BY published DESC LIMIT ?""",
        (*by_person, since, MAX_ITEMS),
    ).fetchall()
    conn.close()

    items, seen_links, fetched = [], set(), 0
    for person, title, link, published, summary in rows:
        if link in seen_links:     # 同一篇偶尔会被两个feed各收一次
            continue
        seen_links.add(link)
        if link in cache:
            image = cache[link]
        else:
            image = fetch_og_image(link)
            fetched += 1
            time.sleep(0.5)    # 别一口气打太密
        c = by_person[person]
        items.append({
            "company": c["name"], "key": c["key"], "title": title, "link": link,
            "date": (published or "")[:10], "summary": summary or "", "image": image,
        })

    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "companies": [{"name": c["name"], "key": c["key"]} for c in COMPANIES],
        "items": items,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    with_img = sum(1 for x in items if x["image"])
    print(f"[OK] companies.json — {len(items)}条(近{WINDOW_DAYS}天high)，{with_img}条有配图，新抓配图{fetched}次")


if __name__ == "__main__":
    main()
