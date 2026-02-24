import tempfile
import unittest
from pathlib import Path

import extensions.student_utils.script as su


class StudentUtilsTests(unittest.TestCase):
    def test_sanitize_filename(self):
        self.assertEqual(su.sanitize_filename("my file?.md"), "my_file__md")
        self.assertEqual(su.sanitize_filename(""), "chat_export")

    def test_export_chat_empty_history(self):
        msg, link = su.export_chat([], "Markdown (.md)", "abc")
        self.assertIn("Start a chat", msg)
        self.assertEqual(link, "")

    def test_save_and_load_notes_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "notes.txt"
            original = su.NOTES_FILE_CANDIDATES
            su.NOTES_FILE_CANDIDATES = [path]
            try:
                status = su.save_notes("hello")
                self.assertIn("Saved", status)
                self.assertEqual(su.load_notes(), "hello")
            finally:
                su.NOTES_FILE_CANDIDATES = original


if __name__ == "__main__":
    unittest.main()
