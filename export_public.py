"""
生成公开站的产物到`public/`。产物推到 github.com/YYeees/AIDailyNews，由 Cloudflare Worker
(静态资源)接那个仓发布到 aidailynews.yyeees.workers.dev;同仓的 GitHub Pages
(yyeees.github.io/AIDailyNews/)没关,留作备份线路。

跟私有站的关系:**公开站是私有站的严格子集**。这个脚本不碰digest.db,只读docs/下已经导出好
的产物做过滤——这样tier规则、HIGH_ONLY_PERSONS、always_archive那套判断逻辑只有一份
(在export_recent.py/export_json.py里),不会因为两个脚本各自实现一遍而慢慢判出两种结果。

公开的边界(2026-09-02跟用户定的):
- 只放命中AI track的条目;`tracks`里只留ai那条。**锚点track整条不外传**——anchor_reason
  会直接引用RANKING_CRITERIA.md里的正向母题原话,那是用户的思想坐标,不是内容信息。
  同一条内容两个track都命中时,条目照常公开,只是把anchor那条从tracks里摘掉。
- X动态不放:X是不限tier全展示的(见config.ALWAYS_DISPLAY_TYPES),里面混着跟AI无关的
  个人动态,展示规则跟"只公开AI"直接冲突。
- GitHub Trending照常放:那份导出本来就只有ai_related=1的仓库。
- 运行日志(费用/token)照常放:run_log.json里只有花费和用量,没有任何内容或prompt。

字段走**白名单**不走黑名单(见PUBLIC_ITEM_FIELDS):以后往items表/导出里加新字段,默认是
不出去的,不会因为忘了在这里补一条排除规则就漏出去。

前端HTML不复制第二份,直接用docs/下那两个文件,把`<!--SITE-CONFIG-->`那行换成一个开关
脚本(见SITE_CONFIG_MARKER)。index.html里所有`IS_PUBLIC`的分支就是靠这个开关生效的。
"""

import json
import shutil
from pathlib import Path

DOCS = Path("docs")
DOCS_DATA = DOCS / "data"
OUT = Path("public")
OUT_DATA = OUT / "data"

SITE_CONFIG_MARKER = "<!--SITE-CONFIG-->"
SITE_CONFIG_SCRIPT = "<script>window.PUBLIC_SITE = true;</script>"

# 公开条目只搬这些字段。私有导出里的`first_seen`(第一次抓到的时间)不在列——前端不用它,
# 那就没有理由发出去。
PUBLIC_ITEM_FIELDS = ("person", "title", "link", "date", "source_type", "summary", "is_new")

# 原样搬运的数据文件:内容本身已经满足公开边界,不需要过滤。
COPY_AS_IS = ("trending.json", "run_log.json")

HTML_PAGES = ("index.html", "digest.html")

# 光靠JS在运行时删掉锚点筛选器是不够的:HTML源码里还留着"锚点"两个字,查看源代码就能看见
# 有这么个隐藏分类。这里在导出时就从文本里摘干净。每条都是精确匹配、命中即换,配合下面
# 那句"产物里不许再出现锚点"的断言——哪天前端改了措辞导致这里匹配不上,跑批会当场炸,
# 而不是悄悄把字眼发出去。
HTML_STRIPS = (
    ('        <option value="anchor">锚点</option>\n', ""),
    ("const TRACK_LABEL = { ai: 'AI', anchor: '锚点' };", "const TRACK_LABEL = { ai: 'AI' };"),
    # 开发注释也算:它们泄露不了判断内容,但会告诉读源码的人"这里还有第二条track"
    ("AI/锚点/tier标签", "AI/tier标签"),
    ("// ---- 最近更新板块：AI实操+关注锚点合并。右上角两类独立标签：",
     "// ---- 最近更新板块。右上角两类独立标签："),
)

README = """# AI Daily News

每天自动抓取一批AI领域的信息源(博客/播客/YouTube/GitHub Trending),由Claude Code逐条判断
"这条对成为AI高手有多大帮助",筛出值得看的,附上一句话理由和摘要。

网站: https://aidailynews.yyeees.workers.dev
备份地址: https://yyeees.github.io/AIDailyNews/

- **最近更新** — 最近7天筛出来的内容,标了推荐度(High/Medium)和判断理由
- **GitHub Trending** — 每周抓一次趋势榜,按"这一期涨了多少"排序,标了难度和推荐理由
- **运行日志** — 每次定时任务实际花了多少token和钱

这个仓库只存网站产物,由上游的抓取/排序管线自动推送,不接受直接改动。
"""


def public_item(item):
    """按白名单挑字段 + 只留AI track;这条内容没命中AI track时返回None(整条不公开)。"""
    ai_tracks = [
        {"track": t["track"], "tier": t["tier"], "reason": t.get("reason", "")}
        for t in item.get("tracks", []) if t.get("track") == "ai"
    ]
    if not ai_tracks:
        return None
    out = {k: item[k] for k in PUBLIC_ITEM_FIELDS if k in item}
    out["tracks"] = ai_tracks
    return out


def public_items(items):
    return [p for p in (public_item(i) for i in items) if p is not None]


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def audit(paths):
    """产物自检:锚点的任何痕迹都不该出现在公开数据里。

    这不是"以防万一"——上面的过滤只要哪天被改错(比如白名单里手滑加回tracks原样透传),
    静默漏出去的就是用户的母题清单。宁可让跑批在这里炸掉,也不要悄悄发出去。
    """
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for needle in ('"anchor"', "anchor_tier", "anchor_reason", "锚点"):
            if needle in text:
                raise SystemExit(f"[中止] {path} 里出现了`{needle}`,锚点内容可能正在外泄,不导出。")


def export():
    if OUT.exists():
        shutil.rmtree(OUT)   # 全量重建:上一次导出的残留(比如某个月份被清空了)不该留在公开站
    OUT_DATA.mkdir(parents=True)

    written = []

    recent = json.loads((DOCS_DATA / "recent.json").read_text(encoding="utf-8"))
    items = public_items(recent["items"])
    write_json(OUT_DATA / "recent.json", {"items": items})
    written.append(OUT_DATA / "recent.json")
    print(f"[OK] recent.json — {len(items)}条 (私有站{len(recent['items'])}条)")

    months = []
    for src in sorted(DOCS_DATA.glob("digest_*.json")):
        data = json.loads(src.read_text(encoding="utf-8"))
        month_items = public_items(data.get("items", []))
        github = data.get("github_track", [])
        if not month_items and not github:
            print(f"[跳过] {src.name} — 过滤后没有可公开的内容")
            continue
        dst = OUT_DATA / src.name
        write_json(dst, {"items": month_items, "github_track": github})
        written.append(dst)
        months.append(src.stem.replace("digest_", ""))
        print(f"[OK] {src.name} — {len(month_items)}条 (私有站{len(data.get('items', []))}条) github:{len(github)}个")

    months.sort(reverse=True)
    write_json(OUT_DATA / "months.json", {"months": months})
    written.append(OUT_DATA / "months.json")
    print(f"[OK] months.json — {months}")

    for name in COPY_AS_IS:
        shutil.copy2(DOCS_DATA / name, OUT_DATA / name)
        written.append(OUT_DATA / name)
        print(f"[OK] {name} — 原样搬运")

    audit(written)
    print("[OK] 自检通过:公开数据里没有锚点痕迹")

    for name in HTML_PAGES:
        html = (DOCS / name).read_text(encoding="utf-8")
        # 必须恰好一处:marker字面量如果在别处(比如某句注释里)也出现过,replace会一并换掉,
        # 把一个</script>塞进脚本块中间——HTML解析器在那里提前收尾,后面的JS全部失效。
        # 2026-09-02真踩过,公开站当时只渲染出2张卡。
        if html.count(SITE_CONFIG_MARKER) != 1:
            raise SystemExit(
                f"[中止] docs/{name} 里{SITE_CONFIG_MARKER}出现了{html.count(SITE_CONFIG_MARKER)}次,应该恰好1次。"
            )
        html = html.replace(SITE_CONFIG_MARKER, SITE_CONFIG_SCRIPT)
        for old_text, new_text in HTML_STRIPS:
            html = html.replace(old_text, new_text)
        if "锚点" in html:
            raise SystemExit(f"[中止] docs/{name} 剥离后仍残留`锚点`字样,HTML_STRIPS该更新了,不导出。")
        (OUT / name).write_text(html, encoding="utf-8")
        print(f"[OK] {name} — 已注入公开站开关、剥掉锚点字样")

    # Jekyll会吃掉下划线开头的文件;这个站是纯静态产物,不需要它插手
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "README.md").write_text(README, encoding="utf-8")
    print(f"[OK] public/ 生成完毕")


if __name__ == "__main__":
    export()
