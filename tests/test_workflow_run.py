from modules.feature_workflows import run_workflow, save_workflow


def test_workflow_save_and_run():
    wid = save_workflow(
        "u1",
        {
            "name": "Build draft",
            "nodes": [
                {"id": "n1", "type": "Planner", "params": {}},
                {"id": "n2", "type": "WebSearch", "params": {}},
                {"id": "n3", "type": "Writer", "params": {}},
            ],
            "edges": [["n1", "n2"], ["n2", "n3"]],
        },
    )
    result = run_workflow(wid, "Explain photosynthesis")
    assert result["workflow_id"] == wid
    assert "draft" in result
