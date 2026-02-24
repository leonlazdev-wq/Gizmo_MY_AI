import unittest

from modules.colab_compat import (
    build_lesson_tabs_html,
    check_frontend_dependencies,
    run_colab_feature_smoke_test,
)


class ColabCompatTests(unittest.TestCase):
    def test_build_lesson_tabs_html_has_tabs(self):
        html = build_lesson_tabs_html()
        self.assertIn("role=\"tablist\"", html)
        self.assertIn("📚 Tutorials", html)
        self.assertIn("🛠️ Student Utils", html)

    def test_dependency_check_has_core_entries(self):
        checks = check_frontend_dependencies()
        names = {item.name for item in checks}
        self.assertIn("IPython.display", names)
        self.assertIn("extensions.learning_center.script", names)

    def test_smoke_report_contains_html_key(self):
        report = run_colab_feature_smoke_test()
        self.assertIn("lesson_tabs_html", report)


if __name__ == "__main__":
    unittest.main()
