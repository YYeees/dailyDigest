import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from content_extract import extract_body, html_to_text, is_truncated  # noqa: E402


def entry(html):
    return {"content": [{"value": html}]}


class TestHtmlToText(unittest.TestCase):
    def test_keeps_heading_and_list_structure(self):
        out = html_to_text("<h2><strong>标题</strong></h2><p>正文</p><ul><li>一</li><li>二</li></ul>")
        self.assertEqual(out, "## 标题\n正文\n\n- 一\n- 二")

    def test_unescapes_entities(self):
        self.assertEqual(html_to_text("<p>Bio &#215; AI &amp; more</p>"), "Bio × AI & more")

    def test_drops_script_and_style(self):
        self.assertEqual(html_to_text("<style>a{b:c}</style><p>正文</p><script>x()</script>"), "正文")


class TestExtractBody(unittest.TestCase):
    def test_no_content_field_returns_none(self):
        # Simon Willison/Craig Mod/Lex这类源的RSS没有content，只能靠WebFetch
        self.assertIsNone(extract_body("标题", {}))
        self.assertIsNone(extract_body("标题", entry("   ")))

    def test_ainews_cut_at_first_recap_section(self):
        html = ("<p>编者按正文</p><h1><strong>AI Twitter Recap</strong></h1>"
                "<p>大段机器聚合的社媒原文</p><h1><strong>AI Reddit Recap</strong></h1><p>更多</p>")
        self.assertEqual(extract_body("[AINews] 某某", entry(html)), "编者按正文")

    def test_recap_cut_only_applies_to_ainews(self):
        # 播客/文章标题没有[AINews]前缀，整篇留下
        html = "<p>开头</p><h1><strong>AI Twitter Recap</strong></h1><p>后面</p>"
        self.assertIn("后面", extract_body("React for Agents — 某嘉宾, 某公司", entry(html)))

    def test_ainews_without_recap_section_keeps_everything(self):
        self.assertEqual(extract_body("[AINews] 某某", entry("<p>只有编者按</p>")), "只有编者按")

    def test_strips_substack_read_more_footer(self):
        html = '<p>正文</p>\n <p>\n <a href="https://x/p/y">\n Read more\n </a>\n </p>'
        self.assertEqual(extract_body("标题", entry(html)), "正文")

    def test_respects_cap(self):
        # 播客集数偶尔带完整转录稿(实测有一条133K字符)，必须截断
        self.assertEqual(len(extract_body("标题", entry("<p>" + "字" * 5000 + "</p>"), cap=100)), 100)


class TestIsTruncated(unittest.TestCase):
    def test_ellipsis_ending_is_truncated(self):
        self.assertTrue(is_truncated("Where you can see the degree to which 3.5 and 3.6 Flash had fallen behind…"))

    def test_missing_body_is_truncated(self):
        self.assertTrue(is_truncated(None))
        self.assertTrue(is_truncated(""))

    def test_long_body_is_not_truncated(self):
        self.assertFalse(is_truncated("正" * 600))

    def test_short_body_without_ellipsis_still_truncated(self):
        # 长度和省略号一起看：`[AINews] not much happened today`那种真的很短的不该误判，
        # 但500字符以下的确实不够判断，宁可去抓一次原文
        self.assertTrue(is_truncated("很短的一段"))


if __name__ == "__main__":
    unittest.main()
