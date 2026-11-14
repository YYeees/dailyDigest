"""
导出「专辑墙」(docs/albums.html)的数据：docs/data/albums.json。

2026-11-14加。用户最在意的几个人，每人一张"专辑"：封面 + 一段介绍 + 最近的作品当曲目。
页面版式参考tetragrammaton.com/playlists(单栏、大方封面、衬线标题、专辑之间一条细线)。

- 曲目来自digest.db里这个人的条目(不看tier，这些人用户本来就要全看)，被排序阶段标了
  excluded_reason的不算(比如转发别人的产品宣传语)。
- Thorsten Ball不在digest.db里，他的曲目是docs/data/letters/index.json里的每周来信，
  点专辑直接进卷轴页(letter.html)。
- 名单、介绍、封面主题都写在下面ALBUMS里，改人就改这里。封面是页面里的内联SVG线稿，
  按cover字段挑，不用别人的照片(版权，也为了整面墙风格统一)。
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH  # noqa: E402

OUT = ROOT / "docs" / "data" / "albums.json"
LETTERS_INDEX = ROOT / "docs" / "data" / "letters" / "index.json"
TRACKS_PER_ALBUM = 10

ALBUMS = [
    {
        "person": "Craig Mod", "album": "Walking", "cover": "ridge",
        "home": "https://craigmod.com",
        "bio": "住在日本的作家、摄影师。常年徒步穿越日本的乡间小路，把一路遇到的人和店写进 "
               "Ridgeline 和 Roden 两份 newsletter，出过《Kissa by Kissa》《Things Become Other Things》。"
               "慢、长、专注，是他对抗速度的方式。",
    },
    {
        "person": "Thorsten Ball", "album": "Joy & Curiosity", "cover": "rays",
        "home": "https://registerspill.thorstenball.com", "href": "letter.html", "source": "letters",
        "bio": "软件工程师，在 Amp 做编程智能体，写过《Writing An Interpreter In Go》。"
               "每周日寄出一封 Joy & Curiosity，把一周里让他快乐、让他好奇的东西装进去。",
    },
    {
        "person": "Dan Koe", "album": "future/proof", "cover": "spiral",
        "home": "https://thedankoe.com",
        "bio": "写「一人企业」和自我教育的作者。他的看法是：AI 能生成一切听起来不错的句子，"
               "最后剩下的护城河，是只有你能看见的那个视角。",
    },
    {
        "person": "Teo Crawford", "album": "Frames", "cover": "aperture",
        "home": "https://www.youtube.com/@TeoCrawford",
        "bio": "拍胶片和街头摄影的 YouTuber，镜头里多是日本的日常与慢下来的生活。"
               "从 2013 年开始做视频，十年如一日地拍。",
    },
    {
        "person": "Andy Matuschak", "album": "Evergreen", "cover": "nodes",
        "home": "https://andymatuschak.org",
        "bio": "研究「思维工具」的独立研究者，和 Michael Nielsen 一起做过 Quantum Country。"
               "他公开的常青笔记本身就是一个不断生长、彼此链接的网站。",
    },
]


def tracks_from_db(conn, person):
    rows = conn.execute(
        """SELECT title, link, published, source_type, digest_summary
           FROM items WHERE person = ? AND (excluded_reason IS NULL OR excluded_reason = '')
           ORDER BY published DESC LIMIT ?""",
        (person, TRACKS_PER_ALBUM),
    ).fetchall()
    return [{"title": t, "link": l, "date": (p or "")[:10], "kind": k, "note": s or ""}
            for t, l, p, k, s in rows]


def tracks_from_letters():
    if not LETTERS_INDEX.exists():
        return []
    letters = json.loads(LETTERS_INDEX.read_text(encoding="utf-8")).get("letters", [])
    return [{"title": x["title"], "link": "letter.html", "date": x["date"], "kind": "letter",
             "note": f"{x.get('links_count', 0)} 处去向"} for x in letters[:TRACKS_PER_ALBUM]]


def main():
    conn = sqlite3.connect(DB_PATH)
    albums = []
    for a in ALBUMS:
        tracks = tracks_from_letters() if a.get("source") == "letters" else tracks_from_db(conn, a["person"])
        entry = {k: v for k, v in a.items() if k != "source"}
        entry["tracks"] = tracks
        entry["latest"] = tracks[0]["date"] if tracks else None
        albums.append(entry)
        print(f"[OK] {a['person']} — {len(tracks)}首, 最新 {entry['latest']}")
    conn.close()
    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "albums": albums,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
