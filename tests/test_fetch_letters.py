import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from fetch_letters import clean_html, parse_feed, select_new, LETTER_SOURCES  # noqa: E402

FEED = """<?xml version="1.0"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
<item><title><![CDATA[Joy & Curiosity #105]]></title>
<link>https://example.com/p/jc-105</link><pubDate>Sun, 08 Nov 2026 08:24:03 GMT</pubDate>
<description>Interesting things</description>
<content:encoded><![CDATA[<p>Hi <a href="https://a.com/x">A</a></p>]]></content:encoded></item>
<item><title><![CDATA[Some normal post]]></title>
<link>https://example.com/p/other</link><pubDate>Sat, 07 Nov 2026 08:00:00 GMT</pubDate>
<content:encoded><![CDATA[<p>x</p>]]></content:encoded></item>
<item><title><![CDATA[Joy & Curiosity #104]]></title>
<link>https://example.com/p/jc-104</link><pubDate>Sun, 01 Nov 2026 08:00:00 GMT</pubDate>
<content:encoded><![CDATA[<p>old</p>]]></content:encoded></item>
</channel></rss>"""


class TestCleanHtml(unittest.TestCase):
    def test_drops_subscribe_widget_and_form(self):
        raw = ('<p>Before</p><div class="subscription-widget-wrap-editor"><div class="subscription-widget">'
               '<p class="cta-caption">Subscribe!</p><form><input type="email"><input type="submit"></form>'
               '</div></div><p>After</p>')
        html, links = clean_html(raw)
        self.assertEqual(html, "<p>Before</p><p>After</p>")
        self.assertEqual(links, [])

    def test_links_numbered_and_open_in_new_tab(self):
        html, links = clean_html('<ul><li><p><a href="https://a.com" class="x">One</a> and '
                                 '<a href="https://b.com">Two</a></p></li></ul>')
        self.assertIn('data-i="0"', html)
        self.assertIn('data-i="1"', html)
        self.assertIn('target="_blank"', html)
        self.assertNotIn('class=', html)
        self.assertEqual([l["text"] for l in links], ["One", "Two"])

    def test_picture_keeps_only_img_and_image_wrapper_link_not_counted(self):
        raw = ('<div class="captioned-image-container"><figure><a class="image-link" '
               'href="https://substackcdn.com/image/big.png"><picture><source srcset="x 1x">'
               '<img src="https://substackcdn.com/image/a.png" alt="pic" srcset="y"></picture></a></figure></div>')
        html, links = clean_html(raw)
        self.assertEqual(html, '<figure><img src="https://substackcdn.com/image/a.png" alt="pic" loading="lazy"></figure>')
        self.assertEqual(links, [])

    def test_text_is_escaped(self):
        html, _ = clean_html("<p>a &lt;script&gt; b</p>")
        self.assertEqual(html, "<p>a &lt;script&gt; b</p>")


class TestParseAndSelect(unittest.TestCase):
    def setUp(self):
        self.issues = parse_feed(FEED.encode(), LETTER_SOURCES[0])

    def test_only_series_issues_newest_first(self):
        self.assertEqual([x["number"] for x in self.issues], [105, 104])
        self.assertEqual(self.issues[0]["id"], "jc-105")
        self.assertEqual(self.issues[0]["date"], "2026-11-08")
        self.assertEqual(self.issues[0]["links"][0]["href"], "https://a.com/x")

    def test_first_run_takes_only_latest(self):
        self.assertEqual([x["number"] for x in select_new(self.issues, [])], [105])

    def test_later_runs_take_only_newer(self):
        self.assertEqual(select_new(self.issues, [105]), [])
        self.assertEqual([x["number"] for x in select_new(self.issues, [104])], [105])


if __name__ == "__main__":
    unittest.main()
