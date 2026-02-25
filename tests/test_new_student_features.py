"""Tests for the five new student productivity modules."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestTranslation(unittest.TestCase):
    def test_word_count_basic(self):
        from modules.translation import word_count
        result = word_count("Hello world this is a test")
        self.assertIn("6 words", result)
        self.assertIn("characters", result)

    def test_word_count_empty(self):
        from modules.translation import word_count
        result = word_count("")
        self.assertIn("0 words", result)

    def test_languages_list_has_auto_detect(self):
        from modules.translation import LANGUAGES, TARGET_LANGUAGES
        self.assertIn("Auto-detect", LANGUAGES)
        self.assertNotIn("Auto-detect", TARGET_LANGUAGES)
        self.assertIn("English", TARGET_LANGUAGES)
        self.assertIn("Spanish", TARGET_LANGUAGES)

    def test_save_and_list_translation(self):
        import tempfile, os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmpdir:
            translations_dir = os.path.join(tmpdir, "translations")
            import modules.translation as tl_mod
            original_dir = tl_mod._TRANSLATIONS_DIR
            tl_mod._TRANSLATIONS_DIR = translations_dir
            try:
                msg = tl_mod.save_translation("Hello", "Hola", "English", "Spanish")
                self.assertIn("✅", msg)
                results = tl_mod.list_translations()
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["source_text"], "Hello")
                self.assertEqual(results[0]["translated_text"], "Hola")
            finally:
                tl_mod._TRANSLATIONS_DIR = original_dir

    def test_delete_translation(self):
        import tempfile, os
        from modules import translation as tl_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            tl_mod._TRANSLATIONS_DIR = os.path.join(tmpdir, "translations")
            tl_mod.save_translation("Bye", "Adios", "English", "Spanish")
            results = tl_mod.list_translations()
            self.assertEqual(len(results), 1)
            tid = results[0]["id"]
            msg = tl_mod.delete_translation(tid)
            self.assertIn("✅", msg)
            self.assertEqual(tl_mod.list_translations(), [])


class TestGamification(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self._tmpdir = tempfile.mkdtemp()
        import modules.gamification as gm
        self._original_file = gm._GAMIFICATION_FILE
        gm._GAMIFICATION_FILE = os.path.join(self._tmpdir, "gamification.json")

    def tearDown(self):
        import modules.gamification as gm
        gm._GAMIFICATION_FILE = self._original_file
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_get_level_info_zero_xp(self):
        from modules.gamification import get_level_info
        info = get_level_info(0)
        self.assertEqual(info["level"], 1)
        self.assertEqual(info["level_name"], "Beginner")
        self.assertEqual(info["xp"], 0)

    def test_get_level_info_levels_up(self):
        from modules.gamification import get_level_info
        info = get_level_info(150)
        self.assertEqual(info["level"], 2)
        self.assertEqual(info["level_name"], "Learner")

    def test_award_xp(self):
        from modules.gamification import award_xp, get_all_data
        result = award_xp(50, "test")
        self.assertEqual(result["xp"], 50)
        data = get_all_data()
        self.assertEqual(data["xp"], 50)

    def test_award_xp_level_up(self):
        from modules.gamification import award_xp
        result = award_xp(100, "test level up")
        self.assertTrue(result["leveled_up"])
        self.assertEqual(result["level"], 2)

    def test_check_badge_unknown(self):
        from modules.gamification import check_badge
        result = check_badge("nonexistent_badge")
        self.assertFalse(result)

    def test_increment_stat_and_check_badge(self):
        from modules.gamification import increment_stat, check_badge, get_all_data
        for _ in range(1):
            increment_stat("quizzes_completed", 1)
        earned = check_badge("first_quiz")
        self.assertTrue(earned)
        data = get_all_data()
        self.assertIn("first_quiz", data["badges"])

    def test_badges_dict_has_required_keys(self):
        from modules.gamification import BADGES
        for badge_id, badge in BADGES.items():
            self.assertIn("name", badge)
            self.assertIn("icon", badge)
            self.assertIn("description", badge)

    def test_weekly_activity_returns_7_days(self):
        from modules.gamification import get_weekly_activity
        weekly = get_weekly_activity()
        self.assertEqual(len(weekly), 7)

    def test_get_streak(self):
        from modules.gamification import get_streak
        streak = get_streak()
        self.assertIn("current", streak)
        self.assertIn("longest", streak)


class TestEssayWriter(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self._tmpdir = tempfile.mkdtemp()
        import modules.essay_writer as ew
        self._original_dir = ew._ESSAYS_DIR
        ew._ESSAYS_DIR = os.path.join(self._tmpdir, "essays")

    def tearDown(self):
        import modules.essay_writer as ew
        ew._ESSAYS_DIR = self._original_dir
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_word_count_stats(self):
        from modules.essay_writer import word_count_stats
        stats = word_count_stats("This is a test sentence. Another sentence here.")
        self.assertEqual(stats["words"], 8)
        self.assertGreater(stats["sentences"], 0)
        self.assertIn("reading_level", stats)

    def test_word_count_stats_empty(self):
        from modules.essay_writer import word_count_stats
        stats = word_count_stats("")
        self.assertEqual(stats["words"], 0)
        self.assertEqual(stats["sentences"], 0)

    def test_save_and_list_essays(self):
        from modules.essay_writer import save_essay, list_essays
        msg = save_essay("Test Essay", {"topic": "Testing", "full_essay": "Hello world."})
        self.assertIn("✅", msg)
        essays = list_essays()
        self.assertEqual(len(essays), 1)
        self.assertEqual(essays[0]["topic"], "Testing")

    def test_export_markdown(self):
        from modules.essay_writer import export_essay_markdown
        data = {
            "title": "My Essay",
            "topic": "Testing",
            "essay_type": "Argumentative",
            "full_essay": "This is the essay content.",
        }
        md = export_essay_markdown(data)
        self.assertIn("# My Essay", md)
        self.assertIn("Testing", md)

    def test_essay_types_and_levels(self):
        from modules.essay_writer import ESSAY_TYPES, ACADEMIC_LEVELS
        self.assertIn("Argumentative", ESSAY_TYPES)
        self.assertIn("Narrative", ESSAY_TYPES)
        self.assertIn("Graduate", ACADEMIC_LEVELS)
        self.assertIn("High School", ACADEMIC_LEVELS)


class TestCollaborativeStudy(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self._tmpdir = tempfile.mkdtemp()
        import modules.collaborative_study as cs
        self._original_dir = cs._STUDY_ROOMS_DIR
        cs._STUDY_ROOMS_DIR = os.path.join(self._tmpdir, "study_rooms")

    def tearDown(self):
        import modules.collaborative_study as cs
        cs._STUDY_ROOMS_DIR = self._original_dir
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_create_room(self):
        from modules.collaborative_study import create_room, get_room_info
        code, err = create_room("Test Room", "Alice")
        self.assertIsNone(err)
        self.assertEqual(len(code), 6)
        room, err2 = get_room_info(code)
        self.assertIsNone(err2)
        self.assertEqual(room["name"], "Test Room")
        self.assertIn("Alice", room["participants"])

    def test_join_room(self):
        from modules.collaborative_study import create_room, join_room
        code, _ = create_room("Study Hall", "Alice")
        room, err = join_room(code, "Bob")
        self.assertIsNone(err)
        self.assertIn("Bob", room["participants"])

    def test_join_nonexistent_room(self):
        from modules.collaborative_study import join_room
        room, err = join_room("XXXXXX")
        self.assertIsNone(room)
        self.assertIn("not found", err)

    def test_send_chat_message(self):
        from modules.collaborative_study import create_room, send_chat_message
        code, _ = create_room("Chat Test", "Alice")
        chat, err = send_chat_message(code, "Alice", "Hello!")
        self.assertIsNone(err)
        self.assertEqual(len(chat), 1)
        self.assertEqual(chat[0]["message"], "Hello!")

    def test_get_scoreboard_empty(self):
        from modules.collaborative_study import create_room, get_scoreboard
        code, _ = create_room("Score Test", "Alice")
        scores = get_scoreboard(code)
        self.assertEqual(scores, {})

    def test_create_room_empty_name(self):
        from modules.collaborative_study import create_room
        code, err = create_room("")
        self.assertEqual(code, "")
        self.assertIsNotNone(err)


class TestTtsReader(unittest.TestCase):
    def test_detect_engine_returns_tuple(self):
        from modules.tts_reader import detect_tts_engine
        engine, msg = detect_tts_engine()
        self.assertIsInstance(engine, str)
        self.assertIsInstance(msg, str)

    def test_split_paragraphs(self):
        from modules.tts_reader import split_into_paragraphs
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        paragraphs = split_into_paragraphs(text)
        self.assertEqual(len(paragraphs), 3)
        self.assertEqual(paragraphs[0], "First paragraph.")

    def test_extract_text_unsupported(self):
        from modules.tts_reader import extract_text_from_file
        text, msg = extract_text_from_file("/tmp/test.xyz")
        self.assertEqual(text, "")
        self.assertIn("Unsupported", msg)

    def test_load_settings_defaults(self):
        import tempfile, os
        from modules import tts_reader as tts_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = tts_mod._TTS_SETTINGS_FILE
            tts_mod._TTS_SETTINGS_FILE = os.path.join(tmpdir, "tts_settings.json")
            try:
                settings = tts_mod.load_settings()
                self.assertIn("engine", settings)
                self.assertIn("language", settings)
                self.assertIn("speed", settings)
            finally:
                tts_mod._TTS_SETTINGS_FILE = orig

    def test_save_and_load_settings(self):
        import tempfile, os
        from modules import tts_reader as tts_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = tts_mod._TTS_SETTINGS_FILE
            tts_mod._TTS_SETTINGS_FILE = os.path.join(tmpdir, "tts_settings.json")
            try:
                msg = tts_mod.save_settings({
                    "engine": "gtts", "language": "es", "speed": 1.5,
                    "auto_play": True, "reading_mode": "Full document",
                })
                self.assertIn("✅", msg)
                loaded = tts_mod.load_settings()
                self.assertEqual(loaded["engine"], "gtts")
                self.assertEqual(loaded["language"], "es")
            finally:
                tts_mod._TTS_SETTINGS_FILE = orig

    def test_languages_list(self):
        from modules.tts_reader import TTS_LANGUAGES
        codes = [code for _, code in TTS_LANGUAGES]
        self.assertIn("en", codes)
        self.assertIn("es", codes)
        self.assertIn("ja", codes)


if __name__ == "__main__":
    unittest.main()
