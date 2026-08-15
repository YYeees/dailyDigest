import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch_x import make_title, normalize_tweet, parse_tweet_date  # noqa: E402


class TestParseTweetDate(unittest.TestCase):
    def test_parses_twitter_date_format(self):
        result = parse_tweet_date("Wed Aug 12 17:48:36 +0000 2026")
        self.assertEqual(result, "2026-08-12T17:48:36+00:00")


class TestMakeTitle(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(make_title("hello world"), "hello world")

    def test_strips_and_collapses_newlines(self):
        self.assertEqual(make_title("  hello\nworld  "), "hello world")

    def test_truncates_long_text_with_ellipsis(self):
        text = "x" * 150
        result = make_title(text)
        self.assertEqual(len(result), 101)  # 100 chars + ellipsis
        self.assertTrue(result.endswith("…"))


class TestNormalizeTweet(unittest.TestCase):
    SOURCE = {"person": "Test Person", "x_username": "testuser"}
    TWEET = {
        "id": "12345",
        "url": "https://x.com/testuser/status/12345",
        "text": "hello world",
        "createdAt": "Wed Aug 12 17:48:36 +0000 2026",
    }

    def test_guid_namespaced_by_person(self):
        record = normalize_tweet(self.SOURCE, self.TWEET)
        self.assertEqual(record["guid"], "Test Person (X)::12345")

    def test_source_type_is_x(self):
        record = normalize_tweet(self.SOURCE, self.TWEET)
        self.assertEqual(record["source_type"], "x")

    def test_has_full_text_always_true(self):
        record = normalize_tweet(self.SOURCE, self.TWEET)
        self.assertEqual(record["has_full_text"], 1)


if __name__ == "__main__":
    unittest.main()
