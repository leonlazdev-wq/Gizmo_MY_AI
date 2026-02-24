import tempfile
import unittest
from pathlib import Path

import extensions.student_utils.script as su


class StudentUtilsTests(unittest.TestCase):
    def test_sanitize_filename(self):
        self.assertEqual(su.sanitize_filename("my file?.md"), "my_file__md")
        self.assertEqual(su.sanitize_filename(""), "chat_export")

    def test_export_chat_empty_history(self):
        msg, link, ok = su.export_chat([], "Markdown (.md)", "abc")
        self.assertIn("Start a chat", msg)
        self.assertEqual(link, "")
        self.assertFalse(ok)

    def test_save_and_load_notes_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "notes.txt"
            original = su.NOTES_FILE_CANDIDATES
            su.NOTES_FILE_CANDIDATES = [path]
            try:
                status, ok = su.save_notes("hello")
                self.assertIn("Saved", status)
                self.assertTrue(ok)
                self.assertEqual(su.load_notes(), "hello")
            finally:
                su.NOTES_FILE_CANDIDATES = original

    def test_activity_is_capped_to_50(self):
        items = []
        for i in range(70):
            items, _, _ = su.add_activity(items, f"event {i}")
        self.assertEqual(len(items), 50)
        self.assertEqual(items[0]["message"], "event 69")


if __name__ == "__main__":
    unittest.main()
