"""
拉取sources.py里X_SOURCES的最新推文(TwitterAPI.io)，存入digest.db的items表，
按guid去重——跟fetch.py是同一张表、同一套去重逻辑，只是source_type='x'。

只取每人最新一页(最多20条，不含回复)，不做分页增量——这两个账号发帖频率不高，
weekly跑一次单页覆盖足够；真出现单周发了20+条不含回复的情况，后面再加分页。

不做排序、不做摘要生成——这两步交给排序阶段(读RANKING_CRITERIA.md+config.py里的
ALWAYS_SUMMARIZE_TYPES)处理，这里只负责抓取入库，summary字段存推文原文(英文)。

需要环境变量TWITTERAPI_IO_KEY(本地开发从.env读，见requirements.txt里的python-dotenv；
GitHub Actions里从repo secrets读)。
"""

import sqlite3
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
import os

from config import DB_PATH
from sources import X_SOURCES

load_dotenv()

API_URL = "https://api.twitterapi.io/twitter/user/last_tweets"
TWEET_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"  # "Wed Aug 12 17:48:36 +0000 2026"


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
            first_seen_at TEXT
        )
    """)
    conn.commit()


def parse_tweet_date(created_at):
    dt = datetime.strptime(created_at, TWEET_DATE_FORMAT)
    return dt.astimezone(timezone.utc).isoformat()


def make_title(text):
    text = text.strip().replace("\n", " ")
    return text if len(text) <= 100 else text[:100].rstrip() + "…"


def normalize_tweet(source, tweet):
    source_name = f"{source['person']} (X)"
    return {
        "guid": f"{source_name}::{tweet['id']}",
        "person": source["person"],
        "source_name": source_name,
        "source_type": "x",
        "title": make_title(tweet["text"]),
        "link": tweet["url"],
        "published": parse_tweet_date(tweet["createdAt"]),
        "summary": tweet["text"],
        "has_full_text": 1,
        "first_seen_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_all():
    api_key = os.environ.get("TWITTERAPI_IO_KEY")
    if not api_key:
        raise SystemExit("缺少TWITTERAPI_IO_KEY环境变量(本地在.env里配，CI在repo secrets里配)")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    total_new = 0
    for source in X_SOURCES:
        payload = None
        for attempt in range(3):
            resp = requests.get(
                API_URL,
                headers={"X-API-Key": api_key},
                params={"userName": source["x_username"], "cursor": "", "includeReplies": "false"},
                timeout=30,
            )
            try:
                payload = resp.json()
            except ValueError:
                payload = None
            if payload and payload.get("status") == "success":
                break
            time.sleep(2)  # 这个接口偶尔对内容较长的账号返回不完整/失败，重试几次通常就好

        if not payload or payload.get("status") != "success":
            detail = payload.get("msg") if payload else resp.text[:200]
            print(f"[FAIL] {source['person']} — HTTP {resp.status_code} — {detail}")
            continue

        tweets = payload["data"]["tweets"]
        new_count = 0
        for tweet in tweets:
            record = normalize_tweet(source, tweet)
            cur = conn.execute("SELECT 1 FROM items WHERE guid = ?", (record["guid"],))
            if cur.fetchone() is not None:
                continue
            conn.execute(
                """INSERT INTO items
                   (guid, person, source_name, source_type, title, link, published, summary, has_full_text, first_seen_at)
                   VALUES (:guid, :person, :source_name, :source_type, :title, :link, :published, :summary, :has_full_text, :first_seen_at)""",
                record,
            )
            new_count += 1
        conn.commit()
        total_new += new_count
        print(f"[OK] {source['person']}: {len(tweets)}条 in page, {new_count}条新增")

    conn.close()
    print(f"\n共新增 {total_new} 条")


if __name__ == "__main__":
    fetch_all()
