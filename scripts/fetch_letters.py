"""
抓「每周来信」：把按周发的策展型newsletter整期存成JSON。

(2026-11-14 卷轴页 docs/letter.html 撤掉了；现在只给「常读的人」页里 Thorsten Ball 那张卡片提供最新一期。)

2026-11-14加，第一封是Thorsten Ball的Joy & Curiosity；2026-11-25加第二封Benedict Evans的周报
(走邮件转Atom，见LETTER_SOURCES里那条的注释)。跟digest主管线完全分开：
- 不进digest.db、不排tier、不写中文摘要——用户要读原文，他已经替你挑过一遍了，再筛等于否定策展本身。
- 不需要Claude，纯脚本，在digest workflow里Claude那步之前单独跑、单独commit。

存什么：
- docs/data/letters/index.json —— 所有已存期的目录(新的在前)，书架用
- docs/data/letters/<id>.json —— 每期一份：元信息 + 清洗后的正文HTML + 正文里的链接清单

正文清洗：Substack的RSS正文里夹着订阅框(form/input)、<picture>多尺寸源、层层div包装。
只留阅读需要的标签和属性，链接统一加data-i编号(卷轴页记录"点开过哪条"靠它)。

第一次跑(还没有index.json)只存最新一期——用户定的"只补最新一期"。之后每次只收比已存最大期号
更新的期，不回头补。
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "data" / "letters"

LETTER_SOURCES = [
    {
        "slug": "jc",
        "series": "Joy & Curiosity",
        "author": "Thorsten Ball",
        "feed": "https://registerspill.thorstenball.com/feed",
        # 同一个feed里还有他的普通文章，只要这个系列
        "title_re": r"^Joy & Curiosity #(\d+)",
    },
    # 2026-11-25加Benedict Evans的周报(免费版，每周二到)。周报只走邮件、没有公开RSS，用户在
    # kill-the-newsletter.com开了个收件邮箱订阅，那边把收到的邮件转成Atom feed。
    # - feed地址放GitHub secret(BENEDICT_LETTERS_FEED)不写进代码：地址里的ID就是收件邮箱，
    #   仓库是公开的，写进来等于谁都能往这个邮箱塞邮件冒充周报。没配这个变量就跳过，不算失败。
    # - 只认正文里带他Mailchimp账号ID的邮件(content_re，退订链接里的u=...)、且能找到期号的
    #   (number_re，正文头部"NO. 441")，订阅确认信这类靠这两道滤掉。没按发件人认：实测确认信的
    #   发件人是Mandrill的退信地址(bounce-md_...@mandrillapp.com)，不是他的名字。
    # - **不存正文**(store_html=False)：Mailchimp邮件是表格排版，清洗出来没法读；更要紧的是
    #   全量站是公开的，把一份本来不公开发布的周报整期放进公开仓不合适。只存元信息和他推荐的
    #   外链清单，link指向邮件里"在浏览器中查看"那个Mailchimp网页版(他自己发布的公开地址)。
    {
        "slug": "be",
        "series": "Benedict's Newsletter",
        "author": "Benedict Evans",
        "feed_env": "BENEDICT_LETTERS_FEED",
        "format": "atom",
        "content_re": r"b98e2de85f03865f1d38de74f",
        "number_re": r"\bNo\.?\s*(\d{3,4})\b",
        "store_html": False,
        "web_version_re": r"https?://(?:mailchi\.mp|[a-z0-9.-]*campaign-archive\.com)/[^\s\"'<>]+",
        # 退订/偏好设置/付费会员/他自己网站导航，不算"他推荐的链接"
        "drop_link_re": r"list-manage\.com|campaign-archive\.com|mailchi\.mp|memberful\.com|"
                        r"kill-the-newsletter\.com|(?:www\.)?ben-evans\.com/(?:newsletter|privacy|contact|sponsorship)?/?$",
    },
]

CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
ATOM = "{http://www.w3.org/2005/Atom}"

# ---- 正文清洗 ----
ALLOWED = {"p", "a", "ul", "ol", "li", "em", "strong", "b", "i", "blockquote", "h2", "h3", "h4",
           "figure", "figcaption", "img", "hr", "br", "code", "pre", "sup", "sub"}
VOID = {"img", "hr", "br"}
# 整块连同内容一起丢掉的标签
DROP_WITH_CONTENT = {"form", "button", "script", "style", "iframe", "audio", "video", "svg", "source"}
# 整块丢掉的div(按class片段匹配)：订阅框、音频嵌入
DROP_CLASS_PARTS = ("subscription-widget", "native-audio-embed", "button-wrapper")


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.links = []
        self.skip_depth = 0      # >0时在要整块丢掉的子树里
        self.stack = []          # 记录每个开标签是否被输出/是否开启了skip
        self.cur_link = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.skip_depth:
            if tag not in VOID:
                self.skip_depth += 1
                self.stack.append(("skip", tag))
            return
        cls = a.get("class") or ""
        if tag in DROP_WITH_CONTENT or (tag == "div" and any(p in cls for p in DROP_CLASS_PARTS)):
            if tag not in VOID and tag != "source":
                self.skip_depth = 1
                self.stack.append(("skip", tag))
            return
        if tag not in ALLOWED:
            if tag not in VOID:
                self.stack.append(("unwrap", tag))
            return
        if tag == "a":
            href = a.get("href") or ""
            # 图片外面包的那层<a>指向图片本身，不算"他推荐的链接"
            if not href.startswith(("http://", "https://")) or "substackcdn.com" in href \
                    or "substack-post-media" in href:
                self.stack.append(("unwrap", tag))
                return
            i = len(self.links)
            self.links.append({"i": i, "href": href, "text": ""})
            self.cur_link = i
            self.out.append(f'<a href="{escape(href)}" data-i="{i}" target="_blank" rel="noopener">')
        elif tag == "img":
            src = a.get("src") or ""
            if src.startswith("https://"):
                alt = escape(a.get("alt") or "")
                self.out.append(f'<img src="{escape(src)}" alt="{alt}" loading="lazy">')
            return
        elif tag in VOID:
            self.out.append(f"<{tag}>")
            return
        else:
            self.out.append(f"<{tag}>")
        self.stack.append(("keep", tag))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and not self.skip_depth:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        # 找到最近一个同名开标签(容忍RSS里偶尔不配对的HTML)
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx][1] == tag:
                break
        else:
            return
        while len(self.stack) > idx:
            kind, t = self.stack.pop()
            if kind == "skip":
                self.skip_depth -= 1
            elif kind == "keep":
                if t == "a":
                    self.cur_link = None
                self.out.append(f"</{t}>")

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.cur_link is not None:
            self.links[self.cur_link]["text"] += data
        self.out.append(escape(data, quote=False))


def clean_html(raw):
    c = _Cleaner()
    c.feed(raw or "")
    c.close()
    html = "".join(c.out)
    html = re.sub(r"<p>\s*</p>", "", html)          # 订阅框留下的空段落
    html = re.sub(r"<figure>\s*</figure>", "", html)
    for link in c.links:
        link["text"] = re.sub(r"\s+", " ", link["text"]).strip()
    return html.strip(), c.links


# ---- feed解析 ----
def _rss_items(root):
    for item in root.iter("item"):
        yield {
            "title": (item.findtext("title") or "").strip(),
            "published": parsedate_to_datetime(item.findtext("pubDate")),
            "link": (item.findtext("link") or "").strip(),
            "subtitle": (item.findtext("description") or "").strip(),
            "content": item.findtext(CONTENT_NS) or "",
            "sender": item.findtext("{http://purl.org/dc/elements/1.1/}creator") or "",
        }


def _atom_items(root):
    for entry in root.iter(ATOM + "entry"):
        when = entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated")
        author = entry.find(ATOM + "author")
        sender = " ".join((author.findtext(ATOM + t) or "") for t in ("name", "email")) if author is not None else ""
        link = entry.find(ATOM + "link[@rel='alternate']")
        if link is None:
            link = entry.find(ATOM + "link")
        yield {
            "title": (entry.findtext(ATOM + "title") or "").strip(),
            "published": datetime.fromisoformat(when.strip().replace("Z", "+00:00")),
            "link": link.get("href", "") if link is not None else "",
            "subtitle": "",
            "content": entry.findtext(ATOM + "content") or "",
            "sender": sender,
        }


def _issue_number(source, title, content):
    if source.get("title_re"):
        m = re.match(source["title_re"], title)
        return int(m.group(1)) if m else None
    m = re.search(source["number_re"], title, re.I)
    if not m:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", content))
        m = re.search(source["number_re"], text[:3000], re.I)   # 期号在邮件头部，别被正文里的"No. 1"之类误伤
    return int(m.group(1)) if m else None


def parse_feed(xml_text, source):
    root = ET.fromstring(xml_text)
    items = _atom_items(root) if source.get("format") == "atom" else _rss_items(root)
    issues = []
    for it in items:
        if source.get("content_re") and not re.search(source["content_re"], it["content"]):
            continue
        number = _issue_number(source, it["title"], it["content"])
        if number is None:
            continue
        published = it["published"].astimezone(timezone.utc)
        html, links = clean_html(it["content"])
        link = it["link"]
        if source.get("web_version_re"):
            # 邮件转feed服务给的link指向它自己那份(地址里带收件邮箱ID)，换成发件方的网页版；没找到就留空
            m = re.search(source["web_version_re"], it["content"])
            link = m.group(0).replace("&amp;", "&") if m else ""
        if source.get("drop_link_re"):
            links = [x for x in links if not re.search(source["drop_link_re"], x["href"], re.I)]
            for i, x in enumerate(links):
                x["i"] = i
        issues.append({
            "id": f"{source['slug']}-{number}",
            "series": source["series"],
            "author": source["author"],
            "number": number,
            "title": it["title"],
            "subtitle": it["subtitle"],
            "link": link,
            "date": published.date().isoformat(),
            "published": published.isoformat(),
            "html": html if source.get("store_html", True) else "",
            "links": links,
        })
    # 同一期可能收到两封(比如重发)，按期号去重留最早那封
    uniq = {}
    for x in sorted(issues, key=lambda x: x["published"]):
        uniq.setdefault(x["number"], x)
    return sorted(uniq.values(), key=lambda x: x["number"], reverse=True)


def select_new(issues, stored_numbers):
    """第一次(什么都没存)只要最新一期；之后只要比已存最大期号新的。"""
    if not issues:
        return []
    if not stored_numbers:
        return issues[:1]
    top = max(stored_numbers)
    return [x for x in issues if x["number"] > top]


def load_index():
    path = OUT_DIR / "index.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"letters": []}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = load_index()
    failed = []
    added = 0
    for source in LETTER_SOURCES:
        feed = source.get("feed") or os.environ.get(source.get("feed_env", ""), "")
        if not feed:
            print(f"[SKIP] {source['series']} — 没配 {source.get('feed_env')}")
            continue
        added_before = added
        try:
            resp = requests.get(feed, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0 (dailyDigest letters)"})
            resp.raise_for_status()
            issues = parse_feed(resp.content, source)
        except Exception as exc:  # 网络/解析出错只影响这一封，不拖垮整个跑批
            print(f"[FAIL] {source['series']} — {exc}")
            failed.append(source["series"])
            continue
        stored = [x["number"] for x in index["letters"] if x["id"].startswith(source["slug"] + "-")]
        for issue in select_new(issues, stored):
            (OUT_DIR / f"{issue['id']}.json").write_text(
                json.dumps(issue, ensure_ascii=False, indent=1), encoding="utf-8")
            entry = {k: issue[k] for k in ("id", "series", "author", "number", "title",
                                           "subtitle", "link", "date")}
            entry["links_count"] = len(issue["links"])
            index["letters"].append(entry)
            added += 1
            print(f"[OK] {issue['title']} ({issue['date']}) — {len(issue['links'])}个链接")
        if added == added_before:
            print(f"[OK] {source['series']} — 没有新一期")
    index["letters"].sort(key=lambda x: x["date"], reverse=True)
    index["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if added or not (OUT_DIR / "index.json").exists():
        (OUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
