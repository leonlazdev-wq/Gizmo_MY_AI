from pathlib import Path

from modules.ab_test import run_ab_test
from modules.demo_data import seed_demo_data
from modules.feedback import submit_feedback
from modules.theme import build_theme_css, save_theme
from modules.ui_snapshot import capture_ui_state


def test_ab_test_outputs():
    result = run_ab_test('A', 'B', 'hello')
    assert '[A]' in result['output_a']
    assert '[B]' in result['output_b']


def test_theme_save_and_css():
    css = build_theme_css('#111111', '#222222', 15)
    assert 'gizmo-theme-preview' in css
    path = save_theme('#111111', '#222222', 15)
    assert Path(path).exists()


def test_feedback_snapshot_demo_seed():
    feedback = submit_feedback('u1', 's1', 'Looks good', '')
    assert Path(feedback['path']).exists()

    snap = capture_ui_state('s1', {'tabs': ['Chat', 'Workflows']})
    assert Path(snap).exists()

    seeded = seed_demo_data()
    assert seeded['status'] == 'ok'
    assert Path(seeded['doc']).exists()
