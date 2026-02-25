"""Tests for modules/backup_restore.py."""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestCreateBackup(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import modules.backup_restore as br
        self._orig_user_data = br._USER_DATA
        self._orig_backup_dir = br._BACKUP_DIR
        # Point user_data and backup dir to temp locations
        self._fake_user_data = Path(self._tmpdir) / "user_data"
        self._fake_user_data.mkdir()
        (self._fake_user_data / "memory.json").write_text('[]', encoding='utf-8')
        (self._fake_user_data / "flashcards").mkdir()
        (self._fake_user_data / "flashcards" / "bio.json").write_text('[]', encoding='utf-8')
        br._USER_DATA = self._fake_user_data
        br._BACKUP_DIR = Path(self._tmpdir) / "backups"

    def tearDown(self):
        import modules.backup_restore as br
        br._USER_DATA = self._orig_user_data
        br._BACKUP_DIR = self._orig_backup_dir
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_create_backup_returns_zip_path(self):
        from modules.backup_restore import create_backup
        msg, path = create_backup(include_all=True)
        self.assertIn("✅", msg)
        self.assertIsNotNone(path)
        self.assertTrue(Path(path).exists())
        self.assertTrue(zipfile.is_zipfile(path))

    def test_created_zip_contains_files(self):
        from modules.backup_restore import create_backup
        _, path = create_backup(include_all=True)
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
        self.assertTrue(any("memory.json" in n for n in names))
        self.assertTrue(any("bio.json" in n for n in names))

    def test_create_backup_selective(self):
        from modules.backup_restore import create_backup
        msg, path = create_backup(include_all=False)
        # Even with selective mode, should succeed (items may not all exist)
        self.assertIsNotNone(path)


class TestRestoreBackup(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import modules.backup_restore as br
        self._orig_backup_dir = br._BACKUP_DIR
        br._BACKUP_DIR = Path(self._tmpdir) / "backups"

    def tearDown(self):
        import modules.backup_restore as br
        br._BACKUP_DIR = self._orig_backup_dir
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _make_test_zip(self) -> str:
        """Create a minimal valid backup zip in tmpdir."""
        zip_path = Path(self._tmpdir) / "test_backup.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("user_data/memory.json", json.dumps([{"fact": "test"}]))
            zf.writestr("user_data/flashcards/test.json", json.dumps([{"q": "q", "a": "a"}]))
        return str(zip_path)

    def test_restore_valid_zip(self):
        from modules.backup_restore import restore_backup
        zip_path = self._make_test_zip()
        # Patch create_backup so no real backup is taken during test
        with patch("modules.backup_restore.create_backup", return_value=("ok", "/tmp/fake.zip")):
            msg = restore_backup(zip_path, create_pre_restore_backup=True)
        self.assertIn("✅", msg)

    def test_restore_nonexistent_file(self):
        from modules.backup_restore import restore_backup
        msg = restore_backup("/tmp/nonexistent_backup.zip")
        self.assertIn("❌", msg)

    def test_restore_invalid_zip(self):
        bad_zip = Path(self._tmpdir) / "bad.zip"
        bad_zip.write_text("this is not a zip file", encoding="utf-8")
        from modules.backup_restore import restore_backup
        msg = restore_backup(str(bad_zip))
        self.assertIn("❌", msg)

    def test_restore_zip_without_user_data(self):
        zip_path = Path(self._tmpdir) / "no_user_data.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("other_dir/file.json", "{}")
        from modules.backup_restore import restore_backup
        msg = restore_backup(str(zip_path))
        self.assertIn("❌", msg)
        self.assertIn("user_data", msg)


class TestIndividualExportImport(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_export_flashcard_deck_not_found(self):
        from modules.backup_restore import export_flashcard_deck
        msg, path = export_flashcard_deck("nonexistent_deck_xyz")
        self.assertIn("❌", msg)
        self.assertIsNone(path)

    def test_export_quiz_results_no_dir(self):
        import modules.backup_restore as br
        from modules.backup_restore import export_quiz_results
        orig_user_data = br._USER_DATA
        br._USER_DATA = Path(self._tmpdir) / "empty_user_data"
        try:
            msg, path = export_quiz_results()
            self.assertIsInstance(msg, str)
        finally:
            br._USER_DATA = orig_user_data

    def test_import_unknown_type(self):
        import json
        from modules.backup_restore import import_item
        fake_json = Path(self._tmpdir) / "test.json"
        fake_json.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        msg = import_item(str(fake_json), "unknown_type")
        self.assertIn("❌", msg)

    def test_import_nonexistent_file(self):
        from modules.backup_restore import import_item
        msg = import_item("/tmp/does_not_exist_xyz.json", "memory")
        self.assertIn("❌", msg)

    def test_import_invalid_json(self):
        from modules.backup_restore import import_item
        bad_file = Path(self._tmpdir) / "bad.json"
        bad_file.write_text("not valid json {{{{", encoding="utf-8")
        msg = import_item(str(bad_file), "flashcards")
        self.assertIn("❌", msg)


class TestBackupHistory(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import modules.backup_restore as br
        self._orig_backup_dir = br._BACKUP_DIR
        br._BACKUP_DIR = Path(self._tmpdir) / "backups"

    def tearDown(self):
        import modules.backup_restore as br
        br._BACKUP_DIR = self._orig_backup_dir
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_list_local_backups_empty(self):
        from modules.backup_restore import list_local_backups
        result = list_local_backups()
        self.assertEqual(result, [])

    def test_list_local_backups_after_create(self):
        from modules.backup_restore import create_backup, list_local_backups
        create_backup(include_all=False)
        backups = list_local_backups()
        self.assertGreaterEqual(len(backups), 1)
        self.assertIn("name", backups[0])
        self.assertIn("size_kb", backups[0])
        self.assertIn("modified", backups[0])

    def test_get_backup_history_table_returns_list(self):
        from modules.backup_restore import get_backup_history_table
        table = get_backup_history_table()
        self.assertIsInstance(table, list)

    def test_list_drive_backups_no_drive(self):
        from modules.backup_restore import list_drive_backups
        with patch("modules.backup_restore.is_drive_mounted", return_value=False):
            result = list_drive_backups()
        self.assertEqual(result, [])


class TestDriveBackup(unittest.TestCase):
    def test_drive_backup_not_mounted(self):
        from modules.backup_restore import backup_to_drive
        with patch("modules.backup_restore.is_drive_mounted", return_value=False):
            msg = backup_to_drive()
        self.assertIn("⚠️", msg)
        self.assertIn("not mounted", msg)


if __name__ == "__main__":
    unittest.main()
