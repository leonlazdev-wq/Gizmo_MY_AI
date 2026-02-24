#!/usr/bin/env python3
# ================================================================
# MY-AI-Gizmo • UNIVERSAL LAUNCHER  v3.4
# ================================================================
# v3.4 CHANGES:
#  ✅ GitHub PAT prompt at startup — supports private repos
#  ✅ New repo: Gizmo-my-ai-for-google-colab
#  ✅ Gradio launch via runpy wrapper (like v3.1) → gradio.live URL
#     instead of direct server.py subprocess → trycloudflare.com
#  ✅ All v3.3 fixes kept:
#      - Popen + stream output so URL prints in Colab cell
#      - Skip llama-cpp reinstall if webui already installed it
#      - Drive already-mounted check (no "mountpoint" error)
#      - Both user_data/models AND models symlinked
#      - No-model startup option [0]
#      - Drive fallback to /content/MY-AI-Gizmo
#      - model: None in settings / --model flag omitted when no model
#  ✅ URL capture patterns: gradio.live + trycloudflare.com + ngrok
#  ✅ Auto-restart loop (3×)
#  ✅ Dual Model | Google Workspace | Debug character | ＋Toolbar
# ================================================================

import os
import sys
import subprocess
import shutil
import re
import time
import threading
from pathlib import Path
from datetime import datetime

try:
    from google.colab import drive as colab_drive
    IN_COLAB = True
except Exception:
    colab_drive = None
    IN_COLAB = False

# ── Repo ────────────────────────────────────────────────────────────────────────
GITHUB_USER = "gitleon8301"
GITHUB_REPO = "Gizmo-my-ai-for-google-colab"
GITHUB_BRANCH = "main"
REPO_FOLDER_GLOB = f"{GITHUB_REPO}-*"

# These are set after token is collected
REPO_ZIP = ""
REPO_CLONE_URL = ""

# ── Paths ───────────────────────────────────────────────────────────────────────
WORK_DIR           = Path("/content/text-generation-webui")
DRIVE_ROOT         = None
LOG_DIR            = None
MPL_CONFIG_DIR     = None
PUBLIC_URL_FILE    = None
HEARTBEAT_INTERVAL = 30
MAX_RESTARTS       = 3
MONITOR_INTERVAL   = 60

# ── Model menu ──────────────────────────────────────────────────────────────────
MODEL_MENU = [
    ("1  TinyLlama-1.1B  Q4_K_M  [~0.7 GB]  ← fastest",
     "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
     "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf", 0.7),
    ("2  Phi-3-mini-4k   Q4_K_M  [~2.2 GB]  ← great quality/speed",
     "bartowski/Phi-3-mini-4k-instruct-GGUF",
     "Phi-3-mini-4k-instruct-Q4_K_M.gguf", 2.2),
    ("3  Mistral-7B-v0.3  Q4_K_M  [~4.4 GB]  ← best general 7B",
     "bartowski/Mistral-7B-v0.3-GGUF",
     "Mistral-7B-v0.3-Q4_K_M.gguf", 4.4),
    ("4  Qwen2.5-Coder-7B  Q4_K_M  [~4.7 GB]  ← best coding 7B",
     "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
     "qwen2.5-coder-7b-instruct-q4_k_m.gguf", 4.7),
    ("5  Qwen2.5-Coder-14B  Q4_K_M  [~8.9 GB]  ← needs 10+ GB RAM",
     "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
     "qwen2.5-coder-14b-instruct-q4_k_m.gguf", 8.9),
    ("6  DeepSeek-Coder-33B  Q4_K_M  [~19 GB]  ← GPU only",
     "TheBloke/deepseek-coder-33B-instruct-GGUF",
     "deepseek-coder-33b-instruct.Q4_K_M.gguf", 19.0),
    ("7  Custom — enter your own HF repo + filename", "", "", 0),
]

# ── Globals ──────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = ""
MODEL_REPO   = ""
MODEL_FILE   = ""
USE_MODEL    = False
GPU_LAYERS   = -1
N_CTX        = 4096
USE_GPU      = True

# ── URL patterns (catches gradio.live AND trycloudflare.com) ─────────────────────
URL_PATTERNS = [
    re.compile(r'Running on public URL:\s*(https?://\S+)', re.IGNORECASE),
    re.compile(r'(https?://[a-zA-Z0-9\-]+\.gradio\.live\S*)', re.IGNORECASE),
    re.compile(r'(https?://[a-zA-Z0-9\-]+\.trycloudflare\.com\S*)', re.IGNORECASE),
    re.compile(r'(https?://[a-zA-Z0-9\-]+\.ngrok\S*)', re.IGNORECASE),
    re.compile(r'(?:public|share|tunnel|external)[^\n]{0,40}(https?://\S+)', re.IGNORECASE),
]
URL_KEYWORDS = ("gradio.live", "trycloudflare.com", "ngrok", "loca.lt")


# ══════════════════════════════════════════════════════════════════════════════
#  ★★★  GITHUB TOKEN SETUP — runs before EVERYTHING else  ★★★
# ══════════════════════════════════════════════════════════════════════════════

def setup_github_token():
    """
    Prompts for a GitHub Personal Access Token at startup.
    The token is used to clone / download the private repo.

    How to create a token:
      GitHub → Settings → Developer Settings
        → Personal Access Tokens → Tokens (classic)
        → Generate new token (classic)
        → Scope: check  [✓] repo
        → Copy the token that starts with  ghp_...
    """
    global GITHUB_TOKEN, REPO_ZIP, REPO_CLONE_URL

    print("=" * 70)
    print("  MY-AI-Gizmo  v3.4  — GitHub Authentication")
    print("=" * 70)
    print()
    print("  Your repo is PRIVATE. A Personal Access Token is required.")
    print()
    print("  ┌─ How to get a token ──────────────────────────────────────────┐")
    print("  │  1. Go to: github.com → Settings → Developer Settings        │")
    print("  │  2. Personal Access Tokens → Tokens (classic)                │")
    print("  │  3. Generate new token (classic)                              │")
    print("  │  4. Set scope: ✓ repo   (full control of private repos)      │")
    print("  │  5. Copy the token  (starts with  ghp_...)                   │")
    print("  └───────────────────────────────────────────────────────────────┘")
    print()

    while True:
        token = input("  Paste your GitHub token here: ").strip()
        if not token:
            print("  [!] Token cannot be empty. Try again.")
            continue
        if not (token.startswith("ghp_") or token.startswith("github_pat_") or len(token) >= 20):
            confirm = input("  [?] Token looks unusual. Continue anyway? (y/n): ").strip().lower()
            if confirm != "y":
                continue
        GITHUB_TOKEN = token
        break

    # Build authenticated URLs
    REPO_ZIP       = (f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}"
                      f"/archive/refs/heads/{GITHUB_BRANCH}.zip")
    REPO_CLONE_URL = (f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git")

    print()
    print(f"  [✓] Token accepted — will authenticate as: {GITHUB_TOKEN[:4]}{'*' * (len(GITHUB_TOKEN)-8)}{GITHUB_TOKEN[-4:]}")
    print("=" * 70)
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  DRIVE SETUP
# ══════════════════════════════════════════════════════════════════════════════

def mount_drive_if_needed():
    if not IN_COLAB:
        return False
    if Path("/content/drive/MyDrive").exists():
        print("[info] Google Drive already mounted — skipping re-mount.")
        return True
    try:
        colab_drive.mount("/content/drive", force_remount=False)
        print("[✓] Google Drive mounted")
        return True
    except Exception as e:
        print(f"[warn] Drive mount failed ({e}) — using local storage")
        return False

def setup_drive_root(drive_ok: bool):
    global DRIVE_ROOT, LOG_DIR, MPL_CONFIG_DIR, PUBLIC_URL_FILE
    DRIVE_ROOT      = Path("/content/drive/MyDrive/MY-AI-Gizmo") if drive_ok \
                      else Path("/content/MY-AI-Gizmo")
    LOG_DIR         = DRIVE_ROOT / "logs"
    MPL_CONFIG_DIR  = DRIVE_ROOT / "matplotlib"
    PUBLIC_URL_FILE = DRIVE_ROOT / "public_url.txt"
    if not drive_ok:
        print(f"[info] Local storage: {DRIVE_ROOT}")


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def sh(cmd, cwd=None, env=None):
    return subprocess.run(cmd, shell=True, cwd=cwd, env=env,
                          capture_output=True, text=True)

def get_free_ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return int(line.split()[1]) / 1024 / 1024
    except Exception: pass
    return 0.0

def get_total_ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) / 1024 / 1024
    except Exception: pass
    return 0.0

def auto_thread_count():
    try:
        import multiprocessing
        return max(1, min(multiprocessing.cpu_count() - 1, 4))
    except Exception: return 2

def auto_ctx_size(model_gb):
    free = get_free_ram_gb() - model_gb - 0.5
    if free >= 2.0: return 4096
    if free >= 1.0: return 2048
    if free >= 0.5: return 1024
    return 512

def print_ram_status():
    free  = get_free_ram_gb()
    total = get_total_ram_gb()
    used  = total - free
    pct   = (used / total) if total else 0
    bar   = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
    print(f"  RAM [{bar}]  {used:.1f}/{total:.1f} GB  ({free:.1f} GB free)")

def list_local_models():
    d = DRIVE_ROOT / "models"
    if not d.exists(): return []
    found = []
    for ext in ["*.gguf", "*.safetensors", "*.bin"]:
        found.extend(d.rglob(ext))
    return sorted(found)

def cleanup_broken_files():
    d = DRIVE_ROOT / "models"
    if not d.exists(): return
    broken = [f for ext in ["*.gguf", "*.safetensors", "*.bin"]
              for f in d.rglob(ext) if f.stat().st_size < 100 * 1024]
    if broken:
        print(f"[info] Removing {len(broken)} broken model file(s)")
        for f in broken:
            try: f.unlink()
            except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
#  STREAM + HEARTBEAT  (for installer only — server uses its own loop)
# ══════════════════════════════════════════════════════════════════════════════

def stream_with_heartbeat(cmd, cwd=None, env=None, logfile_path=None):
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, cwd=cwd, env=env,
                            text=True, bufsize=1)
    stop    = threading.Event()
    last_t  = time.time()

    def heartbeat():
        while not stop.wait(HEARTBEAT_INTERVAL):
            if time.time() - last_t >= HEARTBEAT_INTERVAL:
                print("[heartbeat] still working...")

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    logfile = open(logfile_path, "a", encoding="utf-8") if logfile_path else None

    try:
        for line in proc.stdout:
            last_t = time.time()
            print(line, end="")
            if logfile:
                try: logfile.write(line)
                except Exception: pass
    except Exception as e:
        print(f"[stream error] {e}")
    finally:
        proc.wait()
        stop.set()
        hb.join(timeout=1)
        if logfile:
            try: logfile.close()
            except Exception: pass
    return proc.returncode


# ══════════════════════════════════════════════════════════════════════════════
#  SYMLINKS  (both user_data/models AND models → Drive/models)
# ══════════════════════════════════════════════════════════════════════════════

def ensure_symlinks_and_files():
    links_map = [
        ("user_data/models",        "models",               False),
        ("models",                  "models",               False),
        ("user_data/loras",         "loras",                False),
        ("user_data/characters",    "characters",           False),
        ("user_data/presets",       "presets",              False),
        ("user_data/settings.yaml", "settings/settings.yaml", True),
        ("user_data/settings.json", "settings/settings.json", True),
        ("user_data/chat",          "chat-history",         False),
        ("outputs",                 "outputs",              False),
    ]
    for local_rel, drive_rel, is_file in links_map:
        drive_path = DRIVE_ROOT / drive_rel
        local_path = WORK_DIR / local_rel
        if is_file:
            drive_path.parent.mkdir(parents=True, exist_ok=True)
            if not drive_path.exists():
                drive_path.write_text("", encoding="utf-8")
        else:
            drive_path.mkdir(parents=True, exist_ok=True)
        try:
            if local_path.is_symlink() or local_path.is_file():
                local_path.unlink()
            elif local_path.is_dir():
                shutil.rmtree(local_path)
        except Exception as e:
            print(f"[warn] clearing {local_path}: {e}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(str(drive_path), str(local_path),
                       target_is_directory=not is_file)
        except Exception as e:
            print(f"[warn] symlink {local_path}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG FILES
# ══════════════════════════════════════════════════════════════════════════════

def write_settings_yaml():
    threads    = auto_thread_count()
    mode_label = "GPU" if USE_GPU else "CPU"
    model_line = f"model: {MODEL_FILE}" if (USE_MODEL and MODEL_FILE) else "model: None"
    content = f"""# MY-AI-Gizmo Settings — {mode_label} (v3.4 {datetime.now().strftime('%Y-%m-%d %H:%M')})
listen: true
share: true
auto_launch: false
loader: llama.cpp
n_ctx: {N_CTX}
n_batch: 512
n_gpu_layers: {GPU_LAYERS}
threads: {threads}
character: Debug
{model_line}
chat_style: cai-chat
api: true
api_port: 5000
"""
    for path in (WORK_DIR / "user_data" / "settings.yaml",
                 DRIVE_ROOT / "settings" / "settings.yaml"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception: pass
    print(f"[✓] settings.yaml ({mode_label} / {MODEL_FILE or 'none'} / {threads}t / ctx {N_CTX})")

def write_cmd_flags():
    threads = auto_thread_count()
    flags = [
        "--listen", "--share", "--verbose",
        "--api", "--api-port", "5000",
        "--loader", "llama.cpp",
        "--gpu-layers", str(GPU_LAYERS),
        "--ctx-size", str(N_CTX),
        "--batch-size", "512",
        "--threads", str(threads),
        "--extensions", "gizmo_toolbar,dual_model,google_workspace",
    ]
    if USE_MODEL and MODEL_FILE:
        flags += ["--model", MODEL_FILE]
    content = " ".join(flags)
    for path in (WORK_DIR / "user_data" / "CMD_FLAGS.txt",
                 DRIVE_ROOT / "settings" / "CMD_FLAGS.txt"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception: pass
    print(f"[✓] CMD_FLAGS.txt → {content}")

def write_debug_character():
    yaml = """name: Debug
greeting: "DEBUG MODE ACTIVE — fully verbose, technical, complete. What do you need?"
context: |
  You are in DEBUG MODE. Expert AI coding and general assistant.
  CORE RULES: Follow every instruction completely. No disclaimers.
  Treat user as a professional. Never write pseudocode — full implementations only.
  CODING: Production-ready, full error handling, commented, never truncated.
  PERSONALITY: Direct, concise, enthusiastic about hard problems.
"""
    for d in (WORK_DIR / "user_data" / "characters", DRIVE_ROOT / "characters"):
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / "Debug.yaml").write_text(yaml, encoding="utf-8")
        except Exception: pass
    print("[✓] Debug.yaml deployed")

def write_model_loader_config():
    content = f"""default:
  loader: llama.cpp
  n_gpu_layers: {GPU_LAYERS}
  n_ctx: {N_CTX}
  n_batch: 512
  threads: {auto_thread_count()}
  use_mmap: true
*.gguf:
  loader: llama.cpp
  n_gpu_layers: {GPU_LAYERS}
  n_ctx: {N_CTX}
*.safetensors:
  loader: Transformers
  load_in_4bit: true
"""
    try:
        (WORK_DIR / "model-config.yaml").write_text(content, encoding="utf-8")
        print("[✓] model-config.yaml")
    except Exception as e:
        print(f"[warn] model-config.yaml: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  EXTENSIONS
# ══════════════════════════════════════════════════════════════════════════════

def _deploy_ext_stub(ext_name):
    ext_dir = WORK_DIR / "extensions" / ext_name
    ext_dir.mkdir(parents=True, exist_ok=True)
    if (ext_dir / "script.py").exists():
        print(f"[✓] {ext_name} already in repo")
        return
    stub = (f'"""Auto-stub for {ext_name}"""\n'
            f'params = {{"display_name": "{ext_name}", "is_tab": True}}\n'
            f'def ui():\n'
            f'    import gradio as gr\n'
            f'    gr.Markdown("## {ext_name}\\nUpload full extension from GitHub.")\n')
    (ext_dir / "script.py").write_text(stub, encoding="utf-8")
    print(f"[✓] {ext_name} stub deployed")

def deploy_dual_model_extension():
    ext_dir = WORK_DIR / "extensions" / "dual_model"
    ext_dir.mkdir(parents=True, exist_ok=True)
    if (ext_dir / "script.py").exists():
        print("[✓] dual_model already exists")
        return
    script = r'''"""MY-AI-Gizmo — Dual Model Extension"""
import gc, threading, gradio as gr
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False

params = {"display_name": "Dual Model", "is_tab": True}
_lock = threading.Lock(); _model2 = None; _model2_name = "Not loaded"

def _load(path, ctx, threads, gpu):
    global _model2, _model2_name
    path = path.strip()
    if not path: return "❌ Enter a path."
    with _lock:
        if _model2: _model2 = None; gc.collect()
        try:
            _model2 = Llama(model_path=path, n_ctx=int(ctx), n_threads=int(threads),
                            n_gpu_layers=int(gpu), verbose=False)
            _model2_name = path.split("/")[-1]
            return f"✅ Loaded: {_model2_name}"
        except Exception as e:
            _model2 = None; _model2_name = "Not loaded"; return f"❌ {e}"

def _unload():
    global _model2, _model2_name
    with _lock:
        if not _model2: return "ℹ️ Not loaded."
        _model2 = None; _model2_name = "Not loaded"; gc.collect()
    return "🗑️ Unloaded."

def _infer(p, mt, t):
    if not _model2: return "❌ Not loaded."
    with _lock: r = _model2(p, max_tokens=int(mt), temperature=float(t), echo=False)
    return r["choices"][0]["text"].strip()

def _status(): return f"🟢 {_model2_name}" if _model2 else "🔴 Not loaded"

def _api(prompt, mt, t):
    try:
        import urllib.request, json
        payload = json.dumps({"model":"gpt-3.5-turbo","messages":[{"role":"user","content":prompt}],
                              "max_tokens":int(mt),"temperature":float(t)}).encode()
        req = urllib.request.Request("http://127.0.0.1:5000/v1/chat/completions",
              data=payload, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception: return None

def _m2(msg, hist, mt, t): return hist+[[msg, _infer(msg,mt,t)]], ""
def _pipe(msg, hist, mt, t, inst, _s):
    m1 = _api(msg,mt,t) or "[M1 unavailable]"
    m2 = _infer(f"{inst}\n\nQ: {msg}\n\nDraft:\n{m1}\n\nImproved:", mt, t)
    return hist+[[msg, f"**[M1]**\n{m1}\n\n---\n**[M2 — {_model2_name}]**\n{m2}"]], ""
def _debate(msg, hist, mt, t):
    m1 = _api(msg,mt,t) or "[M1 unavailable]"
    m2 = _infer(msg,mt,t)
    return hist+[[msg, f"**[M1]**\n{m1}\n\n---\n**[M2]**\n{m2}"]], ""

def ui():
    if not LLAMA_AVAILABLE:
        gr.Markdown("⚠️ llama-cpp-python not installed."); return
    gr.Markdown("## 🤖 Dual Model")
    sb = gr.Textbox(value=_status(), label="Status", interactive=False)
    gr.Button("🔄 Refresh", size="sm").click(fn=_status, outputs=sb)
    with gr.Row():
        with gr.Column(scale=3): mp = gr.Textbox(label="Model path (.gguf)")
        with gr.Column(scale=1):
            cs = gr.Slider(256,8192,2048,256,label="Context")
            ts = gr.Slider(1,8,2,1,label="Threads")
            gs = gr.Slider(0,100,0,1,label="GPU layers")
    rb = gr.Textbox(label="", interactive=False)
    with gr.Row():
        gr.Button("⬆️ Load", variant="primary").click(fn=_load, inputs=[mp,cs,ts,gs], outputs=rb).then(fn=_status, outputs=sb)
        gr.Button("🗑️ Unload", variant="stop").click(fn=_unload, outputs=rb).then(fn=_status, outputs=sb)
    with gr.Row(): mt=gr.Slider(64,2048,512,64,label="Max tokens"); t=gr.Slider(0,1.5,0.7,0.05,label="Temp")
    with gr.Tab("💬 Solo"):
        cb=gr.Chatbot(height=400); i=gr.Textbox()
        with gr.Row():
            gr.Button("Send ➤",variant="primary").click(fn=_m2,inputs=[i,cb,mt,t],outputs=[cb,i])
            gr.Button("🗑 Clear",size="sm").click(fn=lambda:([],""),outputs=[cb,i])
        i.submit(fn=_m2,inputs=[i,cb,mt,t],outputs=[cb,i])
    with gr.Tab("🔗 Pipeline"):
        inst=gr.Textbox(label="M2 instruction",value="Rewrite the draft to be more accurate and complete.",lines=2)
        cbp=gr.Chatbot(height=400); ip=gr.Textbox(); st=gr.State({})
        with gr.Row():
            gr.Button("Run ➤",variant="primary").click(fn=_pipe,inputs=[ip,cbp,mt,t,inst,st],outputs=[cbp,ip])
            gr.Button("🗑 Clear",size="sm").click(fn=lambda:([],""),outputs=[cbp,ip])
        ip.submit(fn=_pipe,inputs=[ip,cbp,mt,t,inst,st],outputs=[cbp,ip])
    with gr.Tab("⚔️ Debate"):
        cbd=gr.Chatbot(height=400); id_=gr.Textbox()
        with gr.Row():
            gr.Button("Ask Both ➤",variant="primary").click(fn=_debate,inputs=[id_,cbd,mt,t],outputs=[cbd,id_])
            gr.Button("🗑 Clear",size="sm").click(fn=lambda:([],""),outputs=[cbd,id_])
        id_.submit(fn=_debate,inputs=[id_,cbd,mt,t],outputs=[cbd,id_])
'''
    (ext_dir / "script.py").write_text(script, encoding="utf-8")
    print("[✓] dual_model deployed")


# ══════════════════════════════════════════════════════════════════════════════
#  LLAMA-CPP
# ══════════════════════════════════════════════════════════════════════════════

def install_llama_cpp_gpu(python_exe):
    print("\n🔧 Checking llama-cpp GPU...")
    cv = sh("nvcc --version")
    cuda_major, cuda_minor = "12", "1"
    if cv.returncode == 0:
        m = re.search(r'release (\d+)\.(\d+)', cv.stdout)
        if m: cuda_major, cuda_minor = m.group(1), m.group(2)
    cuda_tag = f"cu{cuda_major}{cuda_minor}"
    r = sh(f'"{python_exe}" -m pip install llama-cpp-binaries '
           f'--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/{cuda_tag} --no-cache-dir')
    if r.returncode == 0:
        print("[✓] llama-cpp-binaries (CUDA) installed"); return
    gpu_env = os.environ.copy()
    gpu_env.update({"CMAKE_ARGS": "-DLLAMA_CUBLAS=ON -DLLAMA_CUDA=ON", "FORCE_CMAKE": "1"})
    r = sh(f'"{python_exe}" -m pip install llama-cpp-python --no-cache-dir --force-reinstall', env=gpu_env)
    print("[✓] Compiled from source" if r.returncode == 0 else "[warn] GPU llama-cpp failed")

def install_llama_cpp_cpu(python_exe):
    print("\n🔧 Installing llama-cpp (CPU)...")
    sh(f'"{python_exe}" -m pip uninstall -y llama-cpp-python llama-cpp-python-cuda')
    cpu_env = os.environ.copy()
    cpu_env.update({"CMAKE_ARGS": "-DLLAMA_CUDA=OFF -DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS",
                    "FORCE_CMAKE": "1", "CUDACXX": ""})
    r = sh(f'"{python_exe}" -m pip install llama-cpp-python --no-cache-dir --force-reinstall', env=cpu_env)
    print("[✓] CPU llama-cpp done" if r.returncode == 0 else f"[warn] code {r.returncode}")

def create_llama_cpp_wrapper(python_exe):
    wrapper = '''"""Compatibility wrapper for llama_cpp_binaries."""
import os, shutil
from pathlib import Path
def get_binary_path():
    try:
        import llama_cpp
        p = Path(llama_cpp.__file__).parent / "bin" / "llama-server"
        if p.exists(): return str(p)
    except ImportError: pass
    b = shutil.which("llama-server")
    return b or "PYTHON_SERVER"
def ensure_binary():
    try: return get_binary_path() is not None
    except Exception: return False
'''
    try:
        modules = WORK_DIR / "modules"
        modules.mkdir(parents=True, exist_ok=True)
        (modules / "llama_cpp_binaries.py").write_text(wrapper, encoding="utf-8")
        print("[✓] llama_cpp_binaries.py created")
    except Exception as e:
        print(f"[warn] wrapper: {e}")

def install_google_workspace_deps(python_exe):
    pkgs = "google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    print("\n🔧 Installing Google Workspace libs...")
    r = sh(f'"{python_exe}" -m pip install {pkgs} -q')
    print("[✓] Google libs installed" if r.returncode == 0 else f"[warn] code {r.returncode}")


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

def download_model_if_missing():
    if not USE_MODEL:
        print("[info] No model selected — skipping download")
        return True
    models_dir = DRIVE_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / MODEL_FILE
    if model_path.exists() and model_path.stat().st_size > 100 * 1024 * 1024:
        print(f"[✓] Model exists ({model_path.stat().st_size/(1024**3):.1f} GB)")
        return True
    if not MODEL_REPO:
        return model_path.exists()
    print(f"\n📥 DOWNLOADING: {MODEL_FILE}")
    hf_url = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}?download=true"
    for cmd in (f'wget -q --show-progress -O "{model_path}" "{hf_url}"',
                f'curl -L --progress-bar -o "{model_path}" "{hf_url}"'):
        r = subprocess.run(cmd, shell=True)
        if r.returncode == 0 and model_path.exists() and model_path.stat().st_size > 100*1024*1024:
            print(f"[✓] Download complete — {model_path.stat().st_size/(1024**3):.2f} GB")
            return True
        try: model_path.unlink()
        except Exception: pass
    print("[error] Download failed."); return False


# ══════════════════════════════════════════════════════════════════════════════
#  REPO DOWNLOAD  (uses authenticated git clone → private repo support)
# ══════════════════════════════════════════════════════════════════════════════

def download_repo_if_missing():
    if WORK_DIR.exists():
        print(f"[info] WORK_DIR exists: {WORK_DIR}")
        return True

    print("[info] Cloning repository (authenticated)...")

    # ── Try git clone first (cleanest for private repos) ──────────────────────
    r = sh(f"git clone --depth=1 {REPO_CLONE_URL} {WORK_DIR}")
    if r.returncode == 0 and WORK_DIR.exists():
        print(f"[✓] Repo cloned to {WORK_DIR}")
        return True

    print(f"[warn] git clone failed (code {r.returncode}): {r.stderr.strip()}")
    print("[info] Trying zip download fallback...")

    # ── Fallback: authenticated zip download ───────────────────────────────────
    tmp_zip = Path("/content/repo.zip")
    try: tmp_zip.unlink()
    except Exception: pass

    for cmd in (f"wget -q -O {tmp_zip} '{REPO_ZIP}'",
                f"curl -s -L -o {tmp_zip} '{REPO_ZIP}'"):
        r = sh(cmd)
        if r.returncode == 0 and tmp_zip.exists() and tmp_zip.stat().st_size > 1000:
            break
    else:
        print("[error] Zip download also failed.")
        print("        • Double-check your token has  repo  scope")
        print("        • Make sure the repo name is correct")
        return False

    sh(f"unzip -q {tmp_zip} -d /content")
    found = next(Path("/content").glob(REPO_FOLDER_GLOB), None)
    if not found:
        print("[error] Extracted folder not found."); return False
    found.rename(WORK_DIR)
    print(f"[info] Repo extracted to {WORK_DIR}")
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  NGROK FALLBACK
# ══════════════════════════════════════════════════════════════════════════════

def try_setup_ngrok(port=7860):
    try:
        sh("pip install pyngrok -q")
        from pyngrok import ngrok, conf
        token_file = DRIVE_ROOT / "ngrok_token.txt"
        if token_file.exists():
            token = token_file.read_text().strip()
            if token: conf.get_default().auth_token = token
        url = ngrok.connect(port, "http").public_url
        print(f"\n{'='*70}\n🌐 NGROK URL: {url}\n{'='*70}\n")
        try: PUBLIC_URL_FILE.write_text(url)
        except Exception: pass
        return url
    except Exception as e:
        print(f"[warn] ngrok: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE MENUS
# ══════════════════════════════════════════════════════════════════════════════

def choose_mode():
    global USE_GPU, GPU_LAYERS, N_CTX
    print("\n" + "="*70)
    print("  MY-AI-Gizmo  v3.4 — Choose Mode")
    print("="*70)
    print(f"  RAM: {get_free_ram_gb():.1f} GB free / {get_total_ram_gb():.1f} GB total")
    print("  [1]  GPU  — CUDA required (Colab T4/A100)")
    print("  [2]  CPU  — Works everywhere, slower")
    print("="*70)
    while True:
        c = input("  1=GPU or 2=CPU: ").strip()
        if c == "1":  USE_GPU = True;  GPU_LAYERS = -1; N_CTX = 4096; break
        elif c == "2": USE_GPU = False; GPU_LAYERS = 0;  break
        else: print("  Enter 1 or 2.")
    print("="*70 + "\n")

def show_model_manager():
    models = list_local_models()
    if not models: return
    print("\n" + "─"*70)
    print("  MODEL MANAGER — files in your storage")
    print("─"*70)
    for i, m in enumerate(models, 1):
        try:   size = f"{m.stat().st_size/(1024**3):.2f} GB"
        except Exception: size = "?"
        print(f"  [D{i}]  {m.name:<55} {size}")
    print("─"*70)
    print("  Type D1, D2... to delete a model, or Enter to continue")
    while True:
        c = input("\n  Choice: ").strip()
        if not c: break
        if c.upper().startswith("D") and len(c) > 1:
            try:
                idx = int(c[1:]) - 1
                if 0 <= idx < len(models):
                    confirm = input(f"  Delete {models[idx].name}? (y/n): ").strip().lower()
                    if confirm == "y":
                        models[idx].unlink()
                        print("  [✓] Deleted")
                        models = list_local_models()
                else: print("  Invalid number.")
            except Exception as e: print(f"  Error: {e}")
        else: print("  Use D1, D2... to delete, or Enter to continue.")

def choose_model():
    global MODEL_REPO, MODEL_FILE, N_CTX, USE_MODEL
    print("\n" + "="*70)
    print("  MODEL SELECTOR")
    print("="*70)
    local = list_local_models()
    if local:
        print("  ── On your storage ──")
        for i, m in enumerate(local, 1):
            try:   size = f"{m.stat().st_size/(1024**3):.1f} GB"
            except Exception: size = "?"
            print(f"  [L{i}]  {m.name}  ({size})")
        print()
    print("  ── Download new ──")
    for entry in MODEL_MENU:
        print(f"  {entry[0]}")
    print(f"\n  Free RAM: {get_free_ram_gb():.1f} GB")
    print("  [0]  START WITHOUT ANY MODEL  (load from UI later)")
    print("  Enter = use first local model (or download Qwen2.5-Coder-14B)")
    print("="*70)
    while True:
        c = input("  Choice: ").strip()
        if c == "0":
            USE_MODEL = False; MODEL_FILE = ""; MODEL_REPO = ""; N_CTX = 4096
            print("  ✓ Starting without a model"); break
        if c.upper().startswith("L") and local:
            try:
                idx = int(c[1:]) - 1
                if 0 <= idx < len(local):
                    sel = local[idx]; USE_MODEL = True
                    MODEL_FILE = sel.name; MODEL_REPO = ""
                    N_CTX = auto_ctx_size(sel.stat().st_size/(1024**3))
                    print(f"  ✓ {MODEL_FILE}  (ctx={N_CTX})"); break
                else: print("  Invalid number.")
            except Exception as e: print(f"  Error: {e}")
            continue
        if not c:
            if local:
                sel = local[0]; USE_MODEL = True; MODEL_FILE = sel.name; MODEL_REPO = ""
                N_CTX = auto_ctx_size(sel.stat().st_size/(1024**3))
                print(f"  ✓ {MODEL_FILE}  (ctx={N_CTX})"); break
            else:
                USE_MODEL = True; MODEL_REPO = MODEL_MENU[4][1]; MODEL_FILE = MODEL_MENU[4][2]
                N_CTX = auto_ctx_size(MODEL_MENU[4][3])
                print(f"  ✓ {MODEL_FILE}  (ctx={N_CTX})"); break
        try:
            idx = int(c) - 1
            if idx < 0 or idx >= len(MODEL_MENU): raise ValueError()
            entry = MODEL_MENU[idx]
            if not entry[1]:
                MODEL_REPO = input("  HF repo: ").strip()
                MODEL_FILE = input("  Filename: ").strip()
                N_CTX = 2048
            else:
                MODEL_REPO, MODEL_FILE = entry[1], entry[2]
                N_CTX = auto_ctx_size(entry[3])
            USE_MODEL = True
            print(f"  ✓ {MODEL_FILE}  (ctx={N_CTX})"); break
        except ValueError:
            print("  Invalid. Enter 0, L1/L2..., 1-7, or press Enter.")


# ══════════════════════════════════════════════════════════════════════════════
#  BUILD GRADIO LAUNCH WRAPPER
# ══════════════════════════════════════════════════════════════════════════════

def build_launch_wrapper(python_exe):
    threads    = auto_thread_count()
    mode_label = "GPU" if USE_GPU else "CPU"
    model_desc = MODEL_FILE if USE_MODEL else "NO MODEL"
    cuda_block = "" if USE_GPU else "\nos.environ['CUDA_VISIBLE_DEVICES'] = ''"
    model_flag = f"'--model', '{MODEL_FILE}'," if (USE_MODEL and MODEL_FILE) else "# no model"

    code = f"""#!/usr/bin/env python3
# MY-AI-Gizmo launch wrapper v3.4 — Gradio share=True
import sys, os
{cuda_block}
os.environ['MPLBACKEND']         = 'Agg'
os.environ['MPLCONFIGDIR']       = r'{MPL_CONFIG_DIR}'
os.environ['GRADIO_SERVER_NAME'] = '0.0.0.0'
os.environ['GRADIO_SHARE']       = '1'

flags = [
    '--listen', '--share', '--verbose',
    '--api', '--api-port', '5000',
    '--loader', 'llama.cpp',
    '--gpu-layers', '{GPU_LAYERS}',
    '--ctx-size', '{N_CTX}',
    '--batch-size', '512',
    '--threads', '{threads}',
    {model_flag}
    '--extensions', 'gizmo_toolbar,dual_model,google_workspace',
]
for f in flags:
    if f not in sys.argv:
        sys.argv.append(f)

print("[WRAPPER v3.4] {mode_label} | {model_desc} | ＋button | Google Workspace | Dual Model")
try:
    import matplotlib; matplotlib.use('Agg', force=True)
except Exception: pass

import runpy
runpy.run_path('server.py', run_name='__main__')
"""
    wrapper_path = WORK_DIR / "_gizmo_launch.py"
    wrapper_path.write_text(code, encoding="utf-8")
    print("[✓] Launch wrapper: _gizmo_launch.py")
    return str(wrapper_path)


# ══════════════════════════════════════════════════════════════════════════════
#  SERVER LAUNCH WITH STREAMING + URL CAPTURE
# ══════════════════════════════════════════════════════════════════════════════

def launch(python_exe, wrapper_path):
    cmd = [python_exe, "-u", wrapper_path]
    env = os.environ.copy()
    env.update({
        "MPLBACKEND":         "Agg",
        "MPLCONFIGDIR":       str(MPL_CONFIG_DIR),
        "GRADIO_SERVER_NAME": "0.0.0.0",
        "GRADIO_SHARE":       "1",
    })
    if not USE_GPU:
        env["CUDA_VISIBLE_DEVICES"] = ""

    captured = None

    for attempt in range(1, MAX_RESTARTS + 1):
        print(f"\n{'='*70}")
        print(f"  🚀 Starting server (attempt {attempt}/{MAX_RESTARTS})")
        print(f"{'='*70}\n")
        if attempt > 1:
            time.sleep(5)

        log_path = LOG_DIR / f"server_{int(time.time())}.log"
        logfile  = None
        try: logfile = open(log_path, "a", encoding="utf-8")
        except Exception: pass

        os.chdir(WORK_DIR)
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, text=True, bufsize=1,
        )

        last_output = time.time()
        stop_hb     = threading.Event()

        def heartbeat():
            while not stop_hb.wait(HEARTBEAT_INTERVAL):
                if time.time() - last_output >= HEARTBEAT_INTERVAL:
                    print("[heartbeat] server still running...")

        hb = threading.Thread(target=heartbeat, daemon=True)
        hb.start()

        try:
            for line in proc.stdout:
                last_output = time.time()
                print(line, end="", flush=True)
                if logfile:
                    try: logfile.write(line)
                    except Exception: pass

                if not captured:
                    for pat in URL_PATTERNS:
                        m = pat.search(line)
                        if m:
                            url = m.group(1).rstrip(").,\\'\"")
                            if any(k in url.lower() for k in URL_KEYWORDS):
                                captured = url
                                print(f"\n{'='*70}")
                                print(f"  🌐 PUBLIC URL: {captured}")
                                print(f"{'='*70}\n", flush=True)
                                try: PUBLIC_URL_FILE.write_text(captured)
                                except Exception: pass
                                break
        except KeyboardInterrupt:
            print("\n[info] Interrupted by user")
            proc.terminate()
            break
        except Exception as e:
            print(f"[error] Stream error: {e}")
        finally:
            stop_hb.set()
            hb.join(timeout=1)
            if logfile:
                try: logfile.close()
                except Exception: pass

        rc = proc.wait()
        print(f"\n[info] Server exited with code {rc}")

        if rc in (0, -9): break
        if attempt < MAX_RESTARTS:
            print(f"[warn] Crashed (code {rc}) — restarting...")
        else:
            print("[info] Max restarts reached.")

    return captured


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║   STEP 1 — GitHub Token  (MUST happen before everything else)      ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    setup_github_token()

    # ── Banner ─────────────────────────────────────────────────────────────
    print("="*70)
    print("  MY-AI-Gizmo  v3.4  Universal Launcher")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Repo: Gizmo-my-ai-for-google-colab  (private — token auth)")
    print("  ＋button | Styles | Google Docs | Slides | Dual Model")
    print("="*70)

    # ── GPU / CPU choice ───────────────────────────────────────────────────
    choose_mode()

    if USE_GPU:
        r = sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
        print(f"[{'✓' if r.returncode==0 else 'warn'}] GPU: "
              f"{r.stdout.strip() if r.returncode==0 else 'not found'}")

    # ── Drive ──────────────────────────────────────────────────────────────
    drive_ok = mount_drive_if_needed()
    setup_drive_root(drive_ok)

    for d in (DRIVE_ROOT, LOG_DIR, MPL_CONFIG_DIR,
              DRIVE_ROOT / "models", DRIVE_ROOT / "settings", DRIVE_ROOT / "characters"):
        try: d.mkdir(parents=True, exist_ok=True)
        except Exception: pass

    cleanup_broken_files()
    show_model_manager()
    choose_model()

    # ── Repo ───────────────────────────────────────────────────────────────
    if not download_repo_if_missing() and not WORK_DIR.exists():
        raise SystemExit("Repository unavailable — check your token and repo name.")

    # ── Symlinks ───────────────────────────────────────────────────────────
    ensure_symlinks_and_files()

    # ── Model ──────────────────────────────────────────────────────────────
    print("\n📥 Checking model...")
    print_ram_status()
    if not download_model_if_missing():
        raise SystemExit(1)

    # ── Config files ───────────────────────────────────────────────────────
    write_settings_yaml()
    write_cmd_flags()
    write_debug_character()
    write_model_loader_config()

    # ── Extensions ─────────────────────────────────────────────────────────
    print("\n📦 Deploying extensions...")
    _deploy_ext_stub("gizmo_toolbar")
    _deploy_ext_stub("google_workspace")
    deploy_dual_model_extension()

    # ── Install env ────────────────────────────────────────────────────────
    start_sh   = WORK_DIR / "start_linux.sh"
    env_marker = WORK_DIR / "installer_files" / "env" / "bin" / "python"
    python_exe = str(env_marker) if env_marker.exists() else "python3"

    if not start_sh.exists():
        raise SystemExit("[error] start_linux.sh not found — check your repo.")
    sh("chmod +x start_linux.sh")

    if not env_marker.exists():
        print("[info] First run — installing env (5-10 min)...")
        MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        install_env = os.environ.copy()
        if USE_GPU:
            install_env.update({
                "MPLBACKEND":"Agg","MPLCONFIGDIR":str(MPL_CONFIG_DIR),
                "GPU_CHOICE":"A","LAUNCH_AFTER_INSTALL":"FALSE",
                "INSTALL_EXTENSIONS":"FALSE",
                "CMAKE_ARGS":"-DLLAMA_CUBLAS=ON -DLLAMA_CUDA=ON",
                "FORCE_CMAKE":"1","SKIP_TORCH_TEST":"TRUE","FORCE_CUDA":"TRUE",
            })
        else:
            install_env.update({
                "MPLBACKEND":"Agg","MPLCONFIGDIR":str(MPL_CONFIG_DIR),
                "GPU_CHOICE":"N","LAUNCH_AFTER_INSTALL":"FALSE",
                "INSTALL_EXTENSIONS":"FALSE",
                "CMAKE_ARGS":"-DLLAMA_CUDA=OFF -DLLAMA_CUBLAS=OFF",
                "FORCE_CMAKE":"1","CUDA_VISIBLE_DEVICES":"","CUDACXX":"",
                "SKIP_TORCH_TEST":"TRUE","FORCE_CUDA":"FALSE",
            })
        installer_log = LOG_DIR / f"installer_{int(time.time())}.log"
        code = stream_with_heartbeat(
            "bash start_linux.sh", cwd=str(WORK_DIR),
            env=install_env, logfile_path=str(installer_log))
        print(f"[{'✓' if code==0 else 'warn'}] Installer code {code}")
        python_exe = str(env_marker) if env_marker.exists() else "python3"

    # ── Post-install: skip llama-cpp if webui already installed it ─────────
    pip_exe = str(Path(python_exe).parent / "pip") if Path(python_exe).exists() else "pip"
    llama_check = sh(f'"{pip_exe}" show llama-cpp-binaries 2>/dev/null')
    if llama_check.returncode == 0 and "llama-cpp-binaries" in llama_check.stdout:
        ver = next((l for l in llama_check.stdout.splitlines() if l.startswith("Version:")), "")
        print(f"[info] llama-cpp-binaries already installed ({ver.strip()}) — skipping reinstall")
    else:
        if USE_GPU: install_llama_cpp_gpu(python_exe)
        else:       install_llama_cpp_cpu(python_exe)

    create_llama_cpp_wrapper(python_exe)
    install_google_workspace_deps(python_exe)

    # ── Kill old servers ───────────────────────────────────────────────────
    sh("pkill -9 -f 'python.*server.py'")
    sh("pkill -9 -f 'python.*gradio'")
    sh("pkill -9 -f '_gizmo_launch'")
    time.sleep(2)

    # ── Build Gradio launch wrapper ────────────────────────────────────────
    wrapper_path = build_launch_wrapper(python_exe)

    mode_label = "GPU" if USE_GPU else "CPU"
    model_desc = MODEL_FILE if USE_MODEL else "(none — load from UI)"
    print("\n" + "="*70)
    print(f"  LAUNCHING v3.4 — {mode_label}")
    print(f"  Model   : {model_desc}")
    print(f"  Threads : {auto_thread_count()}  |  ctx: {N_CTX}")
    print(f"  Extensions: ＋Toolbar | Dual Model | Google Workspace")
    print(f"  URL will appear below — wait ~30 s after model loads")
    print("="*70)
    print_ram_status()
    print("⏳ Starting server...\n")

    # ── LAUNCH ─────────────────────────────────────────────────────────────
    captured = launch(python_exe, wrapper_path)

    # ── Fallback: ngrok ────────────────────────────────────────────────────
    if not captured:
        print("\n[info] No URL captured — trying ngrok fallback...")
        captured = try_setup_ngrok(7860)

    # ── Final summary ──────────────────────────────────────────────────────
    print("\n" + "="*70)
    if captured:
        print(f"  ✅ READY!  →  {captured}")
        print("="*70)
        print("  • ＋ button (bottom-left)  → styles, connectors, tools")
        print("  • 🔗 Google Workspace tab  → connect Docs & Slides")
        print("  • 🤖 Dual Model tab        → load a second model")
        print("  • API: http://0.0.0.0:5000/v1")
        if not USE_MODEL:
            print("  • ⚠️  No model loaded — go to Model tab in UI to load one")
    else:
        print("  ❌ NO PUBLIC URL CAPTURED")
        print("="*70)
        print("  Fixes: pkill -9 -f server.py | delete installer_files/ | check Colab internet")
    print_ram_status()
    print("="*70)
