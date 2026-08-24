"""scan_inbox.py的回归测试。

重点锁死2026-08-24第一版踩的那个坑:norm_url整段剥掉query,导致所有
youtube.com/watch?v=XXX 归一化成同一个key,一条笔记匹配上库里全部YouTube内容,
eval数字静默判歪。这类bug不会让脚本报错,只会让结论错——正是最该有测试的地方。
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scan_inbox  # noqa: E402

ITEMS = [
    # guid, link, ranked, ai_tier, anchor_tier
    ("yt::a", "https://www.youtube.com/watch?v=AAA", "2026-08-01", "high", "low"),
    ("yt::b", "https://www.youtube.com/watch?v=BBB", "2026-08-01", "low", "low"),
    ("yt::c", "https://www.youtube.com/watch?v=CCC", "2026-08-01", "low", "low"),
    ("yt::d", "https://www.youtube.com/watch?v=DDD", "2026-08-01", "low", "low"),
    ("blog::x", "https://simonwillison.net/2026/Aug/20/foo/", "2026-08-01", "medium", "low"),
    # 同一篇文章从两个feed进来过(真实存在,见nav.al的两个源)
    ("navA::p", "https://nav.al/tokens", "2026-08-01", "low", "low"),
    ("navB::p", "https://nav.al/tokens", "2026-08-01", "low", "low"),
    ("old::z", "https://example.com/old", None, None, None),  # 没排过序,不进eval样本
]


def make_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE items (guid TEXT PRIMARY KEY, link TEXT, title TEXT, person TEXT,"
        " published TEXT, ai_tier TEXT, anchor_tier TEXT, ranked_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO items (guid, link, title, person, published, ranked_at, ai_tier, anchor_tier)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [(g, l, "T", "P", "2026-08-01", r, a, n) for g, l, r, a, n in ITEMS],
    )
    conn.commit()
    return conn


class TestNormUrl(unittest.TestCase):
    def test_youtube_video_ids_do_not_collide(self):
        """踩过的坑:剥掉整段query会让所有 watch?v=XXX 变成同一个key。"""
        a = scan_inbox.norm_url("https://www.youtube.com/watch?v=AAA")
        b = scan_inbox.norm_url("https://www.youtube.com/watch?v=BBB")
        self.assertNotEqual(a, b)

    def test_query_as_primary_key_is_preserved(self):
        """lexfridman的 ?p=6494 同理,query里装的是主键不是噪音。"""
        self.assertNotEqual(
            scan_inbox.norm_url("https://lexfridman.com/?p=6494"),
            scan_inbox.norm_url("https://lexfridman.com/?p=6474"),
        )

    def test_noise_is_normalized_away(self):
        base = scan_inbox.norm_url("https://nav.al/tokens")
        for variant in (
            "http://nav.al/tokens",
            "https://www.nav.al/tokens/",
            "https://nav.al/tokens?utm_source=x&utm_medium=y",
            "https://nav.al/tokens#section",
        ):
            self.assertEqual(scan_inbox.norm_url(variant), base, variant)

    def test_path_case_is_preserved(self):
        """simonwillison.net/2026/Aug/20/... 路径区分大小写,压平会造成误合并。"""
        self.assertNotEqual(
            scan_inbox.norm_url("https://simonwillison.net/2026/Aug/20/foo"),
            scan_inbox.norm_url("https://simonwillison.net/2026/aug/20/Foo"),
        )


class TestScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = Path(self.tmp.name)
        self.conn = make_db(":memory:")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def write(self, name, body):
        (self.inbox / name).write_text(body, encoding="utf-8")

    def scan(self):
        return {n["note"]: n for n in scan_inbox.scan(self.inbox, self.conn)}

    def test_exact_match(self):
        self.write("a.md", "---\nsource: https://www.youtube.com/watch?v=AAA\ndate: 2026-08-24\n---\n\n想法\n")
        n = self.scan()["a.md"]
        self.assertEqual(n["status"], "matched")
        self.assertEqual(n["guids"], ["yt::a"])

    def test_source_from_markdown_link_in_body(self):
        """页面「记一笔」生成的正是这个格式:frontmatter只有date,正文第一行是[标题](链接)。"""
        self.write("md.md", "---\ndate: 2026-08-24\n---\n\n[某个标题](https://www.youtube.com/watch?v=AAA)\n\n想法\n")
        n = self.scan()["md.md"]
        self.assertEqual(n["status"], "matched")
        self.assertEqual(n["guids"], ["yt::a"])

    def test_body_link_wins_over_frontmatter_source(self):
        """两种写法都认,但正文里那个是页面生成的、更可信。"""
        self.write("both.md", "---\nsource: https://nav.al/tokens\ndate: 2026-08-24\n---\n\n"
                              "[某个标题](https://www.youtube.com/watch?v=AAA)\n\n想法\n")
        self.assertEqual(self.scan()["both.md"]["guids"], ["yt::a"])

    def test_source_as_person_name_is_not_mistaken_for_url(self):
        """2026-08-24起frontmatter的source装的是信息来源名(人/刊物),不是URL。"""
        self.write("p.md", '---\nsource: "Latent Space"\ndate: 2026-08-24\n---\n\n'
                           '[某个标题](https://www.youtube.com/watch?v=AAA)\n\n想法\n')
        n = self.scan()["p.md"]
        self.assertEqual(n["person"], "Latent Space")
        self.assertEqual(n["guids"], ["yt::a"])

    def test_url_key_is_accepted_as_fallback(self):
        """手工建的笔记可以用 url: 写来源链接,不必非要markdown链接。"""
        self.write("u.md", "---\nurl: https://www.youtube.com/watch?v=AAA\ndate: 2026-08-24\n---\n\n想法\n")
        self.assertEqual(self.scan()["u.md"]["guids"], ["yt::a"])

    def test_legacy_source_as_url_still_works(self):
        """老格式(source里装URL)留了一手,不该因为改名就匹配不上。"""
        self.write("l.md", "---\nsource: https://www.youtube.com/watch?v=AAA\ndate: 2026-08-24\n---\n\n想法\n")
        self.assertEqual(self.scan()["l.md"]["guids"], ["yt::a"])

    def test_non_http_link_is_not_mistaken_for_source(self):
        """笔记里的wiki链接/相对链接不该被当成来源。"""
        self.write("rel.md", "---\ndate: 2026-08-24\n---\n\n[别的笔记](./other.md)\n\n想法\n")
        self.assertEqual(self.scan()["rel.md"]["status"], "no_source")

    def test_loose_match_survives_url_noise(self):
        self.write("b.md", "---\nsource: http://nav.al/tokens/?utm_source=x\ndate: 2026-08-24\n---\n\n想法\n")
        n = self.scan()["b.md"]
        self.assertEqual(n["status"], "matched")
        self.assertEqual(sorted(n["guids"]), ["navA::p", "navB::p"])  # 同一篇的两条记录都算

    def test_collision_is_reported_not_silently_matched(self):
        """归一化万一又把不同URL压成一个key,宁可判未匹配,也不要静默算出错的eval。"""
        original = scan_inbox.norm_url
        scan_inbox.norm_url = lambda u: "COLLIDE" if u else ""
        try:
            self.write("c.md", "---\nsource: https://whatever.example/x\ndate: 2026-08-24\n---\n\n想法\n")
            self.assertEqual(self.scan()["c.md"]["status"], "unmatched")
        finally:
            scan_inbox.norm_url = original

    def test_note_without_source_is_skipped_not_failed(self):
        """散步想到的想法照样往收件箱扔,不写source就是不参与eval,不该算成匹配失败。"""
        self.write("d.md", "---\ndate: 2026-08-24\n---\n\n跟digest无关的想法\n")
        self.assertEqual(self.scan()["d.md"]["status"], "no_source")

    def test_note_without_frontmatter_is_skipped(self):
        self.write("e.md", "随手写的,连frontmatter都没有\n")
        self.assertEqual(self.scan()["e.md"]["status"], "no_source")

    def test_readme_and_dotfiles_are_ignored(self):
        self.write("README.md", "---\nsource: https://nav.al/tokens\n---\n")
        self.write(".hidden.md", "---\nsource: https://nav.al/tokens\n---\n")
        self.assertEqual(self.scan(), {})

    def test_unmatched_source(self):
        self.write("f.md", "---\nsource: https://nowhere.example/nope\ndate: 2026-08-24\n---\n\n想法\n")
        self.assertEqual(self.scan()["f.md"]["status"], "unmatched")


if __name__ == "__main__":
    unittest.main()
