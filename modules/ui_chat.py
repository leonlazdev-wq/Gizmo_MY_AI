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


def _github_config_path():
    p = Path("user_data") / "github_agent.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_github_config():
    p = _github_config_path()
    if not p.exists():
        return {"repo_url": "", "repo_path": ".", "base_branch": "main", "token": ""}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"repo_url": "", "repo_path": ".", "base_branch": "main", "token": ""}


def _save_github_config(cfg):
    _github_config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _run_git(args, cwd):
    proc = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def github_connect(repo_url, repo_path, base_branch, token):
    cfg = {
        "repo_url": (repo_url or "").strip(),
        "repo_path": (repo_path or ".").strip() or ".",
        "base_branch": (base_branch or "main").strip() or "main",
        "token": (token or "").strip(),
    }
    repo = Path(cfg["repo_path"]).resolve()

    if cfg["repo_url"] and (not repo.exists() or not (repo / ".git").exists()):
        repo.parent.mkdir(parents=True, exist_ok=True)
        clone_url = cfg["repo_url"]
        if cfg["token"] and clone_url.startswith("https://") and "@" not in clone_url:
            clone_url = "https://" + cfg["token"] + "@" + clone_url[len("https://"):]
        proc = subprocess.run(["git", "clone", clone_url, str(repo)], text=True, capture_output=True)
        if proc.returncode != 0:
            return f"❌ Clone failed: {(proc.stderr or proc.stdout).strip()}", "", ""

    if not repo.exists() or not (repo / ".git").exists():
        return "❌ Invalid repository path (missing .git directory).", "", ""

    code, out, err = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    if code != 0:
        return f"❌ Git repo check failed: {err or out}", "", ""
    _save_github_config(cfg)
    return f"✅ Connected to {repo} (current branch: {out})", str(repo), cfg.get("repo_url", "")


def github_create_branch(task_text, mode, thinking, repo_path, base_branch):
    repo = Path((repo_path or ".").strip() or ".").resolve()
    if not repo.exists() or not (repo / ".git").exists():
        return "❌ Invalid repository path.", "", ""
    if not (task_text or "").strip():
        return "❌ Task is required.", "", ""

    branch = f"gizmo/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    _run_git(["checkout", base_branch or "main"], repo)
    code, out, err = _run_git(["checkout", "-b", branch], repo)
    if code != 0:
        return f"❌ Could not create branch: {err or out}", "", ""

    tasks_dir = repo / "user_data" / "github_agent_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_file = tasks_dir / f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    task_file.write_text(
        f"# GitHub Agent Task\n\n- Mode: {mode}\n- Thinking: {thinking}\n- Branch: {branch}\n\n## Instruction\n{task_text}\n",
        encoding="utf-8",
    )

    _run_git(["add", str(task_file.relative_to(repo))], repo)
    _run_git(["commit", "-m", f"chore: start github agent task ({branch})"], repo)
    return f"✅ Branch ready: {branch}. Task file committed.", branch, str(task_file)


def github_open_pr(repo_path, branch, title, body):
    cfg = _load_github_config()
    repo = Path((repo_path or cfg.get("repo_path") or ".")).resolve()
    if not repo.exists() or not (repo / ".git").exists():
        return "❌ Invalid repository path.", ""
    if not branch:
        return "❌ Create a branch first.", ""

    code, out, err = _run_git(["push", "-u", "origin", branch], repo)
    if code != 0:
        return f"❌ Push failed: {err or out}", ""

    gh_check = subprocess.run(["bash", "-lc", "command -v gh"], text=True, capture_output=True)
    if gh_check.returncode != 0:
        return "✅ Branch pushed. Install/authenticate GitHub CLI (`gh`) to create PR automatically.", ""

    cmd = ["gh", "pr", "create", "--title", title or f"AI: {branch}", "--body", body or "Automated PR by Gizmo GitHub Agent", "--head", branch]
    proc = subprocess.run(cmd, cwd=repo, text=True, capture_output=True)
    if proc.returncode != 0:
        return f"⚠️ Branch pushed, but PR creation failed: {(proc.stderr or proc.stdout).strip()}", ""
    pr_url = (proc.stdout or "").strip().splitlines()[-1] if (proc.stdout or "").strip() else ""
    return "✅ Pull request created.", pr_url


def github_repo_health(repo_path):
    repo = Path((repo_path or '.').strip() or '.').resolve()
    if not repo.exists() or not (repo / '.git').exists():
        return "❌ Invalid repository path.", []

    def _safe_git(args):
        code, out, err = _run_git(args, repo)
        return out if code == 0 else (err or out)

    branch = _safe_git(["rev-parse", "--abbrev-ref", "HEAD"])
    remote = _safe_git(["remote", "get-url", "origin"])
    ahead_behind = _safe_git(["status", "--porcelain=v1", "--branch"]).splitlines()[:2]
    changed = _safe_git(["status", "--short"]).splitlines()
    gh_ready = subprocess.run(["bash", "-lc", "command -v gh"], text=True, capture_output=True).returncode == 0

    summary = [
        f"✅ Repo: {repo}",
        f"🌿 Branch: {branch}",
        f"🔗 Origin: {remote}",
        f"🧰 GitHub CLI: {'available' if gh_ready else 'not found'}",
    ]
    if ahead_behind:
        summary.extend([f"📈 {line}" for line in ahead_behind])
    if changed:
        summary.append(f"📝 Changed files: {len(changed)}")

    table = [[line[:2].strip() or '--', line[3:]] for line in changed[:200]]
    return "\n".join(summary), table


def github_create_multi_agent_tasks(repo_path, base_branch, task_text, ai_count, models_csv, strategy):
    repo = Path((repo_path or '.').strip() or '.').resolve()
    if not repo.exists() or not (repo / '.git').exists():
        return "❌ Invalid repository path.", ""
    if not (task_text or '').strip():
        return "❌ Task is required.", ""

    count = max(1, min(8, int(ai_count or 1)))
    model_list = [m.strip() for m in (models_csv or '').split(',') if m.strip()]
    if not model_list:
        model_list = [shared.settings.get('model', 'current-model')]

    tasks_dir = repo / 'user_data' / 'github_agent_tasks'
    tasks_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    board = tasks_dir / f'team_board_{stamp}.md'

    lines = [
        '# Multi-AI Coding Board',
        '',
        f'- Base branch: {base_branch or "main"}',
        f'- Strategy: {strategy}',
        f'- Agents: {count}',
        f'- Models: {", ".join(model_list)}',
        '',
        '## Objective',
        task_text.strip(),
        '',
        '## Agent Assignments',
    ]

    for i in range(count):
        model = model_list[i % len(model_list)]
        role = ['Planner', 'Implementer', 'Reviewer', 'Tester', 'Security', 'Docs', 'Performance', 'Release'][i % 8]
        lines.extend([
            f'### Agent {i+1} — {role}',
            f'- Model: {model}',
            f'- Deliverable: {role} update for objective',
            f'- Branch suggestion: gizmo/{role.lower()}-{stamp}',
            '',
        ])

    board.write_text("\n".join(lines), encoding='utf-8')
    return f"✅ Created multi-AI task board with {count} agents.", str(board)


def build_multi_ai_prompt(task_text, ai_count, models_csv, strategy):
    task = (task_text or '').strip()
    if not task:
        return '❌ Enter a task first.'

    count = max(1, min(8, int(ai_count or 1)))
    models = [m.strip() for m in (models_csv or '').split(',') if m.strip()]
    if not models:
        models = ['model-a', 'model-b']

    lines = [
        'You are an AI team working in parallel.',
        f'Strategy: {strategy}',
        f'Agent count: {count}',
        f'Model pool: {", ".join(models)}',
        '',
        'Task:',
        task,
        '',
        'Protocol:',
        '1) Planner agent decomposes into milestones.',
        '2) Implementer agents work in parallel per milestone.',
        '3) Reviewer agent performs diff + risk checks.',
        '4) Tester agent validates and reports gaps.',
        '5) Final synthesizer outputs unified patch + changelog.',
    ]
    return "\n".join(lines)


def _build_kanban(rows):
    cards = []
    for role, branch, status, detail in rows:
        lane = 'Backlog' if status == 'ready' else 'Review'
        cards.append({'title': role, 'branch': branch, 'status': lane, 'detail': detail})
    return {
        'Backlog': [c for c in cards if c['status'] == 'Backlog'],
        'In Progress': [],
        'Review': [c for c in cards if c['status'] == 'Review'],
        'Done': [],
    }


def _timeline_from_rows(rows, header='Execution timeline'):
    lines = [header]
    for role, branch, status, detail in rows:
        lines.append(f'- {role} | {branch} | {status} | {detail}')
    return "\n".join(lines)


def start_parallel_executor_action(repo_path, base_branch, task_text, strategy, ai_count):
    status, integration_branch, rows = start_parallel_branches(repo_path, base_branch, task_text, strategy, ai_count)
    branch_list = ", ".join([r[1] for r in rows if r[2] == 'ready'])
    kanban = _build_kanban(rows)
    timeline = _timeline_from_rows(rows, header='Parallel branch executor')
    why = (
        'Created role-specialized agent branches with budget caps and shared workspace artifacts. '
        'Use quality gates before requesting one big PR into main.'
    )
    return status, integration_branch, branch_list, timeline, kanban, rows, why


def quality_gates_action(repo_path, integration_branch):
    status, rows = run_quality_gates(repo_path, integration_branch)
    timeline = _timeline_from_rows([[r[0], integration_branch, r[1], r[2]] for r in rows], header='Quality gates')
    why = 'Quality gates enforce compile/lint/security checks before merge.'
    return status, timeline, rows, why


def conflict_synth_action(repo_path, integration_branch, branch_list):
    status, rationale_path = synthesize_conflicts(repo_path, integration_branch, branch_list)
    rows = [['conflict-synthesizer', 'done', rationale_path or 'n/a']]
    timeline = f'Conflict synthesizer result\n- {status}\n- rationale: {rationale_path or "n/a"}'
    why = 'Conflict-aware synthesizer merged clean branches and produced rationale for manual/AI review.'
    return status, timeline, rows, why


def issue_plan_action(issue_text, strategy):
    status, plan = issue_to_plan(issue_text, strategy)
    return status, plan


def strategy_template_action(strategy):
    templates = {
        'planner->workers->reviewer': (
            "Template: Bugfix\n"
            "- Reproduce\n"
            "- Isolate root cause\n"
            "- Patch\n"
            "- Regression tests\n"
            "- Reviewer sign-off"
        ),
        'spec->implement->test': (
            "Template: Feature\n"
            "- Spec acceptance criteria\n"
            "- Implement slices\n"
            "- Add tests\n"
            "- Docs update"
        ),
        'fast parallel brainstorm': (
            "Template: Refactor/Ideas\n"
            "- Generate alternatives\n"
            "- Rank by risk\n"
            "- Choose plan\n"
            "- Execute minimal safe path"
        ),
    }
    return templates.get(strategy, 'Template unavailable')


def repo_map_action(repo_path):
    status, rows = build_repo_map(repo_path)
    return status, rows


def pr_intel_action(repo_path, integration_branch):
    status, report = pr_intelligence(repo_path, integration_branch)
    why = 'PR intelligence estimates risk, impacted files, and rollback guidance.'
    return status, report, why


def sync_main_action(repo_path, branch_list):
    status, rows = sync_branches_with_main(repo_path, branch_list)
    timeline = _timeline_from_rows([[r[0], r[0], r[1], r[2]] for r in rows], header='Sync with main')
    return status, timeline, rows


def ensemble_vote_action(candidate_lines):
    lines = [x.strip() for x in (candidate_lines or '').splitlines() if x.strip()]
    if not lines:
        return '❌ Add candidate responses: model: answer', ''

    answers = {}
    for line in lines:
        if ':' in line:
            _, ans = line.split(':', 1)
            key = ans.strip()
        else:
            key = line
        answers[key] = answers.get(key, 0) + 1

    winner = sorted(answers.items(), key=lambda x: x[1], reverse=True)[0]
    report = "\n".join([f'- {k} (votes: {v})' for k, v in sorted(answers.items(), key=lambda x: x[1], reverse=True)])
    return f'✅ Ensemble winner: {winner[0]}', report


def debate_mode_action(proposal, critique):
    if not (proposal or '').strip():
        return '❌ Proposal is required.'

    synthesis = (
        'Debate synthesis:\n'
        f'Proposal: {(proposal or "").strip()}\n\n'
        f'Critique: {(critique or "No critique provided").strip()}\n\n'
        'Final: Keep proposal intent, apply critique risk mitigations, add tests and docs.'
    )
    return synthesis


def cost_optimizer_action(task_text, models_csv):
    models = [m.strip() for m in (models_csv or '').split(',') if m.strip()]
    if not models:
        models = ['small-model', 'large-model']

    task = (task_text or '').strip()
    complexity = len(task.split())
    chosen = models[0] if complexity < 40 else models[min(1, len(models) - 1)]
    reason = 'short/simple task' if complexity < 40 else 'larger/complex task'
    return f'✅ Route to: {chosen} ({reason}, tokens≈{complexity})'


def memory_bus_action(repo_path, decision, constraint, todo):
    repo = Path((repo_path or '.').strip() or '.').resolve()
    if not (repo / '.git').exists():
        return '❌ Invalid repository path.', ''

    bus = repo / 'user_data' / 'ai_workspace' / 'memory_bus.json'
    bus.parent.mkdir(parents=True, exist_ok=True)
    data = {'decisions': [], 'constraints': [], 'todos': []}
    if bus.exists():
        try:
            data = json.loads(bus.read_text(encoding='utf-8'))
        except Exception:
            pass

    if (decision or '').strip():
        data.setdefault('decisions', []).append(decision.strip())
    if (constraint or '').strip():
        data.setdefault('constraints', []).append(constraint.strip())
    if (todo or '').strip():
        data.setdefault('todos', []).append(todo.strip())

    bus.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return '✅ Memory bus updated.', json.dumps(data, indent=2)


def unified_pr_prep_action(repo_path, integration_branch, branch_list, pr_title, issue_plan, why_change):
    synth_status, rationale_path = synthesize_conflicts(repo_path, integration_branch, branch_list)
    body = "\n".join([
        "## Unified Multi-Agent PR",
        "",
        f"- Integration branch: {integration_branch}",
        f"- Synthesis: {synth_status}",
        f"- Conflict rationale: {rationale_path or 'n/a'}",
        "",
        "## Issue Plan",
        issue_plan or "(not provided)",
        "",
        "## Why this change",
        why_change or "(not provided)",
    ])
    final_title = pr_title or f"AI Orchestration: merge agent branches into {integration_branch}"
    return '✅ Unified PR draft prepared. Use Push + Open PR.', final_title, body



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
                with gr.Row(elem_id="chat-input-row"):
                    with gr.Column(scale=1, elem_id='gr-hover-container'):
                        gr.HTML(value='<div class="hover-element" onclick="void(0)"><span style="width: 100px; display: block" id="hover-element-button">&#9776;</span><div class="hover-menu" id="hover-menu"></div>', elem_id='gr-hover')

                    with gr.Column(scale=10, elem_id='chat-input-container'):
                        shared.gradio['textbox'] = gr.MultimodalTextbox(label='', placeholder='Send a message', file_types=['text', '.pdf', 'image'], file_count="multiple", elem_id='chat-input', elem_classes=['add_scrollbar'])
                        shared.gradio['typing-dots'] = gr.HTML(value='<div class="typing"><span></span><span class="dot1"></span><span class="dot2"></span></div>', label='typing', elem_id='typing-container')

                    with gr.Column(scale=1, elem_id='connector-plus-container'):
                        shared.gradio['connector-plus'] = gr.HTML(value='''<div class="connector-menu-wrapper">
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

                with gr.Accordion('🔧 GitHub Agent (Beta)', open=False):
                    gh_defaults = _load_github_config()
                    shared.gradio['gh_repo_url'] = gr.Textbox(label='Repository URL (optional)', value=gh_defaults.get('repo_url', ''), placeholder='https://github.com/owner/repo.git')
                    shared.gradio['gh_repo_path'] = gr.Textbox(label='Local repository path', value=gh_defaults.get('repo_path', '.'))
                    shared.gradio['gh_base_branch'] = gr.Textbox(label='Base branch', value=gh_defaults.get('base_branch', 'main'))
                    shared.gradio['gh_token'] = gr.Textbox(label='GitHub token (optional, for gh auth)', type='password', value=gh_defaults.get('token', ''))
                    shared.gradio['gh_task'] = gr.Textbox(label='Task for AI coding agent', lines=4, placeholder='Describe the code change to implement...')
                    with gr.Row():
                        shared.gradio['gh_connect_btn'] = gr.Button('🔌 Connect Repo')
                        shared.gradio['gh_branch_btn'] = gr.Button('🌿 Create Branch + Task Commit')
                    with gr.Row():
                        shared.gradio['gh_pr_title'] = gr.Textbox(label='PR title', value='AI generated change')
                        shared.gradio['gh_pr_btn'] = gr.Button('🚀 Push + Open PR', variant='primary')
                    shared.gradio['gh_status'] = gr.Textbox(label='GitHub Agent Status', interactive=False)
                    shared.gradio['gh_branch'] = gr.Textbox(label='Working branch', interactive=False)
                    shared.gradio['gh_task_file'] = gr.Textbox(label='Task file', interactive=False)
                    shared.gradio['gh_pr_url'] = gr.Textbox(label='PR URL', interactive=False)

                    with gr.Accordion('🧠 AI Team + Copilot Studio', open=False):
                        shared.gradio['ai_team_count'] = gr.Slider(minimum=1, maximum=8, value=3, step=1, label='Parallel AI workers')
                        shared.gradio['ai_team_models'] = gr.Textbox(label='Model pool (comma-separated)', placeholder='qwen2.5-coder-14b, mistral-7b, gpt-oss')
                        shared.gradio['ai_team_strategy'] = gr.Dropdown(
                            choices=['planner->workers->reviewer', 'spec->implement->test', 'fast parallel brainstorm'],
                            value='planner->workers->reviewer',
                            label='Coordination strategy',
                        )
                        with gr.Row():
                            shared.gradio['ai_team_prompt_btn'] = gr.Button('🪄 Build Team Prompt')
                            shared.gradio['gh_health_btn'] = gr.Button('🩺 Repo Health Check')
                            shared.gradio['gh_team_tasks_btn'] = gr.Button('🗂️ Create Multi-AI Task Board')
                        shared.gradio['ai_team_prompt'] = gr.Textbox(label='Generated Team Prompt', lines=8)
                        shared.gradio['gh_health_table'] = gr.Dataframe(
                            headers=['status', 'path/file'],
                            datatype=['str', 'str'],
                            row_count=8,
                            interactive=False,
                        )


                        gr.Markdown('### 🧭 Advanced Workspace')
                        shared.gradio['aw_issue_text'] = gr.Textbox(label='Issue / Problem statement', lines=4, placeholder='Paste GitHub issue text or feature request...')
                        with gr.Row():
                            shared.gradio['aw_start_parallel_btn'] = gr.Button('🚀 Start Parallel Branch Executor')
                            shared.gradio['aw_quality_btn'] = gr.Button('🧪 Run Quality Gates')
                            shared.gradio['aw_synth_btn'] = gr.Button('🧩 Conflict-aware Synthesizer')
                        with gr.Row():
                            shared.gradio['aw_repo_map_btn'] = gr.Button('🗺️ Repo Map + Hotspots')
                            shared.gradio['aw_issue_plan_btn'] = gr.Button('📝 Issue → Plan')
                            shared.gradio['aw_strategy_template_btn'] = gr.Button('📚 Strategy Prompt Template')
                            shared.gradio['aw_pr_intel_btn'] = gr.Button('📊 PR Intelligence')
                            shared.gradio['aw_sync_main_btn'] = gr.Button('🔄 Sync Branches with main')
                            shared.gradio['aw_unified_pr_btn'] = gr.Button('📦 Prepare One Big Unified PR')

                        shared.gradio['aw_branch_list'] = gr.Textbox(label='Agent branches (comma-separated)', lines=2)
                        shared.gradio['aw_integration_branch'] = gr.Textbox(label='Integration branch', interactive=False)
                        shared.gradio['aw_timeline'] = gr.Textbox(label='Execution timeline', lines=6, interactive=False)
                        shared.gradio['aw_kanban'] = gr.JSON(label='Kanban board')
                        shared.gradio['aw_issue_plan'] = gr.Textbox(label='Issue decomposition + branch plan', lines=8)
                        shared.gradio['aw_strategy_template'] = gr.Textbox(label='Prompt template per strategy', lines=4)
                        shared.gradio['aw_pr_report'] = gr.Textbox(label='PR intelligence report', lines=8)
                        shared.gradio['aw_pr_body'] = gr.Textbox(label='Unified PR body draft', lines=8)
                        shared.gradio['aw_why_change'] = gr.Textbox(label='Why this change? (rationale + risk)', lines=4)
                        shared.gradio['aw_candidates'] = gr.Textbox(label='Model outputs for ensemble (one per line: model: answer)', lines=4)
                        with gr.Row():
                            shared.gradio['aw_ensemble_btn'] = gr.Button('🗳️ Model Ensemble Voting')
                            shared.gradio['aw_debate_btn'] = gr.Button('🗣️ Debate Mode Synthesizer')
                            shared.gradio['aw_cost_btn'] = gr.Button('💸 Cost/Speed Optimizer')
                        shared.gradio['aw_proposal'] = gr.Textbox(label='Debate proposal', lines=3)
                        shared.gradio['aw_critique'] = gr.Textbox(label='Debate critique', lines=3)
                        shared.gradio['aw_ensemble_report'] = gr.Textbox(label='Ensemble / Debate output', lines=6)
                        with gr.Row():
                            shared.gradio['aw_mem_decision'] = gr.Textbox(label='Memory bus decision')
                            shared.gradio['aw_mem_constraint'] = gr.Textbox(label='Memory bus constraint')
                            shared.gradio['aw_mem_todo'] = gr.Textbox(label='Memory bus TODO')
                        shared.gradio['aw_mem_btn'] = gr.Button('🧠 Update Shared Memory Bus')
                        shared.gradio['aw_mem_view'] = gr.Textbox(label='Memory bus snapshot', lines=6)
                        shared.gradio['aw_table'] = gr.Dataframe(
                            headers=['name', 'status', 'details'],
                            datatype=['str', 'str', 'str'],
                            row_count=8,
                            interactive=False,
                        )
                        shared.gradio['aw_repo_map_table'] = gr.Dataframe(
                            headers=['path', 'size_bytes'],
                            datatype=['str', 'str'],
                            row_count=12,
                            interactive=False,
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


    print("[info] registered shared.gradio keys:", list(shared.gradio.keys()))


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

    shared.gradio['gh_connect_btn'].click(
        github_connect,
        gradio('gh_repo_url', 'gh_repo_path', 'gh_base_branch', 'gh_token'),
        gradio('gh_status', 'gh_repo_path', 'gh_repo_url'),
        show_progress=False,
    )

    shared.gradio['gh_branch_btn'].click(
        github_create_branch,
        gradio('gh_task', 'mode', 'reasoning_effort', 'gh_repo_path', 'gh_base_branch'),
        gradio('gh_status', 'gh_branch', 'gh_task_file'),
        show_progress=False,
    )

    shared.gradio['gh_pr_btn'].click(
        github_open_pr,
        gradio('gh_repo_path', 'gh_branch', 'gh_pr_title', 'aw_pr_body'),
        gradio('gh_status', 'gh_pr_url'),
        show_progress=False,
    )

    shared.gradio['ai_team_prompt_btn'].click(
        build_multi_ai_prompt,
        gradio('gh_task', 'ai_team_count', 'ai_team_models', 'ai_team_strategy'),
        gradio('ai_team_prompt'),
        show_progress=False,
    )

    shared.gradio['gh_health_btn'].click(
        github_repo_health,
        gradio('gh_repo_path'),
        gradio('gh_status', 'gh_health_table'),
        show_progress=False,
    )

    shared.gradio['gh_team_tasks_btn'].click(
        github_create_multi_agent_tasks,
        gradio('gh_repo_path', 'gh_base_branch', 'gh_task', 'ai_team_count', 'ai_team_models', 'ai_team_strategy'),
        gradio('gh_status', 'gh_task_file'),
        show_progress=False,
    )


    shared.gradio['aw_start_parallel_btn'].click(
        start_parallel_executor_action,
        gradio('gh_repo_path', 'gh_base_branch', 'gh_task', 'ai_team_strategy', 'ai_team_count'),
        gradio('gh_status', 'aw_integration_branch', 'aw_branch_list', 'aw_timeline', 'aw_kanban', 'aw_table', 'aw_why_change'),
        show_progress=False,
    )

    shared.gradio['aw_quality_btn'].click(
        quality_gates_action,
        gradio('gh_repo_path', 'aw_integration_branch'),
        gradio('gh_status', 'aw_timeline', 'aw_table', 'aw_why_change'),
        show_progress=False,
    )

    shared.gradio['aw_synth_btn'].click(
        conflict_synth_action,
        gradio('gh_repo_path', 'aw_integration_branch', 'aw_branch_list'),
        gradio('gh_status', 'aw_timeline', 'aw_table', 'aw_why_change'),
        show_progress=False,
    )

    shared.gradio['aw_issue_plan_btn'].click(
        issue_plan_action,
        gradio('aw_issue_text', 'ai_team_strategy'),
        gradio('gh_status', 'aw_issue_plan'),
        show_progress=False,
    )


    shared.gradio['aw_strategy_template_btn'].click(
        strategy_template_action,
        gradio('ai_team_strategy'),
        gradio('aw_strategy_template'),
        show_progress=False,
    )


    shared.gradio['aw_repo_map_btn'].click(
        repo_map_action,
        gradio('gh_repo_path'),
        gradio('gh_status', 'aw_repo_map_table'),
        show_progress=False,
    )

    shared.gradio['aw_pr_intel_btn'].click(
        pr_intel_action,
        gradio('gh_repo_path', 'aw_integration_branch'),
        gradio('gh_status', 'aw_pr_report', 'aw_why_change'),
        show_progress=False,
    )

    shared.gradio['aw_sync_main_btn'].click(
        sync_main_action,
        gradio('gh_repo_path', 'aw_branch_list'),
        gradio('gh_status', 'aw_timeline', 'aw_table'),
        show_progress=False,
    )


    shared.gradio['aw_unified_pr_btn'].click(
        unified_pr_prep_action,
        gradio('gh_repo_path', 'aw_integration_branch', 'aw_branch_list', 'gh_pr_title', 'aw_issue_plan', 'aw_why_change'),
        gradio('gh_status', 'gh_pr_title', 'aw_pr_body'),
        show_progress=False,
    )



    shared.gradio['aw_ensemble_btn'].click(
        ensemble_vote_action,
        gradio('aw_candidates'),
        gradio('gh_status', 'aw_ensemble_report'),
        show_progress=False,
    )

    shared.gradio['aw_debate_btn'].click(
        debate_mode_action,
        gradio('aw_proposal', 'aw_critique'),
        gradio('aw_ensemble_report'),
        show_progress=False,
    )

    shared.gradio['aw_cost_btn'].click(
        cost_optimizer_action,
        gradio('gh_task', 'ai_team_models'),
        gradio('gh_status'),
        show_progress=False,
    )

    shared.gradio['aw_mem_btn'].click(
        memory_bus_action,
        gradio('gh_repo_path', 'aw_mem_decision', 'aw_mem_constraint', 'aw_mem_todo'),
        gradio('gh_status', 'aw_mem_view'),
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
