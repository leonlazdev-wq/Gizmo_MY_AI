import json
import subprocess
from datetime import datetime
from functools import partial
from pathlib import Path

import gradio as gr
from PIL import Image

from modules import chat, shared, ui, utils
from modules.chat_actions import MessageActions
from modules.chat_templates import (
    apply_template as apply_chat_template,
    create_custom_template,
    get_template_choices,
)
from modules.context_manager import ContextManager
from modules.ai_workspace import (
    build_repo_map,
    issue_to_plan,
    pr_intelligence,
    run_quality_gates,
    start_parallel_branches,
    synthesize_conflicts,
    sync_branches_with_main,
)
from modules.adaptive_ui import summarize_text, suggest_actions
from modules.audit import list_steps
from modules.html_generator import chat_html_wrapper
from modules.text_generation import stop_everything_event
from modules.utils import gradio

inputs = ('Chat input', 'interface_state')
reload_arr = ('history', 'name1', 'name2', 'mode', 'chat_style', 'character_menu')


LESSON_TAB_SYSTEM_PROMPT = '''SYSTEM PROMPT — Lesson-Tab AI
You are a lesson assistant agent. Primary goal: convert teacher instructions, class materials, or a student's request into short interactive lessons that support visual, auditory, and multilingual learners.

Capabilities you must offer:
- Receive text, or short structured requests (task: "teach X", "quiz me on Y", "annotate slide Z").
- Produce: (A) short lesson text (2–6 bullet points), (B) spoken audio (TTS), (C) visual aids (annotated images / small diagrams), (D) a short quiz (3–8 questions with answers).
- Support any language requested by the user; detect language automatically when not specified.
- When given permission, access linked classroom materials (Slides or Docs) and: summarize, extract learning objectives, produce slide-ready content, and generate Q&A for practice.
- Produce annotated images by combining an internet-found image or a generated placeholder and overlaying arrows/labels (e.g., "nucleus", "proton", "neutron"). When web images are used, cite the source metadata in a single short line.
- Provide a compact "export to slide" payload that maps lesson bullets → slide title + 2–3 bullets per slide.
- Offer accessibility options: adjustable speaking rate, closed captions, large-font images.

User controls:
- Microphone input: accept spoken questions and return spoken replies.
- Play button: plays the generated TTS audio.
- Visual icon: request a visual variant; when clicked produce annotated image(s) and an image thumbnail gallery.
- Language selector: override auto-detection.
- "Use classroom file" button: on approval, the agent will read Slides/Docs from the linked classroom account and produce a lesson draft.

Constraints & safety:
- Only read files explicitly authorized by the user.
- If the user asks for copyrighted text beyond short excerpts, summarize instead of verbatim quoting.
- If content appears to be dangerous or harmful, refuse and offer a safe alternative.

Output format (when asked to produce lesson content):
Return a JSON object with fields:
{
  "title": "string",
  "language": "ISO code",
  "bullets": ["..."],
  "tts_audio_url": "https://...",
  "images": [ {"thumb_url":"...","annotated_url":"...","source":"..."} ],
  "quiz": [ {"q":"...","choices":["..."],"answer_index":n} ],
  "slide_export": [ {"slide_title":"...","slide_bullets":["..."]} ]
}
'''


def apply_custom_ai_style(chat_input, style_enabled, style_prompt):
    if not style_enabled or not style_prompt or not style_prompt.strip():
        return chat_input

    updated_input = chat_input.copy()
    style_block = f"[Custom AI style instructions]\n{style_prompt.strip()}\n[/Custom AI style instructions]\n\n"
    updated_input['text'] = f"{style_block}{updated_input.get('text', '')}"
    return updated_input


def apply_lesson_tab_prompt():
    return True, LESSON_TAB_SYSTEM_PROMPT


MESSAGE_ACTIONS = MessageActions()
CONTEXT_MANAGER = ContextManager()


# ── GitHub Agent — config & persistence ─────────────────────────────────────

def _github_config_path():
    # Save to user_data (Drive-backed) so token survives Colab resets
    p = Path("user_data") / "github_agent.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_github_config():
    p = _github_config_path()
    if not p.exists():
        return {"repo_path": "/content/text-generation-webui", "base_branch": "main", "token": ""}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"repo_path": "/content/text-generation-webui", "base_branch": "main", "token": ""}


def _save_github_config(cfg):
    _github_config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _session_path(repo: Path):
    p = repo / "github_agent_tasks"
    p.mkdir(parents=True, exist_ok=True)
    return p / "session.json"


def _load_session(repo_path: str):
    try:
        p = _session_path(Path(repo_path).resolve())
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"log": [], "branches": []}


def _save_session(repo_path: str, session: dict):
    try:
        p = _session_path(Path(repo_path).resolve())
        p.write_text(json.dumps(session, indent=2), encoding="utf-8")
    except Exception:
        pass


def _session_add_log(session: dict, role: str, text: str) -> dict:
    import copy
    s = copy.deepcopy(session)
    s["log"].append({"role": role, "text": text, "time": datetime.now().strftime("%H:%M:%S")})
    return s


# ── GitHub Agent — git helpers ───────────────────────────────────────────────

def _run_git(args, cwd):
    proc = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _ensure_git_identity(repo: Path):
    rc, out, _ = _run_git(["config", "user.email"], repo)
    if rc != 0 or not out.strip():
        _run_git(["config", "user.email", "gizmo-agent@colab.local"], repo)
    rc, out, _ = _run_git(["config", "user.name"], repo)
    if rc != 0 or not out.strip():
        _run_git(["config", "user.name", "Gizmo Agent"], repo)


def _push_branch(repo: Path, branch: str):
    _ensure_git_identity(repo)
    code, out, err = _run_git(["push", "-u", "origin", branch], repo)
    return code, out, err


def _open_pr_gh(repo: Path, branch: str, title: str, body: str):
    gh_check = subprocess.run(["bash", "-lc", "command -v gh"], text=True, capture_output=True)
    if gh_check.returncode != 0:
        return None, f"✅ Branch '{branch}' pushed. Open PR manually on GitHub (gh CLI not installed)."
    cmd = ["gh", "pr", "create", "--title", title, "--body", body, "--head", branch]
    proc = subprocess.run(cmd, cwd=repo, text=True, capture_output=True)
    if proc.returncode != 0:
        return None, f"⚠️ gh CLI failed: {(proc.stderr or proc.stdout).strip()}"
    url = (proc.stdout or "").strip().splitlines()[-1] if (proc.stdout or "").strip() else ""
    return url, f"✅ PR created: {url}"


# ── GitHub Agent — render ────────────────────────────────────────────────────

def render_agent_chat_html(session: dict) -> str:
    log = session.get("log", [])
    if not log:
        return (
            "<div id='gh-chat-log' style='height:260px;overflow-y:auto;padding:10px;"
            "background:#0d0d1a;border-radius:8px;font-size:.87em'>"
            "<div style='color:#555;text-align:center;padding-top:80px'>No messages yet — "
            "connect a repo and start typing below 👇</div></div>"
        )
    colors = {"system": "#8ec8ff", "user": "#e0e0ff", "agent": "#7aff9a", "error": "#ff7a7a"}
    icons  = {"system": "⚙️", "user": "👤", "agent": "🤖", "error": "❌"}
    rows = []
    for m in log:
        role = m.get("role", "system")
        color = colors.get(role, "#ccc")
        icon  = icons.get(role, "•")
        time  = m.get("time", "")
        text  = m.get("text", "").replace("\n", "<br>")
        rows.append(
            f"<div style='margin-bottom:8px'>"
            f"<span style='color:{color};font-weight:600'>{icon} {role.title()}</span>"
            f"<span style='color:#555;font-size:.82em;margin-left:8px'>{time}</span>"
            f"<div style='margin-top:3px;color:#d0d0e8;padding-left:20px'>{text}</div></div>"
        )
    body = "".join(rows)
    return (
        f"<div id='gh-chat-log' style='height:260px;overflow-y:auto;padding:10px;"
        f"background:#0d0d1a;border-radius:8px;font-size:.87em'>{body}</div>"
        f"<script>var el=document.getElementById('gh-chat-log');if(el)el.scrollTop=el.scrollHeight;</script>"
    )


def render_branches_html(session: dict) -> str:
    branches = session.get("branches", [])
    if not branches:
        return "<div style='color:#555;font-size:.85em;padding:6px'>No active branches yet.</div>"
    status_colors = {"ready": "#7aff9a", "pushed": "#8ec8ff", "failed": "#ff7a7a", "merged": "#f39c12"}
    row_parts = []
    for b in branches:
        bstatus = b.get("status", "ready")
        bcolor = status_colors.get(bstatus, "#ccc")
        icon = "✅" if bstatus == "pushed" else "🔀" if bstatus == "merged" else "❌" if bstatus == "failed" else "🌿"
        row_parts.append(
            f"<tr>"
            f"<td style='padding:4px 8px;font-family:monospace;font-size:.82em;color:#8ec8ff'>{b.get('name','')}</td>"
            f"<td style='padding:4px 8px;color:#aaa'>{b.get('role','')}</td>"
            f"<td style='padding:4px 8px;color:#aaa'>{b.get('model','current')}</td>"
            f"<td style='padding:4px 8px;color:{bcolor}'>{icon} {bstatus}</td>"
            f"</tr>"
        )
    rows = "".join(row_parts)
    return (
        f"<table style='width:100%;border-collapse:collapse;font-size:.85em'>"
        f"<thead><tr style='color:#555;border-bottom:1px solid #2a2a4a'>"
        f"<th style='text-align:left;padding:4px 8px'>Branch</th>"
        f"<th style='text-align:left;padding:4px 8px'>Role</th>"
        f"<th style='text-align:left;padding:4px 8px'>Model</th>"
        f"<th style='text-align:left;padding:4px 8px'>Status</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def github_status_html(status, branch, pr_url):
    if not status:
        return "<div class='gh-status-bar gh-idle'>🔧 GitHub Agent — not connected</div>"
    color = "#2ecc71" if "✅" in status else "#e74c3c" if "❌" in status else "#f39c12"
    branch_pill = f"<span class='gh-branch-pill'>🌿 {branch}</span>" if branch else ""
    pr_link = f" <a href='{pr_url}' target='_blank' class='gh-pr-link'>View PR →</a>" if pr_url else ""
    return (
        f"<div class='gh-status-bar' style='border-left:3px solid {color}'>"
        f"{status}{branch_pill}{pr_link}</div>"
    )


# ── GitHub Agent — core actions ──────────────────────────────────────────────

def github_connect(repo_path, base_branch, token):
    cfg = {
        "repo_path": (repo_path or "/content/text-generation-webui").strip(),
        "base_branch": (base_branch or "main").strip() or "main",
        "token": (token or "").strip(),
    }
    repo = Path(cfg["repo_path"]).resolve()
    if not repo.exists() or not (repo / ".git").exists():
        return "❌ Invalid repository path (missing .git directory).", "", "{}", ""
    code, out, err = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    if code != 0:
        return f"❌ Git repo check failed: {err or out}", "", "{}", ""
    if cfg["token"]:
        rc, remote_url, _ = _run_git(["remote", "get-url", "origin"], repo)
        if rc == 0 and remote_url.startswith("https://") and "@" not in remote_url:
            authed_url = remote_url.replace("https://", f"https://{cfg['token']}@")
            _run_git(["remote", "set-url", "origin", authed_url], repo)
    _ensure_git_identity(repo)
    _save_github_config(cfg)
    session = _load_session(cfg["repo_path"])
    status_msg = f"✅ Connected to {repo} (branch: {out})"
    session = _session_add_log(session, "system", status_msg)
    _save_session(cfg["repo_path"], session)
    return status_msg, str(repo), json.dumps(session), render_agent_chat_html(session)


def github_agent_send(user_msg, session_json, repo_path):
    """Add a user message to the agent chat log."""
    if not (user_msg or "").strip():
        return session_json, render_agent_chat_html(json.loads(session_json or "{}"))
    try:
        session = json.loads(session_json or "{}")
    except Exception:
        session = {"log": [], "branches": []}
    session = _session_add_log(session, "user", user_msg.strip())
    _save_session(repo_path or ".", session)
    return json.dumps(session), render_agent_chat_html(session)


def github_create_branch(task_text, mode, reasoning_effort, repo_path, base_branch, session_json="{}"):
    repo = Path((repo_path or ".").strip() or ".").resolve()
    if not repo.exists() or not (repo / ".git").exists():
        return "❌ Invalid repository path.", "", "", session_json, render_agent_chat_html(json.loads(session_json or "{}"))
    if not (task_text or "").strip():
        return "❌ Task is required.", "", "", session_json, render_agent_chat_html(json.loads(session_json or "{}"))
    try:
        session = json.loads(session_json or "{}")
    except Exception:
        session = {"log": [], "branches": []}

    _ensure_git_identity(repo)
    branch = f"gizmo/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    _run_git(["checkout", base_branch or "main"], repo)
    code, out, err = _run_git(["checkout", "-b", branch], repo)
    if code != 0:
        msg = f"❌ Could not create branch: {err or out}"
        session = _session_add_log(session, "error", msg)
        return msg, "", "", json.dumps(session), render_agent_chat_html(session)

    tasks_dir = repo / "github_agent_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    task_file = tasks_dir / f"task_{stamp}.md"
    task_file.write_text(
        f"# GitHub Agent Task\n\n- Mode: {mode}\n- Reasoning effort: {reasoning_effort}\n- Branch: {branch}\n\n## Instruction\n{task_text}\n",
        encoding="utf-8",
    )
    rel_path = str(task_file.relative_to(repo))
    _run_git(["add", rel_path], repo)
    rc_staged, staged_out, _ = _run_git(["diff", "--cached", "--name-only"], repo)
    if not staged_out.strip():
        msg = f"❌ Nothing staged. Path: {rel_path}"
        session = _session_add_log(session, "error", msg)
        return msg, "", "", json.dumps(session), render_agent_chat_html(session)
    code, out, err = _run_git(["commit", "-m", f"chore: start github agent task ({branch})"], repo)
    if code != 0:
        msg = f"❌ Commit failed: {err or out}"
        session = _session_add_log(session, "error", msg)
        return msg, "", "", json.dumps(session), render_agent_chat_html(session)

    if "branches" not in session:
        session["branches"] = []
    session["branches"].append({"name": branch, "role": "single", "model": "current", "status": "ready"})
    status_msg = f"✅ Branch ready: {branch}"
    session = _session_add_log(session, "agent", status_msg)
    _save_session(str(repo), session)
    return status_msg, branch, str(task_file), json.dumps(session), render_agent_chat_html(session)


def github_open_pr(repo_path, branch, title, body, session_json="{}"):
    cfg = _load_github_config()
    repo = Path((repo_path or cfg.get("repo_path") or ".")).resolve()
    try:
        session = json.loads(session_json or "{}")
    except Exception:
        session = {"log": [], "branches": []}

    if not repo.exists() or not (repo / ".git").exists():
        msg = "❌ Invalid repository path."
        session = _session_add_log(session, "error", msg)
        return msg, "", json.dumps(session), render_agent_chat_html(session)
    if not branch:
        msg = "❌ Create a branch first."
        session = _session_add_log(session, "error", msg)
        return msg, "", json.dumps(session), render_agent_chat_html(session)

    _ensure_git_identity(repo)
    code, out, err = _run_git(["push", "-u", "origin", branch], repo)
    if code != 0:
        msg = f"❌ Push failed: {err or out}\n\nTip: Check your GitHub token in Connect."
        session = _session_add_log(session, "error", msg)
        return msg, "", json.dumps(session), render_agent_chat_html(session)

    for b in session.get("branches", []):
        if b.get("name") == branch:
            b["status"] = "pushed"

    pr_url, pr_msg = _open_pr_gh(repo, branch, title or f"AI: {branch}", body or "Automated PR by Gizmo GitHub Agent")
    session = _session_add_log(session, "agent", pr_msg)
    _save_session(str(repo), session)
    return pr_msg, pr_url or "", json.dumps(session), render_agent_chat_html(session)


def github_launch_multi_agent(task, selected_roles, model_override, repo_path, base_branch, session_json="{}"):
    """Create one branch per selected agent role, all from the same base branch."""
    repo = Path((repo_path or ".").strip() or ".").resolve()
    try:
        session = json.loads(session_json or "{}")
    except Exception:
        session = {"log": [], "branches": []}

    if not repo.exists() or not (repo / ".git").exists():
        msg = "❌ Invalid repository path."
        session = _session_add_log(session, "error", msg)
        return msg, "{}", render_agent_chat_html(session), render_branches_html(session)
    if not (task or "").strip():
        msg = "❌ Task is required."
        session = _session_add_log(session, "error", msg)
        return msg, session_json, render_agent_chat_html(session), render_branches_html(session)
    if not selected_roles:
        msg = "❌ Select at least one agent role."
        session = _session_add_log(session, "error", msg)
        return msg, session_json, render_agent_chat_html(session), render_branches_html(session)

    _ensure_git_identity(repo)
    model_name = (model_override or "").strip() or "current model"
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    tasks_dir = repo / "github_agent_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    if "branches" not in session:
        session["branches"] = []

    launched = []
    failed = []
    for role in selected_roles:
        role_slug = role.lower().replace(" ", "-")
        branch = f"gizmo/{role_slug}-{stamp}"
        _run_git(["checkout", base_branch or "main"], repo)
        code, out, err = _run_git(["checkout", "-b", branch], repo)
        if code != 0:
            failed.append(role)
            session = _session_add_log(session, "error", f"❌ Branch failed for {role}: {err or out}")
            continue

        task_file = tasks_dir / f"task_{role_slug}_{stamp}.md"
        task_file.write_text(
            f"# Agent Task — {role}\n\n"
            f"- Role: {role}\n"
            f"- Assigned model: {model_name}\n"
            f"- Branch: {branch}\n"
            f"- Base: {base_branch or 'main'}\n\n"
            f"## Role Instructions\n"
            f"You are the **{role}** agent. Focus only on the {role.lower()} aspect of this task.\n\n"
            f"## Task\n{task.strip()}\n",
            encoding="utf-8",
        )
        rel_path = str(task_file.relative_to(repo))
        _run_git(["add", rel_path], repo)
        rc2, staged, _ = _run_git(["diff", "--cached", "--name-only"], repo)
        if not staged.strip():
            failed.append(role)
            session = _session_add_log(session, "error", f"❌ Nothing staged for {role}")
            continue
        rc3, _, cerr = _run_git(["commit", "-m", f"chore(ai-agent): launch {role} agent ({branch})"], repo)
        if rc3 != 0:
            failed.append(role)
            session = _session_add_log(session, "error", f"❌ Commit failed for {role}: {cerr}")
            continue

        session["branches"].append({"name": branch, "role": role, "model": model_name, "status": "ready"})
        launched.append(branch)
        session = _session_add_log(session, "agent", f"🌿 [{role}] Branch ready: `{branch}` — assigned to {model_name}")

    if launched:
        summary = f"✅ Launched {len(launched)} agent(s): {', '.join(selected_roles if not failed else [r for r in selected_roles if r not in failed])}"
        if failed:
            summary += f" | ❌ Failed: {', '.join(failed)}"
        session = _session_add_log(session, "system", summary)
    else:
        summary = f"❌ All agents failed. Check repo connection."

    _save_session(str(repo), session)
    return summary, json.dumps(session), render_agent_chat_html(session), render_branches_html(session)


def github_merge_all_pr(repo_path, base_branch, pr_title, session_json="{}"):
    """Push all ready branches and create a single merge PR into base branch."""
    cfg = _load_github_config()
    repo = Path((repo_path or cfg.get("repo_path") or ".")).resolve()
    try:
        session = json.loads(session_json or "{}")
    except Exception:
        session = {"log": [], "branches": []}

    if not repo.exists() or not (repo / ".git").exists():
        msg = "❌ Invalid repository path."
        session = _session_add_log(session, "error", msg)
        return msg, "", json.dumps(session), render_agent_chat_html(session), render_branches_html(session)

    branches = [b for b in session.get("branches", []) if b.get("status") in ("ready", "pushed")]
    if not branches:
        msg = "❌ No active branches to merge. Launch agents first."
        session = _session_add_log(session, "error", msg)
        return msg, "", json.dumps(session), render_agent_chat_html(session), render_branches_html(session)

    _ensure_git_identity(repo)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    merge_branch = f"gizmo/merge-all-{stamp}"

    # Create integration branch from base
    _run_git(["checkout", base_branch or "main"], repo)
    code, out, err = _run_git(["checkout", "-b", merge_branch], repo)
    if code != 0:
        msg = f"❌ Could not create merge branch: {err or out}"
        session = _session_add_log(session, "error", msg)
        return msg, "", json.dumps(session), render_agent_chat_html(session), render_branches_html(session)

    session = _session_add_log(session, "system", f"🔀 Created merge branch: `{merge_branch}`")

    push_results = []
    for b in branches:
        branch_name = b.get("name", "")
        # Push each agent branch first
        _run_git(["checkout", branch_name], repo)
        rc, out, err = _run_git(["push", "-u", "origin", branch_name], repo)
        if rc == 0:
            b["status"] = "pushed"
            push_results.append(branch_name)
            session = _session_add_log(session, "agent", f"⬆️ Pushed: `{branch_name}`")
        else:
            session = _session_add_log(session, "error", f"❌ Push failed for `{branch_name}`: {err or out}")

    # Switch back to merge branch and merge all pushed branches
    _run_git(["checkout", merge_branch], repo)
    merge_ok = []
    for branch_name in push_results:
        rc, out, err = _run_git(["merge", "--no-ff", branch_name, "-m", f"merge: {branch_name} into {merge_branch}"], repo)
        if rc == 0:
            merge_ok.append(branch_name)
            for b in session["branches"]:
                if b.get("name") == branch_name:
                    b["status"] = "merged"
        else:
            _run_git(["merge", "--abort"], repo)
            session = _session_add_log(session, "error", f"⚠️ Merge conflict in `{branch_name}` — skipped")

    # Push merge branch
    rc, out, err = _run_git(["push", "-u", "origin", merge_branch], repo)
    if rc != 0:
        msg = f"❌ Push of merge branch failed: {err or out}"
        session = _session_add_log(session, "error", msg)
        _save_session(str(repo), session)
        return msg, "", json.dumps(session), render_agent_chat_html(session), render_branches_html(session)

    # Create the PR
    branch_list = "\n".join(f"- `{b}`" for b in merge_ok)
    body = f"## Multi-agent merge PR\n\nMerges {len(merge_ok)} agent branch(es) into `{base_branch or 'main'}`:\n\n{branch_list}\n\nGenerated by Gizmo GitHub Agent."
    pr_url, pr_msg = _open_pr_gh(repo, merge_branch, pr_title or f"AI: merge {len(merge_ok)} agents → {base_branch or 'main'}", body)
    session = _session_add_log(session, "agent", f"🎉 {pr_msg}")
    _save_session(str(repo), session)
    final_msg = f"✅ Merge PR created from {len(merge_ok)} branch(es)." if pr_url else pr_msg
    return final_msg, pr_url or "", json.dumps(session), render_agent_chat_html(session), render_branches_html(session)


def github_send_to_chat(gh_status, gh_branch, gh_task, gh_pr_url):
    lines = ["🔧 **GitHub Agent Update**"]
    if gh_status:
        lines.append(f"**Status:** {gh_status}")
    if gh_branch:
        lines.append(f"**Branch:** `{gh_branch}`")
    if gh_task and gh_task.strip():
        lines.append(f"**Task:**\n{gh_task.strip()}")
    if gh_pr_url:
        lines.append(f"**PR URL:** {gh_pr_url}")
    return {"text": "\n".join(lines), "files": []}



def refresh_template_choices(category):
    return gr.update(choices=get_template_choices(category), value=None)


def apply_selected_template(template_key, history):
    return apply_chat_template(template_key, history)


def create_template_and_refresh(name, description, system_prompt, category, icon, current_category):
    status = create_custom_template(name, description, system_prompt, category, icon)
    return status, gr.update(choices=get_template_choices(current_category or 'All'), value=None)


def analyze_context(history):
    analysis = CONTEXT_MANAGER.analyze_context(history)
    html = CONTEXT_MANAGER.render_context_html(analysis)
    return html, f"ℹ️ Total tokens: {analysis['total_tokens']} | Remaining: {analysis['remaining_tokens']}"


def edit_message_action(history, msg_index, new_content):
    return MESSAGE_ACTIONS.edit_message(history, int(msg_index), new_content)


def branch_conversation_action(history, branch_point):
    return MESSAGE_ACTIONS.branch_conversation(history, int(branch_point))


def save_snippet_action(history, msg_index, category):
    return MESSAGE_ACTIONS.save_snippet(history, int(msg_index), category)


def export_conversation_action(history, start_idx, end_idx, export_format):
    return MESSAGE_ACTIONS.export_selection(history, int(start_idx), int(end_idx), export_format)


def pin_message_action(history, msg_index):
    return CONTEXT_MANAGER.pin_message(history, int(msg_index))


def prune_context_action(history):
    return CONTEXT_MANAGER.smart_prune(history)


def build_summary_prompt(history):
    visible = history.get('visible', [])
    if not visible:
        return '❌ No conversation to summarize'

    lines = []
    for user_msg, bot_msg in visible[-12:]:
        lines.append(f'User: {user_msg}')
        lines.append(f'Assistant: {bot_msg}')

    return 'Summarize this conversation in 2-3 concise bullet points:\n\n' + '\n'.join(lines)




def create_ui():
    mu = shared.args.multi_user

    shared.gradio['Chat input'] = gr.State()
    shared.gradio['history'] = gr.State({'internal': [], 'visible': [], 'metadata': {}})
    shared.gradio['display'] = gr.JSON(value={}, visible=False)  # Hidden buffer

    with gr.Tab('Chat', elem_id='chat-tab'):
        with gr.Row(elem_id='past-chats-row', elem_classes=['pretty_scrollbar']):
            with gr.Column():
                with gr.Row(elem_id='past-chats-buttons'):
                    shared.gradio['branch_chat'] = gr.Button('Branch', elem_classes=['refresh-button', 'refresh-button-medium'], elem_id='Branch', interactive=not mu)
                    shared.gradio['rename_chat'] = gr.Button('Rename', elem_classes=['refresh-button', 'refresh-button-medium'], interactive=not mu)
                    shared.gradio['delete_chat'] = gr.Button('🗑️', visible=False, elem_classes='refresh-button', interactive=not mu, elem_id='delete_chat')
                    shared.gradio['Start new chat'] = gr.Button('New chat', elem_classes=['refresh-button', 'refresh-button-medium', 'focus-on-chat-input'])
                    shared.gradio['branch_index'] = gr.Number(value=-1, precision=0, visible=False, elem_id="Branch-index", interactive=True)

                shared.gradio['search_chat'] = gr.Textbox(placeholder='Search chats...', max_lines=1, elem_id='search_chat')

                with gr.Row(elem_id='delete-chat-row', visible=False) as shared.gradio['delete-chat-row']:
                    shared.gradio['delete_chat-cancel'] = gr.Button('Cancel', elem_classes=['refresh-button', 'focus-on-chat-input'], elem_id='delete_chat-cancel')
                    shared.gradio['delete_chat-confirm'] = gr.Button('Confirm', variant='stop', elem_classes=['refresh-button', 'focus-on-chat-input'], elem_id='delete_chat-confirm')

                with gr.Row(elem_id='rename-row', visible=False) as shared.gradio['rename-row']:
                    shared.gradio['rename_to'] = gr.Textbox(label='Rename to:', placeholder='New name', elem_classes=['no-background'])
                    with gr.Row():
                        shared.gradio['rename_to-cancel'] = gr.Button('Cancel', elem_classes=['refresh-button', 'focus-on-chat-input'])
                        shared.gradio['rename_to-confirm'] = gr.Button('Confirm', elem_classes=['refresh-button', 'focus-on-chat-input'], variant='primary')

                with gr.Row():
                    shared.gradio['unique_id'] = gr.Radio(label="", elem_classes=['slim-dropdown', 'pretty_scrollbar'], interactive=not mu, elem_id='past-chats')

        with gr.Row():
            with gr.Column(elem_id='chat-col'):
                shared.gradio['html_display'] = gr.HTML(value=chat_html_wrapper({'internal': [], 'visible': [], 'metadata': {}}, '', '', 'chat', 'cai-chat', '')['html'], visible=True)

                # ── GitHub Agent full panel ───────────────────────────────────
                with gr.Row(visible=False, elem_id='gh-main-panel-row') as shared.gradio['gh_panel_row']:
                    with gr.Column(elem_id='gh-main-panel'):
                        gr.HTML("""/* add to a style block in the UI file */
.ui-chat-textarea textarea, .ui-chat-textarea input, textarea#chat-input {
    border-radius: 12px !important;
    box-shadow: 0 12px 32px rgba(0,0,0,0.45) !important;
    min-height: 180px !important;
    max-height: 420px !important;
    padding: 14px !important;
    font-size: 15px !important;
    line-height: 1.45 !important;
    background: linear-gradient(180deg,#1b1f22 0%,#151719 100%) !important;
    color: #e6eef6 !important;
    border: 1px solid rgba(255,255,255,0.035) !important;
    resize: vertical !important;
}

.ui-chat-textarea textarea:focus, textarea#chat-input:focus {
    outline: none !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 18px 40px rgba(0,0,0,0.6), 0 0 0 4px rgba(80,140,255,0.04) !important;
    border-color: rgba(80,140,255,0.2) !important;
}

/* styling for relocated Git button */
.moved-git-btn {
    margin-right: 8px;
    border-radius: 10px;
    padding: 6px 10px;
    font-weight: 600;
    box-shadow: 0 8px 22px rgba(0,0,0,0.35);
    background: linear-gradient(180deg,#2a2c31,#171819);
    color: #e6eef6;
    border: 1px solid rgba(255,255,255,0.03);
    cursor: pointer;
}""")

                        # Session state (JSON blob)
                        shared.gradio['gh_session'] = gr.State("{}")
                        # Visibility state for toggle button
                        shared.gradio['gh_panel_visible'] = gr.State(False)

                        with gr.Row():
                            # Left col: chat log + input
                            with gr.Column(scale=3, min_width=280):
                                gr.HTML("<div class='gh-section-title'>💬 Agent Chat</div>")
                                shared.gradio['gh_chat_html'] = gr.HTML(
                                    value=render_agent_chat_html({"log": [], "branches": []}),
                                    elem_id='gh-chat-html',
                                )
                                with gr.Row():
                                    shared.gradio['gh_msg_input'] = gr.Textbox(
                                        label='', placeholder='Type a message or task…',
                                        show_label=False, scale=5,
                                        elem_id='gh-msg-input',
                                    )
                                    shared.gradio['gh_msg_send_btn'] = gr.Button('Send', scale=1, size='sm', variant='primary')
                                gr.HTML("<div class='gh-section-title'>📝 Task for agents</div>")
                                shared.gradio['gh_task_panel'] = gr.Textbox(
                                    label='', lines=3, show_label=False,
                                    placeholder='Describe the code change — each selected agent will get their own branch with this task…',
                                    elem_id='gh-task-panel',
                                )
                                shared.gradio['gh_pr_title_panel'] = gr.Textbox(
                                    label='PR title', value='AI: multi-agent change',
                                )

                            # Right col: model + roles + branches
                            with gr.Column(scale=2, min_width=220):
                                gr.HTML("<div class='gh-section-title'>🤖 Models & Agents</div>")
                                shared.gradio['gh_model_override'] = gr.Textbox(
                                    label='Model name (leave blank = current)',
                                    placeholder='e.g. Qwen2.5-Coder-14B',
                                )
                                shared.gradio['gh_agent_roles'] = gr.CheckboxGroup(
                                    label='Agent roles (one branch each)',
                                    choices=['Planner', 'Coder', 'Reviewer', 'Tester', 'Security', 'Docs'],
                                    value=['Coder'],
                                )
                                gr.HTML("<hr class='gh-divider'><div class='gh-section-title'>🌿 Active Branches</div>")
                                shared.gradio['gh_branches_html'] = gr.HTML(
                                    value=render_branches_html({"branches": []}),
                                    elem_id='gh-branches-html',
                                )

                        # Action buttons row
                        with gr.Row():
                            shared.gradio['gh_launch_btn'] = gr.Button('🚀 Launch Agents', variant='primary', size='sm')
                            shared.gradio['gh_single_branch_btn'] = gr.Button('🌿 Single Branch', size='sm')
                            shared.gradio['gh_merge_pr_btn'] = gr.Button('🔀 Merge All → PR', size='sm', variant='secondary')
                            shared.gradio['gh_panel_send_btn'] = gr.Button('💬 Send to Chat', size='sm')
                            shared.gradio['gh_panel_close_btn'] = gr.Button('✕ Close', size='sm')

                        shared.gradio['gh_panel_status'] = gr.HTML(
                            value="<div class='gh-status-bar gh-idle'>Connect in the sidebar (🔧 GitHub Agent) then use this panel.</div>",
                        )

                    with gr.Column(scale=10, elem_id='chat-input-container'):
                        # prettier, larger chat input
                        shared.gradio['textbox'] = gr.Textbox(
                            label='',
                            placeholder='Send a message...',
                            lines=8,
                            interactive=True,
                            elem_id='chat-input',
                            elem_classes=['add_scrollbar', 'ui-chat-textarea'],
                        )

                        # typing indicator
                        shared.gradio['typing-dots'] = gr.HTML(
                            value='<div id="typing-dots"><span class="dot dot1"></span><span class="dot dot2"></span><span class="dot dot3"></span></div>',
                            label='typing',
                            elem_id='typing-container'
                        )

                        # Git toggle button and connector menu
                        shared.gradio['gh_toggle_btn'] = gr.Button('🔧 Git', elem_id='gh-toggle-btn', size='sm', elem_classes=['moved-git-btn'])
                        shared.gradio['connector-plus-html'] = gr.HTML(value='''<div id='connector-plus'>
  <details>
    <summary title="Connectors">+</summary>
    <div class="connector-menu-panel">
      <div class="connector-menu-title">Connectors</div>
      <a href="https://github.com/settings/tokens" target="_blank" rel="noopener noreferrer">GitHub <span>Repos, issues, PR tools</span></a>
      <a href="https://developers.google.com/docs/api/quickstart/python" target="_blank" rel="noopener noreferrer">Google Docs <span>Read/write docs</span></a>
      <a href="https://developers.google.com/slides/api/quickstart/python" target="_blank" rel="noopener noreferrer">Google Slides <span>Create/update slides</span></a>
      <a href="https://developers.google.com/drive/api/quickstart/python" target="_blank" rel="noopener noreferrer">Google Drive <span>Files and folders</span></a>
      <a href="https://www.notion.so/my-integrations" target="_blank" rel="noopener noreferrer">Notion <span>Pages and databases</span></a>
      <a href="https://api.slack.com/apps" target="_blank" rel="noopener noreferrer">Slack <span>Channels and bots</span></a>
      <a href="https://developer.atlassian.com/cloud/jira/platform/getting-started/" target="_blank" rel="noopener noreferrer">Jira <span>Projects and tickets</span></a>
      <a href="https://www.figma.com/developers/api" target="_blank" rel="noopener noreferrer">Figma <span>Design files and comments</span></a>
      <a href="https://developer.atlassian.com/cloud/confluence/getting-started/" target="_blank" rel="noopener noreferrer">Confluence/Docs <span>Team knowledge bases</span></a>
      <a href="#" onclick="window.gizmoGoToTab && window.gizmoGoToTab('🛠 Toolbar'); return false;">Gizmo Toolbar <span>Manage style and connector status</span></a>
    </div>
  </details>
</div>
''', elem_id='connector-plus-html')

                    with gr.Column(scale=1, elem_id='generate-stop-container'):
                        with gr.Row():
                            shared.gradio['Stop'] = gr.Button('Stop', elem_id='stop', visible=False)
                            shared.gradio['Generate'] = gr.Button('Send', elem_id='Generate', variant='primary')
                        


        # Hover menu buttons
        with gr.Column(elem_id='chat-buttons'):
            shared.gradio['Regenerate'] = gr.Button('Regenerate (Ctrl + Enter)', elem_id='Regenerate')
            shared.gradio['Continue'] = gr.Button('Continue (Alt + Enter)', elem_id='Continue')
            shared.gradio['Remove last'] = gr.Button('Remove last reply (Ctrl + Shift + Backspace)', elem_id='Remove-last')
            shared.gradio['Impersonate'] = gr.Button('Impersonate (Ctrl + Shift + M)', elem_id='Impersonate')
            shared.gradio['Send dummy message'] = gr.Button('Send dummy message')
            shared.gradio['Send dummy reply'] = gr.Button('Send dummy reply')
            shared.gradio['send-chat-to-notebook'] = gr.Button('Send to Notebook')
            shared.gradio['show_controls'] = gr.Checkbox(value=shared.settings['show_controls'], label='Show controls (Ctrl+S)', elem_id='show-controls')

        with gr.Row(elem_id='adaptive-toolbar', visible=False):
            # Visual mock: ✂️ Summarize | 📝 Action items | 🐞 Find bugs | 📎 Create task
            shared.gradio['adaptive_text'] = gr.Textbox(label='Adaptive input', lines=2)
            shared.gradio['adaptive_summarize_btn'] = gr.Button('✂️ Summarize', elem_id='adaptive-summarize')
            shared.gradio['adaptive_actions_btn'] = gr.Button('📝 Action items')
            shared.gradio['adaptive_bugs_btn'] = gr.Button('🐞 Find bugs')
            shared.gradio['adaptive_task_btn'] = gr.Button('📎 Create task')
            shared.gradio['adaptive_output'] = gr.Textbox(label='Adaptive output', lines=4)
            shared.gradio['provenance_btn'] = gr.Button('🕒 Provenance')
            shared.gradio['provenance_output'] = gr.JSON(label='Provenance timeline')

        with gr.Row(elem_id='chat-controls', elem_classes=['pretty_scrollbar']):
            with gr.Column():
                with gr.Row():
                    shared.gradio['start_with'] = gr.Textbox(label='Start reply with', placeholder='Sure thing!', value=shared.settings['start_with'], elem_classes=['add_scrollbar'])

                with gr.Accordion('Prompt style (local)', open=False):
                    shared.gradio['custom_style_enabled'] = gr.Checkbox(value=False, label='Enable local style snippet')
                    shared.gradio['custom_style_prompt'] = gr.Textbox(
                        label='How the AI should behave',
                        lines=4,
                        placeholder='Example: concise, include next steps.',
                        elem_classes=['add_scrollbar']
                    )
                    shared.gradio['apply_lesson_tab_prompt'] = gr.Button('Use Lesson-Tab AI system prompt', elem_classes=['refresh-button'])

                # Minimal optional footer replacing old Google/custom-style footer bar
                shared.gradio['minimal_footer_html'] = gr.Markdown("<div id='minimal-footer'>Gizmo • privacy-first • optional integrations</div>")

                gr.HTML("<div class='sidebar-vertical-separator'></div>")

                shared.gradio['reasoning_effort'] = gr.Dropdown(value=shared.settings['reasoning_effort'], choices=['low', 'medium', 'high'], label='Reasoning effort', info='Used by GPT-OSS.')
                shared.gradio['enable_thinking'] = gr.Checkbox(value=shared.settings['enable_thinking'], label='Enable thinking', info='Used by Seed-OSS and pre-2507 Qwen3.')

                gr.HTML("<div class='sidebar-vertical-separator'></div>")

                shared.gradio['enable_web_search'] = gr.Checkbox(value=shared.settings.get('enable_web_search', False), label='Activate web search', elem_id='web-search')
                with gr.Row(visible=shared.settings.get('enable_web_search', False)) as shared.gradio['web_search_row']:
                    shared.gradio['web_search_pages'] = gr.Number(value=shared.settings.get('web_search_pages', 3), precision=0, label='Number of pages to download', minimum=1, maximum=10)

                gr.HTML("<div class='sidebar-vertical-separator'></div>")

                with gr.Row():
                    shared.gradio['mode'] = gr.Radio(choices=['instruct', 'chat-instruct', 'chat'], value=None, label='Mode', info='In instruct and chat-instruct modes, the template under Parameters > Instruction template is used.', elem_id='chat-mode')

                with gr.Row():
                    shared.gradio['chat_style'] = gr.Dropdown(choices=utils.get_available_chat_styles(), label='Chat style', value=shared.settings['chat_style'], visible=shared.settings['mode'] != 'instruct')

                with gr.Row():
                    shared.gradio['chat-instruct_command'] = gr.Textbox(value=shared.settings['chat-instruct_command'], lines=12, label='Command for chat-instruct mode', info='<|character|> and <|prompt|> get replaced with the bot name and the regular chat prompt respectively.', visible=shared.settings['mode'] == 'chat-instruct', elem_classes=['add_scrollbar'])

                with gr.Accordion('🔧 GitHub Agent', open=False, elem_id='gh-sidebar-accordion'):
                    gr.HTML("""<style>
                    .gh-step-label{font-size:.75em;font-weight:700;letter-spacing:.08em;
                        color:#8ec8ff;text-transform:uppercase;margin-bottom:4px;margin-top:8px}
                    .gh-status-bar{padding:8px 12px;border-radius:8px;font-size:.88em;
                        background:#1a1a2e;border-left:3px solid #555;margin:6px 0;line-height:1.5}
                    .gh-idle{color:#888}
                    .gh-branch-pill{background:#1e3a5f;color:#8ec8ff;border-radius:12px;
                        padding:2px 8px;font-size:.82em;margin-left:8px;font-family:monospace}
                    .gh-pr-link{color:#8ec8ff;text-decoration:underline;margin-left:6px}
                    .gh-divider{border:none;border-top:1px solid #2a2a3e;margin:10px 0}
                    </style>""")
                    gh_defaults = _load_github_config()
                    gr.HTML("<div class='gh-step-label'>① Connect your repo</div>")
                    shared.gradio['gh_repo_path'] = gr.Textbox(
                        label='Repository path',
                        value=gh_defaults.get('repo_path', '/content/text-generation-webui'),
                        placeholder='/content/text-generation-webui',
                    )
                    with gr.Row():
                        shared.gradio['gh_base_branch'] = gr.Textbox(
                            label='Base branch', value=gh_defaults.get('base_branch', 'main'), scale=1,
                        )
                        shared.gradio['gh_token'] = gr.Textbox(
                            label='GitHub token', type='password',
                            value=gh_defaults.get('token', ''), placeholder='ghp_...', scale=2,
                        )
                    shared.gradio['gh_connect_btn'] = gr.Button('🔌 Connect Repo', variant='primary', size='sm')
                    gr.HTML("<hr class='gh-divider'>")
                    shared.gradio['gh_status_html'] = gr.HTML(
                        value="<div class='gh-status-bar gh-idle'>Not connected — fill in path + token above</div>",
                    )
                    # Hidden state fields used by event handlers
                    shared.gradio['gh_status'] = gr.Textbox(interactive=False, visible=False)
                    shared.gradio['gh_branch'] = gr.Textbox(interactive=False, visible=False)
                    shared.gradio['gh_task_file'] = gr.Textbox(interactive=False, visible=False)
                    shared.gradio['gh_pr_url'] = gr.Textbox(interactive=False, visible=False)
                    shared.gradio['gh_branch_display'] = gr.Textbox(interactive=False, visible=False)
                    shared.gradio['gh_pr_url_display'] = gr.Textbox(interactive=False, visible=False)
                    gr.HTML("<div style='font-size:.8em;color:#555;margin-top:6px'>After connecting, click <b>🔧 Git</b> button below the chat to open the full agent panel.</div>")

                gr.HTML("<div class='sidebar-vertical-separator'></div>")

                gr.HTML(
                    "<div style='padding:6px 0'>"
                    "<a href='https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab/blob/main/README.md#tutorials' "
                    "target='_blank' rel='noopener noreferrer' "
                    "style='font-size:.88em;color:#8ec8ff;text-decoration:none'>"
                    "📖 Tutorial &amp; Documentation</a>"
                    "</div>"
                )

                gr.HTML("<div class='sidebar-vertical-separator'></div>")

                with gr.Row():
                    shared.gradio['count_tokens'] = gr.Button('Count tokens', size='sm', visible=False)

                shared.gradio['token_display'] = gr.HTML(value='', elem_classes='token-display', visible=False)

                gr.HTML("<div class='sidebar-vertical-separator'></div>")
                gr.Markdown('### 📚 Chat Templates')
                shared.gradio['template_category'] = gr.Dropdown(
                    choices=['All', 'Programming', 'Creative', 'Academic', 'Business', 'Other'],
                    value='All',
                    label='Category'
                )
                shared.gradio['template_list'] = gr.Radio(
                    choices=get_template_choices('All'),
                    value=None,
                    label='Select Template'
                )
                with gr.Row():
                    shared.gradio['apply_template_btn'] = gr.Button('✨ Apply Template', variant='primary')
                    shared.gradio['template_status'] = gr.Textbox(label='Template Status', interactive=False)

                with gr.Accordion('➕ Create Custom Template', open=False):
                    shared.gradio['custom_template_name'] = gr.Textbox(label='Template Name')
                    shared.gradio['custom_template_desc'] = gr.Textbox(label='Description', lines=2)
                    shared.gradio['custom_template_prompt'] = gr.Textbox(label='System Prompt', lines=4)
                    shared.gradio['custom_template_category'] = gr.Dropdown(
                        choices=['Programming', 'Creative', 'Academic', 'Business', 'Other'],
                        value='Other',
                        label='Category'
                    )
                    shared.gradio['custom_template_icon'] = gr.Textbox(label='Icon (emoji)', value='💬')
                    shared.gradio['create_template_btn'] = gr.Button('Create Template')

                gr.HTML("<div class='sidebar-vertical-separator'></div>")
                gr.Markdown('### ⚡ Message Actions')
                shared.gradio['message_index'] = gr.Number(label='Message Index', value=0, precision=0)
                with gr.Accordion('📝 Edit Message', open=False):
                    shared.gradio['edit_message_new_content'] = gr.Textbox(label='New Content', lines=3)
                    shared.gradio['edit_message_btn'] = gr.Button('✏️ Edit')
                with gr.Accordion('🌿 Branch Conversation', open=False):
                    shared.gradio['branch_point'] = gr.Number(label='Branch from message', value=0, precision=0)
                    shared.gradio['branch_conversation_btn'] = gr.Button('🌿 Create Branch')
                with gr.Accordion('💾 Save Snippet', open=False):
                    shared.gradio['snippet_category'] = gr.Dropdown(
                        choices=['Code', 'Writing', 'Research', 'General'],
                        value='General',
                        label='Category'
                    )
                    shared.gradio['save_snippet_btn'] = gr.Button('💾 Save')
                with gr.Accordion('📤 Export Conversation', open=False):
                    shared.gradio['export_start'] = gr.Number(label='From message', value=0, precision=0)
                    shared.gradio['export_end'] = gr.Number(label='To message', value=-1, precision=0)
                    shared.gradio['export_format'] = gr.Radio(
                        choices=['markdown', 'json', 'txt'],
                        value='markdown',
                        label='Format'
                    )
                    shared.gradio['export_btn'] = gr.Button('📤 Export')

                gr.HTML("<div class='sidebar-vertical-separator'></div>")
                gr.Markdown('### 🧠 Context Manager')
                shared.gradio['context_token_display'] = gr.HTML(
                    "<div style='text-align:center'><div style='font-size:24px;font-weight:bold'>0 / 4096</div>"
                    "<div style='font-size:12px;color:#888'>tokens used</div></div>"
                )
                with gr.Row():
                    shared.gradio['refresh_context_btn'] = gr.Button('🔄 Refresh Context Info')
                    shared.gradio['prune_context_btn'] = gr.Button('✂️ Auto-Prune')
                shared.gradio['pin_message_index'] = gr.Number(label='Message to pin', value=0, precision=0)
                with gr.Row():
                    shared.gradio['pin_message_btn'] = gr.Button('📌 Pin Message')
                    shared.gradio['summarize_conversation_btn'] = gr.Button('📝 Summarize')
                shared.gradio['context_status'] = gr.Textbox(label='Action/Context Status', interactive=False)

        # Hidden elements for version navigation and editing
        with gr.Row(visible=False):
            shared.gradio['navigate_message_index'] = gr.Number(value=-1, precision=0, elem_id="Navigate-message-index")
            shared.gradio['navigate_direction'] = gr.Textbox(value="", elem_id="Navigate-direction")
            shared.gradio['navigate_message_role'] = gr.Textbox(value="", elem_id="Navigate-message-role")
            shared.gradio['navigate_version'] = gr.Button(elem_id="Navigate-version")
            shared.gradio['edit_message_index'] = gr.Number(value=-1, precision=0, elem_id="Edit-message-index")
            shared.gradio['edit_message_text'] = gr.Textbox(value="", elem_id="Edit-message-text")
            shared.gradio['edit_message_role'] = gr.Textbox(value="", elem_id="Edit-message-role")
            shared.gradio['edit_message'] = gr.Button(elem_id="Edit-message")

        # Chat Folders and Export panels — rendered inside the Chat tab
        from modules import ui_chat_folders, ui_chat_export
        ui_chat_folders.create_ui()
        ui_chat_export.create_ui()


def create_character_settings_ui():
    mu = shared.args.multi_user
    with gr.Tab('Character', elem_id="character-tab"):
        with gr.Row():
            with gr.Column(scale=8):
                with gr.Tab("Character"):
                    with gr.Row():
                        shared.gradio['character_menu'] = gr.Dropdown(value=shared.settings['character'], choices=utils.get_available_characters(), label='Character', elem_id='character-menu', info='Used in chat and chat-instruct modes.', elem_classes='slim-dropdown')
                        ui.create_refresh_button(shared.gradio['character_menu'], lambda: None, lambda: {'choices': utils.get_available_characters()}, 'refresh-button', interactive=not mu)
                        shared.gradio['save_character'] = gr.Button('💾', elem_classes='refresh-button', elem_id="save-character", interactive=not mu)
                        shared.gradio['delete_character'] = gr.Button('🗑️', elem_classes='refresh-button', interactive=not mu)
                        shared.gradio['restore_character'] = gr.Button('Restore character', elem_classes='refresh-button', interactive=True, elem_id='restore-character')

                    shared.gradio['name2'] = gr.Textbox(value=shared.settings['name2'], lines=1, label='Character\'s name')
                    shared.gradio['context'] = gr.Textbox(value=shared.settings['context'], lines=10, label='Context', elem_classes=['add_scrollbar'], elem_id="character-context")
                    shared.gradio['greeting'] = gr.Textbox(value=shared.settings['greeting'], lines=5, label='Greeting', elem_classes=['add_scrollbar'], elem_id="character-greeting")

                with gr.Tab("User"):
                    shared.gradio['name1'] = gr.Textbox(value=shared.settings['name1'], lines=1, label='Name')
                    shared.gradio['user_bio'] = gr.Textbox(value=shared.settings['user_bio'], lines=10, label='Description', info='Here you can optionally write a description of yourself.', placeholder='{{user}}\'s personality: ...', elem_classes=['add_scrollbar'], elem_id="user-description")

                with gr.Tab('Chat history'):
                    with gr.Row():
                        with gr.Column():
                            shared.gradio['save_chat_history'] = gr.Button(value='Save history')

                        with gr.Column():
                            shared.gradio['load_chat_history'] = gr.File(type='binary', file_types=['.json', '.txt'], label='Upload History JSON')

                with gr.Tab('Upload character'):
                    with gr.Tab('YAML or JSON'):
                        with gr.Row():
                            shared.gradio['upload_json'] = gr.File(type='binary', file_types=['.json', '.yaml'], label='JSON or YAML File', interactive=not mu)
                            shared.gradio['upload_img_bot'] = gr.Image(type='filepath', label='Profile Picture (optional)', interactive=not mu)

                        shared.gradio['Submit character'] = gr.Button(value='Submit', interactive=False)

                    with gr.Tab('TavernAI PNG'):
                        with gr.Row():
                            with gr.Column():
                                shared.gradio['upload_img_tavern'] = gr.Image(type='filepath', label='TavernAI PNG File', elem_id='upload_img_tavern', interactive=not mu)
                                shared.gradio['tavern_json'] = gr.State()
                            with gr.Column():
                                shared.gradio['tavern_name'] = gr.Textbox(value='', lines=1, label='Name', interactive=False)
                                shared.gradio['tavern_desc'] = gr.Textbox(value='', lines=10, label='Description', interactive=False, elem_classes=['add_scrollbar'])

                        shared.gradio['Submit tavern character'] = gr.Button(value='Submit', interactive=False)

            with gr.Column(scale=1):
                shared.gradio['character_picture'] = gr.Image(label='Character picture', type='filepath', interactive=not mu)
                shared.gradio['your_picture'] = gr.Image(label='Your picture', type='filepath', value=Image.open(Path('user_data/cache/pfp_me.png')) if Path('user_data/cache/pfp_me.png').exists() else None, interactive=not mu)





def create_chat_settings_ui():
    mu = shared.args.multi_user
    with gr.Tab('Instruction template'):
        with gr.Row():
            with gr.Column():
                with gr.Row():
                    shared.gradio['instruction_template'] = gr.Dropdown(choices=utils.get_available_instruction_templates(), label='Saved instruction templates', info="After selecting the template, click on \"Load\" to load and apply it.", value='None', elem_classes='slim-dropdown')
                    ui.create_refresh_button(shared.gradio['instruction_template'], lambda: None, lambda: {'choices': utils.get_available_instruction_templates()}, 'refresh-button', interactive=not mu)
                    shared.gradio['load_template'] = gr.Button("Load", elem_classes='refresh-button')
                    shared.gradio['save_template'] = gr.Button('💾', elem_classes='refresh-button', interactive=not mu)
                    shared.gradio['delete_template'] = gr.Button('🗑️ ', elem_classes='refresh-button', interactive=not mu)

            with gr.Column():
                pass

        with gr.Row():
            with gr.Column():
                shared.gradio['instruction_template_str'] = gr.Textbox(value=shared.settings['instruction_template_str'], label='Instruction template', lines=24, info='This gets autodetected; you usually don\'t need to change it. Used in instruct and chat-instruct modes.', elem_classes=['add_scrollbar', 'monospace'], elem_id='instruction-template-str')
                with gr.Row():
                    shared.gradio['send_instruction_to_notebook'] = gr.Button('Send to notebook', elem_classes=['small-button'])

            with gr.Column():
                shared.gradio['chat_template_str'] = gr.Textbox(value=shared.settings['chat_template_str'], label='Chat template', lines=22, elem_classes=['add_scrollbar', 'monospace'], info='Defines how the chat prompt in chat/chat-instruct modes is generated.', elem_id='chat-template-str')


def create_event_handlers():
    shared.gradio['adaptive_summarize_btn'].click(
        lambda text: summarize_text(text if isinstance(text, str) else str(text)),
        gradio('adaptive_text'),
        gradio('adaptive_output'),
        show_progress=False,
    )
    shared.gradio['adaptive_actions_btn'].click(
        lambda text: suggest_actions(text if isinstance(text, str) else str(text)),
        gradio('adaptive_text'),
        gradio('adaptive_output'),
        show_progress=False,
    )
    shared.gradio['adaptive_bugs_btn'].click(
        lambda text: 'Potential issues\n' + summarize_text(text if isinstance(text, str) else str(text)),
        gradio('adaptive_text'),
        gradio('adaptive_output'),
        show_progress=False,
    )
    shared.gradio['adaptive_task_btn'].click(
        lambda text: 'Task created from message summary\n' + summarize_text(text if isinstance(text, str) else str(text)),
        gradio('adaptive_text'),
        gradio('adaptive_output'),
        show_progress=False,
    )
    shared.gradio['provenance_btn'].click(
        lambda: str(list_steps('default')),
        None,
        gradio('adaptive_output'),
        show_progress=False,
    )

    # Obsolete variables, kept for compatibility with old extensions
    shared.input_params = gradio(inputs)
    shared.reload_inputs = gradio(reload_arr)

    # Morph HTML updates instead of updating everything
    shared.gradio['display'].change(None, gradio('display'), None, js="(data) => handleMorphdomUpdate(data)")

    def _get_any(*keys):
        for key in keys:
            if key in shared.gradio:
                return shared.gradio[key]
        return None

    def _bind_click(key_options, fn, input_keys, output_keys):
        target = _get_any(*key_options)
        if target is None:
            return
        target.click(fn, gradio(*input_keys) if input_keys else None, gradio(*output_keys) if output_keys else None, show_progress=False)

    shared.gradio['Generate'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        lambda x: x, gradio('textbox'), gradio('Chat input'), show_progress=False).then(
        apply_custom_ai_style,
        gradio('Chat input', 'custom_style_enabled', 'custom_style_prompt'),
        gradio('Chat input'),
        show_progress=False).then(
        lambda x: {"text": "", "files": []}, None, gradio('textbox'), show_progress=False).then(
        lambda: None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.add("_generating")').then(
        chat.generate_chat_reply_wrapper, gradio(inputs), gradio('display', 'history'), show_progress=False).then(
        None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.remove("_generating")').then(
        None, None, None, js=f'() => {{{ui.audio_notification_js}}}')

    shared.gradio['textbox'].submit(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        lambda x: x, gradio('textbox'), gradio('Chat input'), show_progress=False).then(
        apply_custom_ai_style,
        gradio('Chat input', 'custom_style_enabled', 'custom_style_prompt'),
        gradio('Chat input'),
        show_progress=False).then(
        lambda x: {"text": "", "files": []}, None, gradio('textbox'), show_progress=False).then(
        lambda: None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.add("_generating")').then(
        chat.generate_chat_reply_wrapper, gradio(inputs), gradio('display', 'history'), show_progress=False).then(
        None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.remove("_generating")').then(
        None, None, None, js=f'() => {{{ui.audio_notification_js}}}')

    shared.gradio['apply_lesson_tab_prompt'].click(
        apply_lesson_tab_prompt,
        None,
        gradio('custom_style_enabled', 'custom_style_prompt'),
        show_progress=False)

    shared.gradio['Regenerate'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        lambda: None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.add("_generating")').then(
        partial(chat.generate_chat_reply_wrapper, regenerate=True), gradio(inputs), gradio('display', 'history'), show_progress=False).then(
        None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.remove("_generating")').then(
        None, None, None, js=f'() => {{{ui.audio_notification_js}}}')

    shared.gradio['Continue'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        lambda: None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.add("_generating")').then(
        partial(chat.generate_chat_reply_wrapper, _continue=True), gradio(inputs), gradio('display', 'history'), show_progress=False).then(
        None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.remove("_generating")').then(
        None, None, None, js=f'() => {{{ui.audio_notification_js}}}')

    shared.gradio['Impersonate'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        lambda x: x, gradio('textbox'), gradio('Chat input'), show_progress=False).then(
        lambda: None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.add("_generating")').then(
        chat.impersonate_wrapper, gradio(inputs), gradio('textbox', 'display'), show_progress=False).then(
        None, None, None, js='() => document.getElementById("chat").parentNode.parentNode.parentNode.classList.remove("_generating")').then(
        None, None, None, js=f'() => {{{ui.audio_notification_js}}}')

    shared.gradio['Send dummy message'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_send_dummy_message_click, gradio('textbox', 'interface_state'), gradio('history', 'display', 'textbox'), show_progress=False)

    shared.gradio['Send dummy reply'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_send_dummy_reply_click, gradio('textbox', 'interface_state'), gradio('history', 'display', 'textbox'), show_progress=False)

    shared.gradio['Remove last'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_remove_last_click, gradio('interface_state'), gradio('history', 'display', 'textbox'), show_progress=False)

    shared.gradio['Stop'].click(
        stop_everything_event, None, None, queue=False).then(
        chat.redraw_html, gradio(reload_arr), gradio('display'), show_progress=False)

    if not shared.args.multi_user:
        shared.gradio['unique_id'].select(
            ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
            chat.handle_unique_id_select, gradio('interface_state'), gradio('history', 'display'), show_progress=False)

    shared.gradio['Start new chat'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_start_new_chat_click, gradio('interface_state'), gradio('history', 'display', 'unique_id'), show_progress=False)

    shared.gradio['delete_chat-confirm'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_delete_chat_confirm_click, gradio('interface_state'), gradio('history', 'display', 'unique_id'), show_progress=False)

    shared.gradio['branch_chat'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_branch_chat_click, gradio('interface_state'), gradio('history', 'display', 'unique_id', 'branch_index'), show_progress=False)

    shared.gradio['rename_chat'].click(chat.handle_rename_chat_click, None, gradio('rename_to', 'rename-row'), show_progress=False)
    shared.gradio['rename_to-cancel'].click(lambda: gr.update(visible=False), None, gradio('rename-row'), show_progress=False)
    shared.gradio['rename_to-confirm'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_rename_chat_confirm, gradio('rename_to', 'interface_state'), gradio('unique_id', 'rename-row'))

    shared.gradio['rename_to'].submit(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_rename_chat_confirm, gradio('rename_to', 'interface_state'), gradio('unique_id', 'rename-row'), show_progress=False)

    shared.gradio['search_chat'].change(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_search_chat_change, gradio('interface_state'), gradio('unique_id'), show_progress=False)

    shared.gradio['load_chat_history'].upload(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_upload_chat_history, gradio('load_chat_history', 'interface_state'), gradio('history', 'display', 'unique_id'), show_progress=False).then(
        None, None, None, js=f'() => {{{ui.switch_tabs_js}; switch_to_chat()}}')

    shared.gradio['character_menu'].change(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_character_menu_change, gradio('interface_state'), gradio('history', 'display', 'name1', 'name2', 'character_picture', 'greeting', 'context', 'unique_id'), show_progress=False).then(
        None, None, None, js=f'() => {{{ui.update_big_picture_js}; updateBigPicture()}}')

    shared.gradio['character_picture'].change(chat.handle_character_picture_change, gradio('character_picture'), None, show_progress=False)

    shared.gradio['mode'].change(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_mode_change, gradio('interface_state'), gradio('history', 'display', 'chat_style', 'chat-instruct_command', 'unique_id'), show_progress=False).then(
        None, gradio('mode'), None, js="(mode) => {const characterContainer = document.getElementById('character-menu').parentNode.parentNode; const isInChatTab = document.querySelector('#chat-controls').contains(characterContainer); if (isInChatTab) { characterContainer.style.display = mode === 'instruct' ? 'none' : ''; } if (mode === 'instruct') document.querySelectorAll('.bigProfilePicture').forEach(el => el.remove());}")

    shared.gradio['chat_style'].change(chat.redraw_html, gradio(reload_arr), gradio('display'), show_progress=False)

    # ── GitHub Agent: sidebar Connect ────────────────────────────────────────

    def _gh_connect(repo_path, base_branch, token):
        status, repo_out, session_json, chat_html = github_connect(repo_path, base_branch, token)
        status_html = github_status_html(status, None, None)
        return status, repo_out, session_json, status_html, chat_html

    shared.gradio['gh_connect_btn'].click(
        _gh_connect,
        gradio('gh_repo_path', 'gh_base_branch', 'gh_token'),
        gradio('gh_status', 'gh_repo_path', 'gh_session', 'gh_status_html', 'gh_chat_html'),
        show_progress=False,
    )

    # ── GitHub Agent: toggle panel ────────────────────────────────────────────

    def _gh_toggle_panel(is_visible):
        new_visible = not is_visible
        return gr.update(visible=new_visible), new_visible

    shared.gradio['gh_toggle_btn'].click(
        _gh_toggle_panel,
        gradio('gh_panel_visible'),
        gradio('gh_panel_row', 'gh_panel_visible'),
        show_progress=False,
    )

    def _gh_close_panel():
        return gr.update(visible=False), False

    shared.gradio['gh_panel_close_btn'].click(
        _gh_close_panel,
        None,
        gradio('gh_panel_row', 'gh_panel_visible'),
        show_progress=False,
    )

    # ── GitHub Agent: chat send ───────────────────────────────────────────────

    def _gh_send_msg(msg, session_json, repo_path):
        new_session_json, chat_html = github_agent_send(msg, session_json, repo_path)
        return "", new_session_json, chat_html

    shared.gradio['gh_msg_send_btn'].click(
        _gh_send_msg,
        gradio('gh_msg_input', 'gh_session', 'gh_repo_path'),
        gradio('gh_msg_input', 'gh_session', 'gh_chat_html'),
        show_progress=False,
    )

    shared.gradio['gh_msg_input'].submit(
        _gh_send_msg,
        gradio('gh_msg_input', 'gh_session', 'gh_repo_path'),
        gradio('gh_msg_input', 'gh_session', 'gh_chat_html'),
        show_progress=False,
    )

    # ── GitHub Agent: single branch ───────────────────────────────────────────

    def _gh_single_branch(task, mode, effort, repo_path, base_branch, session_json):
        status, branch, task_file, new_session_json, chat_html = github_create_branch(
            task, mode, effort, repo_path, base_branch, session_json
        )
        status_html = github_status_html(status, branch, None)
        branches_html = render_branches_html(json.loads(new_session_json or "{}"))
        return status, branch, task_file, new_session_json, chat_html, branches_html, status_html

    shared.gradio['gh_single_branch_btn'].click(
        _gh_single_branch,
        gradio('gh_task_panel', 'mode', 'reasoning_effort', 'gh_repo_path', 'gh_base_branch', 'gh_session'),
        gradio('gh_status', 'gh_branch', 'gh_task_file', 'gh_session',
               'gh_chat_html', 'gh_branches_html', 'gh_panel_status'),
        show_progress=False,
    )

    # ── GitHub Agent: launch multi-agent ─────────────────────────────────────

    def _gh_launch(task, roles, model, repo_path, base_branch, session_json):
        status, new_session_json, chat_html, branches_html = github_launch_multi_agent(
            task, roles, model, repo_path, base_branch, session_json
        )
        panel_status = github_status_html(status, None, None)
        return status, new_session_json, chat_html, branches_html, panel_status

    shared.gradio['gh_launch_btn'].click(
        _gh_launch,
        gradio('gh_task_panel', 'gh_agent_roles', 'gh_model_override',
               'gh_repo_path', 'gh_base_branch', 'gh_session'),
        gradio('gh_status', 'gh_session', 'gh_chat_html', 'gh_branches_html', 'gh_panel_status'),
        show_progress=False,
    )

    # ── GitHub Agent: merge all → PR ─────────────────────────────────────────

    def _gh_merge_all(repo_path, base_branch, pr_title, session_json):
        status, pr_url, new_session_json, chat_html, branches_html = github_merge_all_pr(
            repo_path, base_branch, pr_title, session_json
        )
        panel_status = github_status_html(status, None, pr_url)
        return status, pr_url, new_session_json, chat_html, branches_html, panel_status

    shared.gradio['gh_merge_pr_btn'].click(
        _gh_merge_all,
        gradio('gh_repo_path', 'gh_base_branch', 'gh_pr_title_panel', 'gh_session'),
        gradio('gh_status', 'gh_pr_url', 'gh_session', 'gh_chat_html', 'gh_branches_html', 'gh_panel_status'),
        show_progress=False,
    )

    # ── GitHub Agent: send status to main chat ────────────────────────────────

    shared.gradio['gh_panel_send_btn'].click(
        github_send_to_chat,
        gradio('gh_status', 'gh_branch', 'gh_task_panel', 'gh_pr_url'),
        gradio('textbox'),
        show_progress=False,
    )

    shared.gradio['navigate_version'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_navigate_version_click, gradio('interface_state'), gradio('history', 'display'), show_progress=False)

    shared.gradio['edit_message'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_edit_message_click, gradio('interface_state'), gradio('history', 'display'), show_progress=False)

    # Save/delete a character
    shared.gradio['save_character'].click(chat.handle_save_character_click, gradio('name2'), gradio('save_character_filename', 'character_saver'), show_progress=False)
    shared.gradio['delete_character'].click(lambda: gr.update(visible=True), None, gradio('character_deleter'), show_progress=False)
    shared.gradio['load_template'].click(chat.handle_load_template_click, gradio('instruction_template'), gradio('instruction_template_str', 'instruction_template'), show_progress=False)
    shared.gradio['save_template'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_save_template_click, gradio('instruction_template_str'), gradio('save_filename', 'save_root', 'save_contents', 'file_saver'), show_progress=False)

    shared.gradio['restore_character'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.restore_character_for_ui, gradio('interface_state'), gradio('interface_state', 'name2', 'context', 'greeting', 'character_picture'), show_progress=False)

    shared.gradio['delete_template'].click(chat.handle_delete_template_click, gradio('instruction_template'), gradio('delete_filename', 'delete_root', 'file_deleter'), show_progress=False)
    shared.gradio['save_chat_history'].click(
        lambda x: json.dumps(x, indent=4), gradio('history'), gradio('temporary_text')).then(
        None, gradio('temporary_text', 'character_menu', 'mode'), None, js=f'(hist, char, mode) => {{{ui.save_files_js}; saveHistory(hist, char, mode)}}')

    shared.gradio['Submit character'].click(
        chat.upload_character, gradio('upload_json', 'upload_img_bot'), gradio('character_menu'), show_progress=False).then(
        None, None, None, js=f'() => {{{ui.switch_tabs_js}; switch_to_character()}}')

    shared.gradio['Submit tavern character'].click(
        chat.upload_tavern_character, gradio('upload_img_tavern', 'tavern_json'), gradio('character_menu'), show_progress=False).then(
        None, None, None, js=f'() => {{{ui.switch_tabs_js}; switch_to_character()}}')

    shared.gradio['upload_json'].upload(lambda: gr.update(interactive=True), None, gradio('Submit character'))
    shared.gradio['upload_json'].clear(lambda: gr.update(interactive=False), None, gradio('Submit character'))
    shared.gradio['upload_img_tavern'].upload(chat.check_tavern_character, gradio('upload_img_tavern'), gradio('tavern_name', 'tavern_desc', 'tavern_json', 'Submit tavern character'), show_progress=False)
    shared.gradio['upload_img_tavern'].clear(lambda: (None, None, None, gr.update(interactive=False)), None, gradio('tavern_name', 'tavern_desc', 'tavern_json', 'Submit tavern character'), show_progress=False)
    shared.gradio['your_picture'].change(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_your_picture_change, gradio('your_picture', 'interface_state'), gradio('display'), show_progress=False)

    shared.gradio['send_instruction_to_notebook'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_send_instruction_click, gradio('interface_state'), gradio('textbox-notebook', 'textbox-default', 'output_textbox'), show_progress=False).then(
        None, None, None, js=f'() => {{{ui.switch_tabs_js}; switch_to_notebook()}}')

    shared.gradio['send-chat-to-notebook'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.handle_send_chat_click, gradio('interface_state'), gradio('textbox-notebook', 'textbox-default', 'output_textbox'), show_progress=False).then(
        None, None, None, js=f'() => {{{ui.switch_tabs_js}; switch_to_notebook()}}')

    shared.gradio['show_controls'].change(None, gradio('show_controls'), None, js=f'(x) => {{{ui.show_controls_js}; toggle_controls(x)}}')

    shared.gradio['count_tokens'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        chat.count_prompt_tokens, gradio('textbox', 'interface_state'), gradio('token_display'), show_progress=False)

    shared.gradio['enable_web_search'].change(
        lambda x: gr.update(visible=x),
        gradio('enable_web_search'),
        gradio('web_search_row')
    )

    shared.gradio['template_category'].change(
        refresh_template_choices,
        gradio('template_category'),
        gradio('template_list'),
        show_progress=False,
    )

    shared.gradio['apply_template_btn'].click(
        apply_selected_template,
        gradio('template_list', 'history'),
        gradio('history', 'context', 'template_status'),
        show_progress=False,
    ).then(
        chat.redraw_html,
        gradio(reload_arr),
        gradio('display'),
        show_progress=False,
    )

    shared.gradio['create_template_btn'].click(
        create_template_and_refresh,
        gradio(
            'custom_template_name',
            'custom_template_desc',
            'custom_template_prompt',
            'custom_template_category',
            'custom_template_icon',
            'template_category',
        ),
        gradio('template_status', 'template_list'),
        show_progress=False,
    )

    shared.gradio['edit_message_btn'].click(
        edit_message_action,
        gradio('history', 'message_index', 'edit_message_new_content'),
        gradio('history', 'context_status'),
        show_progress=False,
    ).then(
        chat.redraw_html,
        gradio(reload_arr),
        gradio('display'),
        show_progress=False,
    )

    shared.gradio['branch_conversation_btn'].click(
        branch_conversation_action,
        gradio('history', 'branch_point'),
        gradio('history', 'context_status'),
        show_progress=False,
    ).then(
        chat.redraw_html,
        gradio(reload_arr),
        gradio('display'),
        show_progress=False,
    )

    shared.gradio['save_snippet_btn'].click(
        save_snippet_action,
        gradio('history', 'message_index', 'snippet_category'),
        gradio('context_status'),
        show_progress=False,
    )

    shared.gradio['export_btn'].click(
        export_conversation_action,
        gradio('history', 'export_start', 'export_end', 'export_format'),
        gradio('context_status'),
        show_progress=False,
    )

    shared.gradio['refresh_context_btn'].click(
        analyze_context,
        gradio('history'),
        gradio('context_token_display', 'context_status'),
        show_progress=False,
    )

    shared.gradio['pin_message_btn'].click(
        pin_message_action,
        gradio('history', 'pin_message_index'),
        gradio('context_status'),
        show_progress=False,
    )

    shared.gradio['prune_context_btn'].click(
        prune_context_action,
        gradio('history'),
        gradio('history', 'context_status'),
        show_progress=False,
    ).then(
        chat.redraw_html,
        gradio(reload_arr),
        gradio('display'),
        show_progress=False,
    ).then(
        analyze_context,
        gradio('history'),
        gradio('context_token_display', 'context_status'),
        show_progress=False,
    )

    shared.gradio['summarize_conversation_btn'].click(
        build_summary_prompt,
        gradio('history'),
        gradio('context_status'),
        show_progress=False,
    )
