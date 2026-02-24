from pathlib import Path

from modules.feature_workflows import ensure_demo_workflow, run_workflow_path


def test_demo_workflow_created_and_runs():
    path = ensure_demo_workflow()
    assert Path(path).exists()
    out = run_workflow_path(path, 'Explain gravity')
    assert 'answer' in out
