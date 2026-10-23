import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from listing_scraper import ListingError, parse_article, scrape_listing  # noqa: E402

SOURCE = {
    "name": "Anthropic", "base_url": "https://www.anthropic.com",
    "listing_urls": ["https://www.anthropic.com/news"],
    "article_path_pattern": r"^/(news|research)/(?!team/)[A-Za-z0-9-]+$",
}

LISTING = """<a href="/news/foo">Foo</a><a href="/news/foo">Foo again</a>
<a href="/news/product">分类页</a><a href="/research/team/alignment">团队页</a>
<a href="/careers">无关</a>"""

ARTICLE = """<html><head><meta property="og:title" content="Foo title"/>
<meta name="description" content="Anthropic is an AI safety and research company that's working..."/>
<meta property="article:published_time" content="2026-10-22T00:00:00.000Z"/></head>
<body><article><h1>Foo</h1><p>正文</p></article></body></html>"""

CATEGORY = "<html><head><meta property=\"og:title\" content=\"Product\"/></head><body></body></html>"


class FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def fake_get(pages):
    def get(url, **kwargs):
        return FakeResp(pages[url])
    return get


class TestParseArticle(unittest.TestCase):
    def test_article(self):
        e = parse_article("https://www.anthropic.com/news/foo", ARTICLE)
        self.assertEqual(e["title"], "Foo title")
        self.assertEqual(e["published_parsed"][:3], (2026, 10, 22))
        self.assertEqual(e["summary"], "")  # 全站默认描述不当摘要
        self.assertIn("正文", e["content"][0]["value"])

    def test_page_without_published_time_is_not_article(self):
        self.assertIsNone(parse_article("https://www.anthropic.com/news/product", CATEGORY))


class TestScrapeListing(unittest.TestCase):
    PAGES = {
        "https://www.anthropic.com/news": LISTING,
        "https://www.anthropic.com/news/foo": ARTICLE,
        "https://www.anthropic.com/news/product": CATEGORY,
    }

    def test_new_articles_only(self):
        entries = scrape_listing(SOURCE, lambda url: False, get=fake_get(self.PAGES))
        self.assertEqual([e["link"] for e in entries], ["https://www.anthropic.com/news/foo"])

    def test_known_links_are_not_fetched(self):
        pages = dict(self.PAGES)
        del pages["https://www.anthropic.com/news/foo"]  # 打开就KeyError
        entries = scrape_listing(SOURCE, lambda url: url.endswith("/foo"), get=fake_get(pages))
        self.assertEqual(entries, [])

    def test_empty_listing_raises(self):
        with self.assertRaises(ListingError):
            scrape_listing(SOURCE, lambda url: False, get=fake_get({"https://www.anthropic.com/news": "<html></html>"}))


if __name__ == "__main__":
    unittest.main()
