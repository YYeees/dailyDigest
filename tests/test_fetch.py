import sys
import time
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch import normalize_entry, parsed_time_to_iso  # noqa: E402


class TestParsedTimeToIso(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(parsed_time_to_iso(None))

    def test_struct_time_converts_to_iso_utc(self):
        struct = time.gmtime(0)  # 1970-01-01T00:00:00Z
        result = parsed_time_to_iso(struct)
        self.assertTrue(result.startswith("1970-01-01T00:00:00"))


class TestNormalizeEntry(unittest.TestCase):
    SOURCE = {"person": "Test Person", "name": "Test Source", "type": "blog", "url": "https://example.com/feed"}

    def test_guid_prefers_id_then_link(self):
        entry = {"id": "abc123", "link": "https://example.com/x"}
        record = normalize_entry(self.SOURCE, entry)
        self.assertEqual(record["guid"], "Test Source::abc123")

    def test_guid_falls_back_to_link(self):
        entry = {"link": "https://example.com/x"}
        record = normalize_entry(self.SOURCE, entry)
        self.assertEqual(record["guid"], "Test Source::https://example.com/x")

    def test_missing_title_defaults(self):
        entry = {"link": "https://example.com/x"}
        record = normalize_entry(self.SOURCE, entry)
        self.assertEqual(record["title"], "(无标题)")

    def test_has_full_text_flag(self):
        entry_with_content = {"link": "https://example.com/x", "content": [{"value": "full text"}]}
        entry_without_content = {"link": "https://example.com/y"}
        self.assertEqual(normalize_entry(self.SOURCE, entry_with_content)["has_full_text"], 1)
        self.assertEqual(normalize_entry(self.SOURCE, entry_without_content)["has_full_text"], 0)

    def test_carries_person_and_source_type(self):
        entry = {"link": "https://example.com/x"}
        record = normalize_entry(self.SOURCE, entry)
        self.assertEqual(record["person"], "Test Person")
        self.assertEqual(record["source_type"], "blog")


if __name__ == "__main__":
    unittest.main()
