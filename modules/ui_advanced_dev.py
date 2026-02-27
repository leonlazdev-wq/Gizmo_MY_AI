"""Advanced Developer Tools UI.

Exposes the Multi-Agent Dev Team, AST semantic search, Auto-Debugger,
and GitHub PR management features in a single Gradio tab.
"""

from __future__ import annotations

import gradio as gr

from modules.ast_engine import index_directory, semantic_search, build_context_string
from modules.dev_team import full_dev_team_pipeline
from modules.auto_debugger import analyze_and_fix
from modules.auto_fix_loop import autonomous_loop
from modules.github_pr_manager import analyze_pull_request


def create_ui():
    """Build the Advanced Auto-Dev UI tab."""
    with gr.Tab("👨‍💻 Auto-Dev Team", id="advanced_dev"):
        gr.Markdown("### Autonomous AI Software Engineer\n\nBuild, test, debug, and review code using a multi-agent system (Architect, Coder, Reviewer).")

        # -------------------------------------------------------------
        # Section 1: The Dev Team Orchestrator
        # -------------------------------------------------------------
        with gr.Accordion("🛠️ Feature Builder (Multi-Agent Team)", open=True):
            with gr.Row():
                with gr.Column(scale=1):
                    dev_project_dir = gr.Textbox(label="Local Project Path (Optional for AST Context)", placeholder="C:/Projects/MyStore")
                    dev_prompt = gr.Textbox(label="Feature Request", lines=4, placeholder="e.g. Build an asynchronous rate limiter for the auth module.")
                    dev_btn = gr.Button("Deploy Dev Team", variant="primary")
                
                with gr.Column(scale=2):
                    dev_architect_out = gr.Textbox(label="1. Architect Blueprint (Chain of Thought)", lines=6, interactive=False)
                    dev_coder_out = gr.Textbox(label="2. Coder Implementation", lines=10, interactive=False)
                    dev_reviewer_out = gr.Textbox(label="3. Reviewer Feedback", lines=5, interactive=False)

        # -------------------------------------------------------------
        # Section 2: Intelligent Auto-Debugger
        # -------------------------------------------------------------
        with gr.Accordion("🪲 Intelligent Auto-Debugger", open=False):
            gr.Markdown("Paste a Python traceback. The AI will locate the local file, analyze the crash context, and generate a unified diff fix.")
            with gr.Row():
                with gr.Column(scale=1):
                    debug_tb = gr.Textbox(label="Traceback Log", lines=8, placeholder='File "app.py", line 42...')
                    debug_btn = gr.Button("Diagnose & Fix", variant="primary")
                with gr.Column(scale=1):
                    debug_out = gr.Textbox(label="AI Diagnosis & Patch", lines=12, interactive=False)

        # -------------------------------------------------------------
        # Section 3: The Auto-Fix Loop (Autonomous Tester)
        # -------------------------------------------------------------
        with gr.Accordion("🔄 The Auto-Fix Loop (Piston Sandbox)", open=False):
            gr.Markdown("The AI will write code, execute it securely in the Piston Sandbox, catch its own errors, and rewrite until the tests pass.")
            with gr.Row():
                with gr.Column(scale=1):
                    loop_prompt = gr.Textbox(label="Code Prompt", lines=4, placeholder="Write a function to calculate Fibonacci series up to N and print the result for N=10")
                    loop_lang = gr.Dropdown(["python", "javascript", "typescript", "go", "rust"], value="python", label="Language")
                    loop_btn = gr.Button("Run Auto-Fix Loop (Max 3 Tries)", variant="primary")
                with gr.Column(scale=2):
                    loop_status = gr.Textbox(label="Loop Status", interactive=False)
                    loop_code = gr.Textbox(label="Final Working Code", lines=8, interactive=False)
                    loop_output = gr.Textbox(label="Execution Output", lines=5, interactive=False)

        # -------------------------------------------------------------
        # Section 4: GitHub PR Reviewer
        # -------------------------------------------------------------
        with gr.Accordion("🐙 GitHub PR Reviewer", open=False):
            gr.Markdown("The AI `Reviewer` agent will analyze a Pull Request diff for security and stylistic issues.")
            with gr.Row():
                with gr.Column(scale=1):
                    pr_token = gr.Textbox(label="GitHub PAT", type="password")
                    pr_repo = gr.Textbox(label="Repository (e.g. torvalds/linux)", placeholder="owner/repo")
                    pr_num = gr.Number(label="Pull Request #", precision=0)
                    pr_btn = gr.Button("Analyze PR", variant="primary")
                with gr.Column(scale=2):
                    pr_status = gr.Textbox(label="PR Status", interactive=False)
                    pr_critique = gr.Textbox(label="AI Code Review", lines=10, interactive=False)


    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------
    
    # 1. Pipeline
    def run_dev_team(prompt, dir_path):
        context = "No local context provided."
        if dir_path and dir_path.strip():
            # Run the AST semantic search
            index = index_directory(dir_path.strip())
            nodes = semantic_search(prompt, index)
            context = build_context_string(nodes)

        results = full_dev_team_pipeline(prompt, context)
        
        if "error" in results:
            return results["error"], "", ""
        
        return results.get("blueprint", ""), results.get("code", ""), results.get("review", "")

    dev_btn.click(
        fn=run_dev_team,
        inputs=[dev_prompt, dev_project_dir],
        outputs=[dev_architect_out, dev_coder_out, dev_reviewer_out],
        api_name="dev_team"
    )

    # 2. Debugger
    def run_debugger(tb_text):
        if not tb_text.strip():
            return "Please provide a traceback."
        msg, err = analyze_and_fix(tb_text)
        return err if err else msg
        
    debug_btn.click(
        fn=run_debugger,
        inputs=[debug_tb],
        outputs=[debug_out],
        api_name="auto_debug"
    )

    # 3. Auto-Fix Loop
    def run_loop(prompt, lang):
        if not prompt.strip():
            return "Please provide a prompt.", "", ""
        
        res = autonomous_loop(prompt, language=lang, max_retries=3)
        
        if res["status"] == "error":
            return f"Error: {res.get('message', 'Unknown error')}", "", ""
            
        status_str = f"Status: {res['status'].upper()} (took {res['iterations']} iterations)\n\n"
        for h in res.get("history", []):
            status_str += f"Attempt {h['attempt']}: {h['action']}\n"
            
        return status_str, res.get("final_code", ""), res.get("execution_output", res.get("message", ""))

    loop_btn.click(
        fn=run_loop,
        inputs=[loop_prompt, loop_lang],
        outputs=[loop_status, loop_code, loop_output],
        api_name="auto_fix"
    )

    # 4. GitHub PR
    def run_pr_review(token, repo, pr_num):
        if not repo or not pr_num:
            return "Repository and PR number required.", ""
        msg, data = analyze_pull_request(repo, int(pr_num), token)
        if "❌" in msg:
            return msg, ""
            
        status = f"{msg}\nTitle: {data.get('title')}\nAuthor: {data.get('author')}\nSummary: {data.get('diff_summary')}"
        return status, data.get("critique", "No critique generated.")

    pr_btn.click(
        fn=run_pr_review,
        inputs=[pr_token, pr_repo, pr_num],
        outputs=[pr_status, pr_critique],
        api_name="pr_review"
    )

