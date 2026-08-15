"""
拉取sources.py里的feed,存入本地SQLite做去重。
不做排序、不做全文抓取、不做X —— 只负责"抓到新条目就记下来"这一步。
"""

import calendar
import sqlite3
import sys
from datetime import datetime, timezone

import feedparser

from config import DB_PATH
from sources import SOURCES


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            guid TEXT PRIMARY KEY,
            person TEXT,
            source_name TEXT,
            source_type TEXT,
            title TEXT,
            link TEXT,
            published TEXT,
            summary TEXT,
            has_full_text INTEGER,
            first_seen_at TEXT,
            ai_tier TEXT,
            ai_reason TEXT,
            anchor_tier TEXT,
            anchor_reason TEXT,
            digest_summary TEXT,
            ranked_at TEXT
        )
    """)
    conn.commit()


def parsed_time_to_iso(struct_time):
    if struct_time is None:
        return None
    # feedparser的published_parsed/updated_parsed已经是UTC struct_time，要用timegm(按UTC解释)
    # 而不是mktime(按本地时区解释)——本机是CST(UTC+8)，用mktime会让存入的时间系统性偏早8小时。
    return datetime.fromtimestamp(calendar.timegm(struct_time), tz=timezone.utc).isoformat()


def normalize_entry(source, entry):
    guid = entry.get("id") or entry.get("link")
    published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    has_full_text = 1 if entry.get("content") else 0
    summary = entry.get("summary", "")
    return {
        "guid": f"{source['name']}::{guid}",
        "person": source["person"],
        "source_name": source["name"],
        "source_type": source["type"],
        "title": entry.get("title", "(无标题)"),
        "link": entry.get("link", ""),
        "published": parsed_time_to_iso(published_struct),
        "summary": summary,
        "has_full_text": has_full_text,
        "first_seen_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_all():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    total_new = 0
    failed = []
    for source in SOURCES:
        parsed = feedparser.parse(source["url"])
        if parsed.bozo and not parsed.entries:
            print(f"[FAIL] {source['name']} ({source['url']}) — {parsed.bozo_exception}")
            failed.append(source["name"])
            continue

        new_count = 0
        for entry in parsed.entries:
            record = normalize_entry(source, entry)
            cur = conn.execute(
                "SELECT 1 FROM items WHERE guid = ?", (record["guid"],)
            )
            if cur.fetchone() is not None:
                continue  # 已经见过,跳过
            conn.execute(
                """INSERT INTO items
                   (guid, person, source_name, source_type, title, link, published, summary, has_full_text, first_seen_at)
                   VALUES (:guid, :person, :source_name, :source_type, :title, :link, :published, :summary, :has_full_text, :first_seen_at)""",
                record,
            )
            new_count += 1
        conn.commit()
        total_new += new_count
        print(f"[OK] {source['name']}: {len(parsed.entries)}条 in feed, {new_count}条新增")

    conn.close()
    print(f"\n共新增 {total_new} 条")
    if failed:
        print(f"共{len(failed)}个源抓取失败: {failed}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    fetch_all()
