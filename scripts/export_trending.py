"""
把repos表里ai_related=1且worth_tier是high/medium的仓库导出成docs/data/trending.json供前端fetch。
(worth_tier=low的仓库留在库里，不进展示层——跟digest的low处理方式一致)
每个仓库取最新一天的daily_snapshots数据(star数)；同一天可能因为出现在多个语言榜而有多条快照，
取排名最靠前的那条。

2026-08-15定案：不用展示太多，排完序只取综合最值得推荐的前config.TRENDING_DAILY_LIMIT个，
不是把评估过的仓库全部展示出来。

2026-08-21改排序：原来是tier→`stars_total`(历史累计star)降序，结果这块板子变成了"AI仓库
历史人气总榜"，几乎不会变——81个够格的仓库里只露出6个，而且是按累计人气选的，新仓库除非
自带十几万star否则永远挤不进来(实测：8-16那周真实榜首diagram-design本周涨了14735星却不展示，
而常驻第6的ML-For-Beginners本周只涨了40星)。现在改成tier→`stars_today`降序，即**档内按这一期
涨了多少排**，tier优先那层不动，你评估出来的质量分档仍然说了算。

关于`stars_today`这个列名：它存的是**榜单页面上显示的"本期新增star"**，抓周榜时就是"本周新增"，
不是"今天新增"——列名是2026-08-15还在跑日榜时定的，改成周榜后没跟着改。导出成JSON时统一叫
`stars_period`，避免前端也被这个名字误导。

只展示**出现在最近一次抓取里**的仓库：按涨幅排就必须限定"这一期"，否则某个仓库某周暴涨
(比如+20000)之后掉出榜单，它会带着这个旧数字永远占着第一位——那就是换一种方式重新冻住。
最近一次抓取里够格的仓库有36个high+21个medium，填满6个位置绰绰有余。

不按GitHub榜单原始名次(`rank`)排，是因为rank是**分榜单页**的：同时抓全语言/Python/Jupyter
Notebook/TypeScript四个页面，所以同一天有4个"第1名"，纯按rank排会把"全语言榜第1(+14735)"和
"Jupyter小榜第1(+84)"当成同等热度，还会把tier评估结果整个丢掉。
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, TRENDING_DAILY_LIMIT  # noqa: E402

OUT_PATH = Path("docs/data/trending.json")


def export():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 只取出现在最近一次抓取里的仓库——按"这一期涨了多少"排序，就不能让掉出榜单的仓库
    # 带着上一期的旧涨幅继续参赛(理由见文件头)
    latest_crawl = conn.execute("SELECT MAX(snapshot_date) FROM daily_snapshots").fetchone()[0]
    repos = conn.execute("""
        SELECT * FROM repos
        WHERE ai_related = 1 AND worth_tier IN ('high', 'medium')
          AND full_name IN (SELECT full_name FROM daily_snapshots WHERE snapshot_date = ?)
    """, (latest_crawl,)).fetchall()

    items = []
    for repo in repos:
        snapshot = conn.execute("""
            SELECT * FROM daily_snapshots
            WHERE full_name = ?
            ORDER BY snapshot_date DESC, rank ASC
            LIMIT 1
        """, (repo["full_name"],)).fetchone()

        items.append({
            "full_name": repo["full_name"],
            "url": repo["url"],
            "description": repo["description"],
            "language": repo["primary_language"],
            "difficulty": repo["difficulty"],
            "worth_tier": repo["worth_tier"],
            "recommend_reason": repo["recommend_reason"],
            "first_seen_date": repo["first_seen_date"],
            "stars_total": snapshot["stars_total"] if snapshot else None,
            # 榜单上这一期新增的star(周榜=本周新增)，既是排序键也给前端显示，见文件头注释
            "stars_period": snapshot["stars_today"] if snapshot else None,
            "last_snapshot_date": snapshot["snapshot_date"] if snapshot else None,
        })

    tier_order = {"high": 0, "medium": 1}
    # 先tier后"这一期涨了多少"——不是历史累计star，理由见文件头2026-08-21那段
    items.sort(key=lambda i: (tier_order.get(i["worth_tier"], 9), -(i["stars_period"] or 0)))
    items = items[:TRENDING_DAILY_LIMIT]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {OUT_PATH} — {len(items)}个仓库(上限{TRENDING_DAILY_LIMIT}, 抓取日{latest_crawl}) "
          f"(high:{sum(1 for i in items if i['worth_tier']=='high')} "
          f"medium:{sum(1 for i in items if i['worth_tier']=='medium')})")

    conn.close()


if __name__ == "__main__":
    export()
