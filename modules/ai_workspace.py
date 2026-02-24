"""Advanced multi-agent workspace helpers for GitHub orchestration."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def _run_git(args: List[str], cwd: Path) -> Tuple[int, str, str]:
    proc = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _workspace_dir(repo: Path) -> Path:
    p = repo / "user_data" / "ai_workspace"
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_execution_plan(task: str, strategy: str) -> List[Dict[str, str]]:
    base = [
        ("Planner", "Break task into milestones and risk list."),
        ("Coder", "Implement core code changes."),
        ("Reviewer", "Review diffs and identify regressions."),
        ("Security", "Run secrets and unsafe pattern checks."),
        ("Test-writer", "Create/update tests and validation scripts."),
        ("Docs", "Write changelog and rationale notes."),
    ]
    return [{"role": role, "subtask": f"[{strategy}] {desc} Task: {task.strip()}"} for role, desc in base]


def start_parallel_branches(repo_path: str, base_branch: str, task: str, strategy: str, max_agents: int) -> Tuple[str, str, List[List[str]]]:
    repo = Path((repo_path or ".").strip() or ".").resolve()
    if not (repo / ".git").exists():
        return "❌ Invalid repository path.", "", []
    if not (task or "").strip():
        return "❌ Task required.", "", []

    agents = create_execution_plan(task, strategy)[: max(1, min(8, int(max_agents or 1)))]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    integration_branch = f"gizmo/integration-{stamp}"
    rows: List[List[str]] = []

    _run_git(["checkout", base_branch or "main"], repo)
    _run_git(["checkout", "-B", integration_branch], repo)

    board_dir = _workspace_dir(repo)
    board_file = board_dir / f"kanban_{stamp}.json"
    bus_file = board_dir / "memory_bus.json"
    timeline_file = board_dir / f"timeline_{stamp}.log"

    backlog = []
    for idx, agent in enumerate(agents, start=1):
        role = agent["role"].lower().replace(" ", "-")
        branch = f"gizmo/{role}-{stamp}-{idx}"
        _run_git(["checkout", base_branch or "main"], repo)
        code, _, err = _run_git(["checkout", "-B", branch], repo)
        if code != 0:
            rows.append([agent["role"], branch, "branch-create-failed", err])
            continue

        task_file = board_dir / f"agent_{idx}_{role}.md"
        task_file.write_text(
            "\n".join([
                f"# Agent {idx}: {agent['role']}",
                "",
                f"Subtask: {agent['subtask']}",
                f"Base branch: {base_branch or 'main'}",
                f"Integration branch: {integration_branch}",
                "",
                "Budget caps:",
                "- Max files changed: 25",
                "- Max shell commands: 40",
                "- Max tokens: 120000",
                "- Max runtime (min): 20",
            ]),
            encoding="utf-8",
        )
        _run_git(["add", str(task_file.relative_to(repo))], repo)
        _run_git(["commit", "-m", f"chore(ai-agent): bootstrap {agent['role']} task"], repo)
        rows.append([agent["role"], branch, "ready", str(task_file.relative_to(repo))])
        backlog.append({"agent": agent["role"], "branch": branch, "status": "Backlog", "subtask": agent["subtask"]})

    board_file.write_text(json.dumps({"created": stamp, "integration_branch": integration_branch, "cards": backlog}, indent=2), encoding="utf-8")
    bus_file.write_text(json.dumps({"decisions": [], "constraints": [], "todos": []}, indent=2), encoding="utf-8")
    timeline_file.write_text(f"{datetime.now().isoformat()} started orchestration\n", encoding="utf-8")

    _run_git(["checkout", integration_branch], repo)
    return f"✅ Orchestration started for {len(rows)} agents.", integration_branch, rows


def run_quality_gates(repo_path: str, integration_branch: str) -> Tuple[str, List[List[str]]]:
    repo = Path((repo_path or ".").strip() or ".").resolve()
    if not (repo / ".git").exists():
        return "❌ Invalid repository path.", []

    _run_git(["checkout", integration_branch], repo)
    checks = [
        ("python compile", "python -m py_compile modules/ui_chat.py"),
        ("secrets scan", "git grep -nE '(ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{35})'"),
        ("unsafe shell", r"git grep -nE 'os\.system\(|subprocess\.Popen\(.*shell=True' -- '*.py'"),
    ]

    rows = []
    overall_ok = True
    for name, cmd in checks:
        proc = subprocess.run(["bash", "-lc", cmd], cwd=repo, text=True, capture_output=True)
        out = (proc.stdout or proc.stderr or "").strip()
        if name == "python compile":
            ok = proc.returncode == 0
        else:
            ok = proc.returncode != 0  # grep finds => failure
        overall_ok = overall_ok and ok
        rows.append([name, "pass" if ok else "fail", out[:400]])

    return ("✅ Quality gates passed." if overall_ok else "⚠️ Quality gates have failures."), rows


def synthesize_conflicts(repo_path: str, integration_branch: str, branch_csv: str) -> Tuple[str, str]:
    repo = Path((repo_path or ".").strip() or ".").resolve()
    if not (repo / ".git").exists():
        return "❌ Invalid repository path.", ""

    branches = [b.strip() for b in (branch_csv or "").split(",") if b.strip()]
    if not branches:
        return "❌ Provide branches list.", ""

    _run_git(["checkout", integration_branch], repo)
    conflicts = []
    merged = []
    for branch in branches:
        code, out, err = _run_git(["merge", "--no-ff", "--no-commit", branch], repo)
        if code != 0:
            ccode, cout, _ = _run_git(["diff", "--name-only", "--diff-filter=U"], repo)
            files = cout.splitlines() if ccode == 0 else []
            conflicts.append({"branch": branch, "files": files})
            _run_git(["merge", "--abort"], repo)
        else:
            _run_git(["commit", "-m", f"merge: {branch} into {integration_branch}"], repo)
            merged.append(branch)

    rationale = {
        "merged": merged,
        "conflicts": conflicts,
        "resolution_strategy": "Prefer integration-branch baseline; request manual/AI reviewer for conflicting files.",
    }
    rationale_path = _workspace_dir(repo) / f"conflict_rationale_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    rationale_path.write_text(json.dumps(rationale, indent=2), encoding="utf-8")
    msg = "✅ All branches merged cleanly." if not conflicts else f"⚠️ {len(conflicts)} branch(es) had conflicts."
    return msg, str(rationale_path)


def build_repo_map(repo_path: str) -> Tuple[str, List[List[str]]]:
    repo = Path((repo_path or ".").strip() or ".").resolve()
    if not (repo / ".git").exists():
        return "❌ Invalid repository path.", []

    files = []
    for path in repo.rglob("*.py"):
        if ".git" in path.parts or "installer_files" in path.parts:
            continue
        try:
            size = path.stat().st_size
            files.append((size, path.relative_to(repo).as_posix()))
        except Exception:
            pass

    files.sort(reverse=True)
    top = files[:80]
    rows = [[p, str(s)] for s, p in top]
    return f"✅ Repo map ready. Indexed {len(files)} python files.", rows


def issue_to_plan(issue_text: str, strategy: str) -> Tuple[str, str]:
    if not (issue_text or "").strip():
        return "❌ Issue text is required.", ""

    items = [x.strip("-• ") for x in issue_text.splitlines() if x.strip()]
    if not items:
        items = [issue_text.strip()]

    plan = [
        f"Strategy: {strategy}",
        "1) Clarify acceptance criteria.",
        "2) Build branch plan per subsystem.",
        "3) Implement + tests + docs.",
        "4) Run quality gates + synthesize PR.",
        "",
        "Issue decomposition:",
    ]
    for i, item in enumerate(items[:12], start=1):
        plan.append(f"- Task {i}: {item}")

    return "✅ Issue decomposed.", "\n".join(plan)


def pr_intelligence(repo_path: str, integration_branch: str) -> Tuple[str, str]:
    repo = Path((repo_path or ".").strip() or ".").resolve()
    if not (repo / ".git").exists():
        return "❌ Invalid repository path.", ""

    _run_git(["checkout", integration_branch], repo)
    _, diff_names, _ = _run_git(["diff", "--name-only", "main...HEAD"], repo)
    impacted = [x for x in diff_names.splitlines() if x]
    risk = min(100, len(impacted) * 6)
    report = {
        "risk_score": risk,
        "impacted_files": impacted[:200],
        "test_coverage_delta": "unknown (no coverage tool configured)",
        "rollback_plan": f"git checkout main && git branch -D {integration_branch} (if rejected)",
    }
    return "✅ PR intelligence generated.", json.dumps(report, indent=2)


def sync_branches_with_main(repo_path: str, branch_csv: str) -> Tuple[str, List[List[str]]]:
    repo = Path((repo_path or ".").strip() or ".").resolve()
    if not (repo / ".git").exists():
        return "❌ Invalid repository path.", []

    branches = [b.strip() for b in (branch_csv or "").split(",") if b.strip()]
    if not branches:
        return "❌ Provide branches list.", []

    _run_git(["fetch", "origin"], repo)
    rows = []
    for b in branches:
        _run_git(["checkout", b], repo)
        code, out, err = _run_git(["rebase", "main"], repo)
        if code != 0:
            _run_git(["rebase", "--abort"], repo)
            rows.append([b, "conflict", (err or out)[:240]])
        else:
            rows.append([b, "synced", "rebased onto main"])
    return "✅ Sync complete.", rows
