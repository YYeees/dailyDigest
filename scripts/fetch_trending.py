"""
抓取GitHub Trending周榜(全语言榜 + Python/Jupyter Notebook/TypeScript这几个AI项目高频出现的语言榜)，
写入digest.db的repos表(仓库基础信息，靠full_name去重，一个仓库只存一份)和daily_snapshots表
(每次抓取时每个仓库的star数/排名，允许同一仓库多次多条——表名叫daily_snapshots是历史遗留，
2026-08-15起实际按周跑，不是按天，字段含义不变只是频率变了，没改表名/字段名避免迁移)。

2026-08-15从"每天抓日榜"改成"每周抓周榜"(since=weekly)：日榜量太大(单天能有50+新仓库)，
评估成本跟"只展示top6/10"这个精简目标不匹配，周榜天然把一周的热度聚合成一份，评估量更可控。
月度视图不用额外处理——export_json.py本来就按first_seen_date聚合当月发现的high档仓库，
一个月大概攒4次周榜的结果，自然形成月度精华。

不做AI评估——新仓库写入repos表后，ai_related等字段留空(evaluated_at IS NULL)，
由trending_repos.py + GITHUB_TRENDING_CRITERIA.md那一步(Claude Code现场读README判断)来填。

GitHub没有官方trending API，这里靠解析trending页面的HTML。页面结构一旦大改，这个脚本可能需要跟着改。
"""

import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, SNAPSHOT_RETENTION_DAYS  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; dailyDigest-trending-bot/1.0)"}

TRENDING_PAGES = [
    ("all", "https://github.com/trending?since=weekly"),
    ("python", "https://github.com/trending/python?since=weekly"),
    ("jupyter-notebook", "https://github.com/trending/jupyter-notebook?since=weekly"),
    ("typescript", "https://github.com/trending/typescript?since=weekly"),
]

# 日榜文案是"X stars today"，周榜是"X stars this week"，月榜是"X stars this month"——
# 三种都匹配，不管since=daily/weekly/monthly哪个都能正确解析。
STARS_TODAY_RE = re.compile(r"([\d,]+)\s+stars?\s+(?:today|this week|this month)")


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            full_name TEXT PRIMARY KEY,
            url TEXT,
            description TEXT,
            primary_language TEXT,
            first_seen_date TEXT,
            last_seen_date TEXT,
            ai_related INTEGER,
            difficulty TEXT,
            worth_tier TEXT,
            recommend_reason TEXT,
            evaluated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            trending_page TEXT NOT NULL,
            rank INTEGER,
            stars_total INTEGER,
            stars_today INTEGER,
            UNIQUE(full_name, snapshot_date, trending_page)
        )
    """)
    conn.commit()


def cleanup_old_snapshots(conn):
    cutoff = (date.today() - timedelta(days=SNAPSHOT_RETENTION_DAYS)).isoformat()
    cur = conn.execute("DELETE FROM daily_snapshots WHERE snapshot_date < ?", (cutoff,))
    conn.commit()
    return cur.rowcount


def parse_int(text):
    text = (text or "").strip().replace(",", "")
    return int(text) if text.isdigit() else None


def parse_trending_page(html):
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("article.Box-row")
    results = []
    for rank, row in enumerate(rows, start=1):
        link = row.select_one("h2 a")
        if not link or not link.get("href"):
            continue
        full_name = link["href"].strip("/")

        desc_el = row.select_one("p.col-9")
        description = desc_el.get_text(strip=True) if desc_el else ""

        lang_el = row.select_one("span[itemprop=programmingLanguage]")
        language = lang_el.get_text(strip=True) if lang_el else None

        stars_a = row.select_one("a[href$=stargazers]")
        stars_total = parse_int(stars_a.get_text()) if stars_a else None

        f6 = row.select_one("div.f6")
        stars_today = None
        if f6:
            m = STARS_TODAY_RE.search(f6.get_text(" ", strip=True))
            if m:
                stars_today = parse_int(m.group(1))

        results.append({
            "full_name": full_name,
            "url": f"https://github.com/{full_name}",
            "description": description,
            "language": language,
            "rank": rank,
            "stars_total": stars_total,
            "stars_today": stars_today,
        })
    return results


def fetch_all():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    new_repos = 0
    snapshot_count = 0
    failed = []

    for page_key, url in TRENDING_PAGES:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"[FAIL] {page_key} ({url}) — HTTP {resp.status_code}")
            failed.append(f"{page_key} (HTTP {resp.status_code})")
            continue
        repos = parse_trending_page(resp.text)
        if not repos:
            print(f"[FAIL] {page_key} ({url}) — 解析出0个仓库，页面结构可能变了")
            failed.append(f"{page_key} (0 repos parsed)")
            continue

        for r in repos:
            existing = conn.execute(
                "SELECT 1 FROM repos WHERE full_name = ?", (r["full_name"],)
            ).fetchone()
            if existing is None:
                conn.execute(
                    """INSERT INTO repos
                       (full_name, url, description, primary_language, first_seen_date, last_seen_date)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (r["full_name"], r["url"], r["description"], r["language"], today, today),
                )
                new_repos += 1
            else:
                conn.execute(
                    "UPDATE repos SET last_seen_date = ? WHERE full_name = ?",
                    (today, r["full_name"]),
                )

            conn.execute(
                """INSERT OR REPLACE INTO daily_snapshots
                   (full_name, snapshot_date, trending_page, rank, stars_total, stars_today)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (r["full_name"], today, page_key, r["rank"], r["stars_total"], r["stars_today"]),
            )
            snapshot_count += 1

        conn.commit()
        print(f"[OK] {page_key}: {len(repos)}个仓库")

    removed = cleanup_old_snapshots(conn)
    conn.close()
    print(f"\n共{snapshot_count}条快照记录，{new_repos}个新仓库(待AI评估)")
    if removed:
        print(f"清理了{removed}条超过{SNAPSHOT_RETENTION_DAYS}天的历史快照")
    if failed:
        print(f"共{len(failed)}个页面抓取失败: {failed}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    fetch_all()
