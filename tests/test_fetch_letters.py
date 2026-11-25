import json
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


BE = next(s for s in LETTER_SOURCES if s["slug"] == "be")
MC_ID = "b98e2de85f03865f1d38de74f"
ISSUE_HTML = (
    '<table><tr><td><a href="https://mailchi.mp/ben-evans/no-612?e=1">View this email in your browser</a>'
    "<p>Benedict's Newsletter NO. 612 FREE EDITION</p>"
    '<p>News <a href="https://techcrunch.com/x">a story</a> and <a href="https://www.ben-evans.com/newsletter">subscribe</a></p>'
    f'<a href="https://ben-evans.us6.list-manage.com/unsubscribe?u={MC_ID}&amp;id=1">unsubscribe</a>'
    "</td></tr></table>"
)
CONFIRM_HTML = f'<p>Confirm <a href="https://ben-evans.us6.list-manage.com/subscribe/confirm?u={MC_ID}">yes</a></p>'


def atom(*entries):
    from html import escape as esc
    body = "".join(
        f'<entry><title>{esc(t)}</title><published>{d}</published>'
        f'<author><name>bounce-md_1@mandrillapp.com</name></author>'
        f'<link rel="alternate" href="https://kill-the-newsletter.com/feeds/SECRET/entries/{i}.html"/>'
        f'<content type="html">{esc(c)}</content></entry>'
        for i, (t, d, c) in enumerate(entries))
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'.encode()


class TestBenedictAtom(unittest.TestCase):
    def setUp(self):
        self.issues = parse_feed(atom(
            ("Benedict's Newsletter: confirmation required", "2026-11-25T14:34:21.748Z", CONFIRM_HTML),
            ("Benedict's Newsletter", "2026-12-01T09:00:00.000Z", ISSUE_HTML),
            ("Spam pretending", "2026-12-02T09:00:00.000Z", "<p>NO. 999</p>"),
        ), BE)

    def test_only_real_issue_kept(self):
        # 确认信没有期号、伪造邮件没有他的Mailchimp账号ID，都被滤掉
        self.assertEqual([x["number"] for x in self.issues], [612])
        self.assertEqual(self.issues[0]["id"], "be-612")
        self.assertEqual(self.issues[0]["date"], "2026-12-01")

    def test_link_is_web_version_not_feed_service(self):
        self.assertEqual(self.issues[0]["link"], "https://mailchi.mp/ben-evans/no-612?e=1")
        self.assertNotIn("SECRET", json.dumps(self.issues[0]))

    def test_no_body_stored_and_only_recommended_links(self):
        self.assertEqual(self.issues[0]["html"], "")
        self.assertEqual([(l["i"], l["href"]) for l in self.issues[0]["links"]],
                         [(0, "https://techcrunch.com/x")])


if __name__ == "__main__":
    unittest.main()
