import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_trending import cleanup_old_snapshots, init_db, parse_int, parse_trending_page  # noqa: E402

FIXTURE_HTML = """
<html><body>
<article class="Box-row">
  <h2><a href="/owner/repo">owner /<span> repo</span></a></h2>
  <p class="col-9">A test repository description.</p>
  <span itemprop="programmingLanguage">Python</span>
  <a href="/owner/repo/stargazers">1,234</a>
  <div class="f6">
    <span>1,234 stars</span>
    <span>56 forks</span>
    <span>78 stars this week</span>
  </div>
</article>
</body></html>
"""


class TestParseInt(unittest.TestCase):
    def test_parses_comma_separated_number(self):
        self.assertEqual(parse_int("1,234"), 1234)

    def test_none_or_empty_returns_none(self):
        self.assertIsNone(parse_int(None))
        self.assertIsNone(parse_int(""))

    def test_non_numeric_returns_none(self):
        self.assertIsNone(parse_int("N/A"))


class TestParseTrendingPage(unittest.TestCase):
    def test_extracts_single_repo(self):
        results = parse_trending_page(FIXTURE_HTML)
        self.assertEqual(len(results), 1)
        repo = results[0]
        self.assertEqual(repo["full_name"], "owner/repo")
        self.assertEqual(repo["language"], "Python")
        self.assertEqual(repo["stars_total"], 1234)
        self.assertEqual(repo["stars_today"], 78)  # matches "this week" via STARS_TODAY_RE
        self.assertEqual(repo["rank"], 1)

    def test_empty_page_returns_empty_list(self):
        self.assertEqual(parse_trending_page("<html><body>no repos here</body></html>"), [])


class TestCleanupOldSnapshots(unittest.TestCase):
    def test_deletes_snapshots_older_than_retention_window(self):
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        old_date = (date.today() - timedelta(days=200)).isoformat()
        recent_date = (date.today() - timedelta(days=1)).isoformat()
        conn.execute(
            "INSERT INTO daily_snapshots (full_name, snapshot_date, trending_page, rank, stars_total, stars_today) "
            "VALUES ('a/old', ?, 'all', 1, 10, 1)", (old_date,),
        )
        conn.execute(
            "INSERT INTO daily_snapshots (full_name, snapshot_date, trending_page, rank, stars_total, stars_today) "
            "VALUES ('a/recent', ?, 'all', 1, 10, 1)", (recent_date,),
        )
        conn.commit()

        removed = cleanup_old_snapshots(conn)

        self.assertEqual(removed, 1)
        remaining = [r[0] for r in conn.execute("SELECT full_name FROM daily_snapshots")]
        self.assertEqual(remaining, ["a/recent"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
