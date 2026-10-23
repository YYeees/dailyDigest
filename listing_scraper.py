"""
没有RSS的信源：读官网列表页，把没见过的文章链接逐篇打开，拼成跟feedparser entry同形的dict，
交回fetch.py走同一条normalize_entry/入库路径。

2026-10-23为Anthropic写的(anthropic.com、claude.com的RSS地址全是404，本人渠道不存在RSS)。
实测时踩到的事实：
- sitemap.xml里的lastmod靠不住：270篇/news全被刷成了最近几天，判断不了新旧。所以只能靠
  "列表页上出现了库里没有的链接"来发现新文章。
- /news和/research两个列表页的HTML结构不一样(前者是TableView行，后者是卡片)，按结构解析
  必然有一边漏。所以只收href，元数据统一去文章页拿：每篇文章页都有og:title、
  article:published_time和<article>正文，这三样是模板级的，比列表页稳。
- 列表页上混着分类页链接(/news/product、/research/team/alignment)，它们没有
  article:published_time，靠这一点过滤，不维护分类名单——分类会加，名单会漏。
- news文章的meta description常常是全站默认文案，不是摘要，见_SITE_DEFAULT_DESC。

只对库里没有的链接打开文章页，所以稳态下一天只多几次请求；第一次跑会把列表页上的几十篇
全打开一遍。
"""

import re
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "Mozilla/5.0 (dailyDigest; +https://github.com/YYeees/dailyDigest)"}
_TIMEOUT = 30

_SITE_DEFAULT_DESC = "Anthropic is an AI safety and research company"


class ListingError(Exception):
    """列表页抓不到或者一篇文章链接都没解析出来——多半是官网改版，要让跑批报警。"""


def _article_links(source, html):
    pattern = re.compile(source["article_path_pattern"])
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.select("a[href]"):
        path = a["href"].split("#")[0].split("?")[0].rstrip("/")
        if pattern.match(path):
            url = urljoin(source["base_url"], path)
            if url not in links:
                links.append(url)
    return links


def parse_article(url, html):
    """文章页 → feedparser entry同形dict。不是文章(没有发布时间)返回None。"""
    soup = BeautifulSoup(html, "lxml")
    published = soup.select_one('meta[property="article:published_time"]')
    if published is None or not published.get("content"):
        return None
    dt = datetime.fromisoformat(published["content"].replace("Z", "+00:00"))

    title_tag = soup.select_one('meta[property="og:title"]')
    title = title_tag["content"].strip() if title_tag else (soup.title.get_text(strip=True) if soup.title else "")

    desc_tag = soup.select_one('meta[name="description"]')
    summary = desc_tag["content"].strip() if desc_tag else ""
    if summary.startswith(_SITE_DEFAULT_DESC):
        summary = ""

    article = soup.select_one("article")
    entry = {
        "id": url,
        "link": url,
        "title": title,
        "summary": summary,
        "published_parsed": dt.utctimetuple(),
    }
    if article is not None:
        entry["content"] = [{"value": str(article)}]
    return entry


def scrape_listing(source, is_known, get=requests.get):
    """返回列表页上新出现的文章(已入库的链接不再打开)。is_known(url) -> bool。"""
    links = []
    for listing_url in source["listing_urls"]:
        try:
            resp = get(listing_url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ListingError(f"{listing_url}: {e}") from e
        found = _article_links(source, resp.text)
        if not found:
            raise ListingError(f"{listing_url}: 一个文章链接都没解析出来，可能是官网改版")
        links.extend(u for u in found if u not in links)

    entries = []
    for url in links:
        if is_known(url):
            continue
        try:
            resp = get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[WARN] {source['name']}: 打不开{url}，下次再试 — {e}")
            continue
        entry = parse_article(url, resp.text)
        if entry is not None:
            entries.append(entry)
        time.sleep(0.5)
    return entries
