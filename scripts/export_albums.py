"""
导出「常读的人」(docs/albums.html)的数据：docs/data/albums.json。

2026-11-14加。用户最在意的几个人，每人一张卡片：封面图 + 一段介绍 + 最新一篇。
页面版式参考tetragrammaton.com/playlists(单栏、大方封面、衬线标题、专辑之间一条细线)。

- 曲目来自digest.db里这个人的条目(不看tier，这些人用户本来就要全看)，被排序阶段标了
  excluded_reason的不算(比如转发别人的产品宣传语)。
- Thorsten Ball不在digest.db里，他的曲目是docs/data/letters/index.json里的每周来信，
  点专辑直接进卷轴页(letter.html)。
- 名单、介绍、封面都写在下面ALBUMS里，改人就改这里。封面image是公开网络上能代表这个人的图
  (本人网站头图/头像/插画)，直接引用原网址，不复制进仓库，原色显示(不做黑白处理——
  2026-11-14用户提过黑白处理后的人像照不吉利；本身是黑白的图由用户挑过，可以)。
  图加载失败时退回cover字段对应的线稿。
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
        "person": "Craig Mod", "pub": "Ridgeline & Roden", "cover": "ridge", "verb": "Read",
        "image": "https://craigmod.com/images/craigmod-homepage-image.jpg",
        "home": "https://craigmod.com",
        "bio": "住在日本的作家、摄影师。常年徒步穿越日本的乡间小路，把一路遇到的人和店写进 "
               "Ridgeline 和 Roden 两份 newsletter，出过《Kissa by Kissa》《Things Become Other Things》。"
               "慢、长、专注，是他对抗速度的方式。",
    },
    {
        "person": "Thorsten Ball", "pub": "Joy & Curiosity", "cover": "rays", "verb": "Open Letter",
        "image": "https://thorstenball.com/images/avatar_2026_final_quadratic.jpg",
        "home": "https://registerspill.thorstenball.com", "href": "letter.html", "source": "letters",
        "bio": "软件工程师，在 Amp 做编程智能体，写过《Writing An Interpreter In Go》。"
               "每周日寄出一封 Joy & Curiosity，把一周里让他快乐、让他好奇的东西装进去。",
    },
    {
        "person": "Dan Koe", "pub": "future/proof", "cover": "spiral", "verb": "Read",
        "image": "https://substackcdn.com/image/fetch/$s_!OZ7Z!,w_800,h_800,c_fill,f_auto,q_auto:good,fl_progressive:steep,g_auto/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2Fc5ee5bed-1760-427e-9744-f5ad89baf5a9_886x886.png",
        "home": "https://thedankoe.com",
        "bio": "写「一人企业」和自我教育的作者。他的看法是：AI 能生成一切听起来不错的句子，"
               "最后剩下的护城河，是只有你能看见的那个视角。",
    },
    {
        "person": "Teo Crawford", "pub": "YouTube", "cover": "aperture", "verb": "Watch",
        "image": "https://yt3.googleusercontent.com/6f-mwpN4uNcUeWCdlzElYj0Y_i33oGydxZyZ4yAN9PhiHsb9CfKp0SpslMVk0anIfwL2vHRA=s900-c-k-c0x00ffffff-no-rj",
        "home": "https://www.youtube.com/@TeoCrawford",
        "bio": "拍胶片和街头摄影的 YouTuber，镜头里多是日本的日常与慢下来的生活。"
               "从 2013 年开始做视频，十年如一日地拍。",
    },
    {
        "person": "Andy Matuschak", "pub": "Notes & Posts", "cover": "wordmark", "verb": "Read",
        # 不用照片：照他网站顶部的名字字标，浅粉底紫字，在页面里画成正方形
        "bg": "#FDF3F1", "ink": "#360EF5",
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
        entry["latest_title"] = tracks[0]["title"] if tracks else None
        # 页面上的按钮直接打开最新一篇原文；Thorsten的信在卷轴页里读(那里记录点开了哪些链接)
        entry["latest_link"] = a.get("href") or (tracks[0]["link"] if tracks else a["home"])
        albums.append(entry)
        print(f"[OK] {a['person']} — {len(tracks)}首, 最新 {entry['latest']}")
    conn.close()
    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "albums": albums,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
