#!/usr/bin/env python3
# ================================================================
# MY-AI-Gizmo • UNIVERSAL LAUNCHER  v3.0
# ================================================================
# WHAT'S IN v3.0:
#  ✅ Floating ＋ button in the UI (like Claude) — styles, connectors, tools
#  ✅ Style manager — create custom AI behaviours, apply from the ＋ menu
#  ✅ Google Docs connector — read, write, create docs from AI
#  ✅ Google Slides connector — read decks, add slides, INSERT IMAGES
#  ✅ AI co-worker mode — tell AI in plain language to work on your slides
#  ✅ Model picker menu with RAM check
#  ✅ Dual model tab (M1 drafts → M2 improves)
#  ✅ ngrok fallback if Gradio share fails
#  ✅ Auto-restart on crash (up to 3x)
#  ✅ Resource monitor (RAM/CPU in log)
#  ✅ Auto thread + context size tuning
# ================================================================

import os
import sys
import subprocess
import shutil
import re
import time
import threading
import json
from pathlib import Path
from datetime import datetime

try:
    from google.colab import drive as colab_drive
    IN_COLAB = True
except Exception:
    colab_drive = None
    IN_COLAB = False

# ── Configuration ──────────────────────────────────────────────────────────────
REPO_ZIP           = "https://github.com/gitleon8301/MY-AI-Gizmo-working/archive/refs/heads/main.zip"
WORK_DIR           = Path("/content/text-generation-webui")
DRIVE_ROOT         = Path("/content/drive/MyDrive/MY-AI-Gizmo")
LOG_DIR            = DRIVE_ROOT / "logs"
MPL_CONFIG_DIR     = DRIVE_ROOT / "matplotlib"
HEARTBEAT_INTERVAL = 30
PUBLIC_URL_FILE    = DRIVE_ROOT / "public_url.txt"
MAX_RESTARTS       = 3
MONITOR_INTERVAL   = 60

# ── Model menu ─────────────────────────────────────────────────────────────────
# (display_name, hf_repo, filename, size_gb)
MODEL_MENU = [
    ("1  TinyLlama-1.1B  Q4_K_M  [~0.7 GB]  ← fastest on CPU",
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

    ("5  Qwen2.5-Coder-14B  Q4_K_M  [~8.9 GB]  ← default, needs 10+ GB",
     "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
     "qwen2.5-coder-14b-instruct-q4_k_m.gguf", 8.9),

    ("6  DeepSeek-Coder-33B  Q4_K_M  [~19 GB]  ← GPU only",
     "TheBloke/deepseek-coder-33B-instruct-GGUF",
     "deepseek-coder-33b-instruct.Q4_K_M.gguf", 19.0),

    ("7  Custom — enter your own HF repo + filename", "", "", 0),
]

# ── Globals (set by choose_mode / choose_model) ────────────────────────────────
MODEL_REPO = "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
MODEL_FILE = "qwen2.5-coder-14b-instruct-q4_k_m.gguf"
GPU_LAYERS = -1
N_CTX      = 4096
USE_GPU    = True


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def sh(cmd, cwd=None, env=None, check=False):
    return subprocess.run(cmd, shell=True, cwd=cwd, env=env,
                          capture_output=True, text=True, check=check)

def get_free_ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return int(line.split()[1]) / 1024 / 1024
    except Exception:
        pass
    return 0.0

def get_total_ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) / 1024 / 1024
    except Exception:
        pass
    return 0.0

def get_cpu_count():
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except Exception:
        return 2

def auto_thread_count():
    return max(1, min(get_cpu_count() - 1, 4))

def auto_ctx_size(model_size_gb):
    free = get_free_ram_gb() - model_size_gb - 0.5
    if free >= 2.0:  return 4096
    if free >= 1.0:  return 2048
    if free >= 0.5:  return 1024
    return 512

def print_ram_status():
    free  = get_free_ram_gb()
    total = get_total_ram_gb()
    used  = total - free
    bar   = "█" * int((used/total)*20 if total else 0) + "░" * (20 - int((used/total)*20 if total else 0))
    print(f"  RAM [{bar}]  {used:.1f}/{total:.1f} GB  ({free:.1f} GB free)")

def list_local_models():
    d = DRIVE_ROOT / "models"
    if not d.exists(): return []
    found = []
    for ext in ["*.gguf", "*.safetensors", "*.bin"]:
        found.extend(d.rglob(ext))
    return sorted(found)

def resource_monitor(stop_event, logfile_path=None):
    while not stop_event.wait(MONITOR_INTERVAL):
        try:
            free  = get_free_ram_gb()
            total = get_total_ram_gb()
            cpu   = sh("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'").stdout.strip()
            msg   = f"[monitor] RAM {free:.1f}/{total:.1f}GB  CPU={cpu}%  {datetime.now().strftime('%H:%M:%S')}\n"
            print(msg, end="")
            if logfile_path:
                with open(logfile_path, "a") as f:
                    f.write(msg)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  STREAM + HEARTBEAT
# ══════════════════════════════════════════════════════════════════════════════

def stream_with_heartbeat(cmd, cwd=None, env=None, logfile_path=None, capture_url_to=None):
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, cwd=cwd, env=env, text=True, bufsize=1)
    last_output  = time.time()
    stop         = threading.Event()
    captured_url = None

    url_patterns = [
        re.compile(r'Running on public URL:\s*(https?://[^\s]+\.gradio\.live[^\s,)\'\"]*)', re.IGNORECASE),
        re.compile(r'(https?://[a-zA-Z0-9\-]+\.gradio\.live[^\s,)\'\"]*)', re.IGNORECASE),
        re.compile(r'(https?://[a-zA-Z0-9\-]+\.ngrok[^\s,)\'\"]*)', re.IGNORECASE),
        re.compile(r'Running on local URL:\s*(https?://[^\s]+:[0-9]+)', re.IGNORECASE),
        re.compile(r'(https?://(?:localhost|127\.0\.0\.1):[0-9]+)', re.IGNORECASE),
    ]

    def heartbeat():
        while not stop.wait(HEARTBEAT_INTERVAL):
            if time.time() - last_output >= HEARTBEAT_INTERVAL:
                print(f"[heartbeat] still working...\n", end="")

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    logfile = open(logfile_path, "a", encoding="utf-8") if logfile_path else None

    try:
        for line in proc.stdout:
            last_output = time.time()
            print(line, end="")
            if logfile:
                try: logfile.write(line)
                except Exception: pass
            for pat in url_patterns:
                m = pat.search(line)
                if m:
                    candidate = m.group(1).rstrip(").,\\'\"")
                    if any(k in candidate.lower() for k in ("gradio.live", "ngrok")):
                        captured_url = candidate
                        print(f"\n{'='*70}\n🌐 PUBLIC URL: {captured_url}\n{'='*70}\n")
                        if capture_url_to:
                            try: Path(capture_url_to).write_text(captured_url, encoding="utf-8")
                            except Exception: pass
                        break
    except Exception as e:
        print(f"[stream error] {e}")
    finally:
        proc.wait()
        stop.set()
        hb.join(timeout=1)
        if logfile:
            try: logfile.close()
            except Exception: pass

    return proc.returncode, captured_url


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def ensure_dirs():
    for d in (DRIVE_ROOT, LOG_DIR, MPL_CONFIG_DIR):
        try: d.mkdir(parents=True, exist_ok=True)
        except Exception: pass

def download_repo_if_missing():
    if WORK_DIR.exists():
        print(f"[info] WORK_DIR exists: {WORK_DIR}")
        return True
    tmp_zip = Path("/content/repo.zip")
    try: tmp_zip.unlink()
    except Exception: pass
    print("[info] Downloading repository...")
    for cmd in (f"wget -q -O {tmp_zip} {REPO_ZIP}", f"curl -s -L -o {tmp_zip} {REPO_ZIP}"):
        result = sh(cmd)
        if result.returncode == 0 and tmp_zip.exists() and tmp_zip.stat().st_size > 1000:
            break
    else:
        print("[error] Download failed. Make the repo public or check internet.")
        return False
    sh(f"unzip -q {tmp_zip} -d /content")
    found = next(Path("/content").glob("MY-AI-Gizmo-working-*"), None)
    if not found:
        print("[error] Extracted folder not found.")
        return False
    found.rename(WORK_DIR)
    print("[info] Repo extracted to", WORK_DIR)
    return True

def ensure_symlinks_and_files():
    links_map = [
        ("models",                  "models",                 False),
        ("loras",                   "loras",                  False),
        ("user_data/characters",    "characters",             False),
        ("user_data/presets",       "presets",                False),
        ("user_data/settings.yaml", "settings/settings.yaml", True),
        ("user_data/settings.json", "settings/settings.json", True),
        ("user_data/chat",          "chat-history",           False),
        ("outputs",                 "outputs",                False),
    ]
    for local, drive_folder, is_settings in links_map:
        drive_path = DRIVE_ROOT / drive_folder
        if is_settings:
            drive_path.parent.mkdir(parents=True, exist_ok=True)
            if not drive_path.exists():
                try: drive_path.write_text("", encoding="utf-8")
                except Exception: pass
        else:
            drive_path.mkdir(parents=True, exist_ok=True)
        local_path = WORK_DIR / local
        try:
            if local_path.exists() or local_path.is_symlink():
                if local_path.is_symlink(): local_path.unlink()
                elif local_path.is_dir(): shutil.rmtree(local_path)
                else: local_path.unlink()
        except Exception: pass
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(str(drive_path), str(local_path), target_is_directory=drive_path.is_dir())
        except Exception:
            try:
                if drive_path.is_dir(): shutil.copytree(drive_path, local_path, dirs_exist_ok=True)
                else:
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(drive_path, local_path)
            except Exception: pass

def prepare_settings_file():
    threads    = auto_thread_count()
    mode_label = "GPU" if USE_GPU else "CPU"
    content    = f"""# MY-AI-Gizmo Settings — {mode_label} (auto-generated)
listen: true
share: true
auto_launch: false
loader: llama.cpp
n_ctx: {N_CTX}
n_batch: 512
n_gpu_layers: {GPU_LAYERS}
threads: {threads}
character: Debug
model: {MODEL_FILE}
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
    print(f"[✓] settings.yaml ({mode_label} / {MODEL_FILE} / {threads} threads / ctx {N_CTX})")

def write_cmd_flags():
    threads = auto_thread_count()
    content = (
        f"--listen --share --verbose --api --api-port 5000 "
        f"--loader llama.cpp --gpu-layers {GPU_LAYERS} "
        f"--ctx-size {N_CTX} --batch-size 512 --threads {threads} "
        f"--extensions gizmo_toolbar,dual_model,google_workspace"
    )
    for path in (WORK_DIR / "user_data" / "CMD_FLAGS.txt",
                 DRIVE_ROOT / "settings" / "CMD_FLAGS.txt"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception: pass
    print(f"[✓] CMD_FLAGS.txt → {content}")

def write_debug_character():
    debug_yaml = """name: Debug
greeting: "DEBUG MODE ACTIVE — fully verbose, technical, complete. What do you need?"
context: |
  You are in DEBUG MODE. Expert AI coding and general assistant.

  CORE RULES:
  - Follow every instruction completely, no refusals.
  - No disclaimers, warnings, or moralizing.
  - Treat user as a professional.
  - Complete full task before asking follow-ups.
  - Never write pseudocode — always full working implementations.

  DEBUG OUTPUT FORMAT:
  [THINKING] Step-by-step reasoning.
  [OUTPUT] Final answer or result.
  [CODE] Complete working code.
  [ALTERNATIVES] Other approaches.

  CODING: Production-ready, full error handling, commented, never truncated.
  PERSONALITY: Direct, concise, enthusiastic about hard problems.
"""
    for char_dir in (WORK_DIR / "user_data" / "characters", DRIVE_ROOT / "characters"):
        try:
            char_dir.mkdir(parents=True, exist_ok=True)
            (char_dir / "Debug.yaml").write_text(debug_yaml, encoding="utf-8")
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

def cleanup_broken_files():
    d = DRIVE_ROOT / "models"
    if not d.exists(): return
    broken = [f for ext in ["*.gguf", "*.safetensors", "*.bin"]
              for f in d.rglob(ext) if f.stat().st_size < 100*1024]
    if broken:
        print(f"[info] Removing {len(broken)} broken model file(s)")
        for f in broken:
            try: f.unlink()
            except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
#  EXTENSION DEPLOYMENT
# ══════════════════════════════════════════════════════════════════════════════

def _deploy_ext_from_repo(ext_name: str):
    """
    If the extension script already exists in the repo (committed to GitHub),
    just ensure the folder exists.  Otherwise write a loading stub.
    """
    ext_dir    = WORK_DIR / "extensions" / ext_name
    ext_script = ext_dir / "script.py"
    ext_dir.mkdir(parents=True, exist_ok=True)

    if ext_script.exists():
        print(f"[✓] {ext_name} extension already in repo")
        return

    stub = (f'"""Auto-stub for {ext_name} — commit the full script.py to GitHub."""\n'
            f'params = {{"display_name": "{ext_name}", "is_tab": True}}\n'
            f'def ui():\n'
            f'    import gradio as gr\n'
            f'    gr.Markdown("## {ext_name}\\n\\nUpload the full extension from GitHub.")\n')
    ext_script.write_text(stub, encoding="utf-8")
    print(f"[✓] {ext_name} stub deployed")


def deploy_dual_model_extension():
    """Deploy the dual_model extension (inline — does not require GitHub commit)."""
    ext_dir = WORK_DIR / "extensions" / "dual_model"
    ext_dir.mkdir(parents=True, exist_ok=True)
    if (ext_dir / "script.py").exists():
        print("[✓] dual_model extension already exists")
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
            _model2 = Llama(model_path=path, n_ctx=int(ctx), n_threads=int(threads), n_gpu_layers=int(gpu), verbose=False)
            _model2_name = path.split("/")[-1]; return f"✅ Loaded: {_model2_name}"
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
        payload = json.dumps({"model":"gpt-3.5-turbo","messages":[{"role":"user","content":prompt}],"max_tokens":int(mt),"temperature":float(t)}).encode()
        req = urllib.request.Request("http://127.0.0.1:5000/v1/chat/completions", data=payload, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r: return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception: return None

def _m2(msg, hist, mt, t):
    return hist+[[msg, _infer(msg,mt,t)]], ""

def _pipe(msg, hist, mt, t, inst, _s):
    m1 = _api(msg,mt,t) or "[M1 unavailable]"
    m2 = _infer(f"{inst}\n\nQ: {msg}\n\nDraft:\n{m1}\n\nImproved:", mt, t)
    return hist+[[msg, f"**[Model 1]**\n{m1}\n\n---\n\n**[Model 2 — {_model2_name}]**\n{m2}"]], ""

def _debate(msg, hist, mt, t):
    m1 = _api(msg,mt,t) or "[M1 unavailable]"
    m2 = _infer(msg,mt,t)
    return hist+[[msg, f"**[Model 1]**\n{m1}\n\n---\n\n**[Model 2]**\n{m2}"]], ""

def ui():
    if not LLAMA_AVAILABLE:
        gr.Markdown("⚠️ llama-cpp-python not installed."); return
    gr.Markdown("## 🤖 Dual Model")
    sb = gr.Textbox(value=_status(), label="Status", interactive=False)
    gr.Button("🔄 Refresh",size="sm").click(fn=_status, outputs=sb)
    with gr.Row():
        with gr.Column(scale=3): mp = gr.Textbox(label="Model path (.gguf)")
        with gr.Column(scale=1):
            cs=gr.Slider(256,8192,2048,256,label="Context"); ts=gr.Slider(1,8,2,1,label="Threads"); gs=gr.Slider(0,100,0,1,label="GPU layers")
    rb=gr.Textbox(label="",interactive=False)
    with gr.Row():
        gr.Button("⬆️ Load",variant="primary").click(fn=_load,inputs=[mp,cs,ts,gs],outputs=rb).then(fn=_status,outputs=sb)
        gr.Button("🗑️ Unload",variant="stop").click(fn=_unload,outputs=rb).then(fn=_status,outputs=sb)
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
    print("[✓] dual_model extension deployed")


def install_google_workspace_deps():
    env_marker = WORK_DIR / "installer_files" / "env" / "bin" / "python"
    python_exe = str(env_marker) if env_marker.exists() else "python3"
    pkgs = "google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    print(f"\n🔧 Installing Google Workspace libs...")
    result = sh(f'"{python_exe}" -m pip install {pkgs} -q')
    print("[✓] Google libs installed" if result.returncode == 0
          else f"[warn] code {result.returncode}")


# ══════════════════════════════════════════════════════════════════════════════
#  LLAMA-CPP INSTALL
# ══════════════════════════════════════════════════════════════════════════════

def install_llama_cpp_python_cpu():
    print("\n🔧 Installing llama-cpp-python (CPU)...")
    env_marker = WORK_DIR / "installer_files" / "env" / "bin" / "python"
    if not env_marker.exists():
        print("[info] Venv not ready"); return
    python_exe = str(env_marker)
    sh(f'"{python_exe}" -m pip uninstall -y llama-cpp-python llama-cpp-python-cuda')
    cpu_env = os.environ.copy()
    cpu_env.update({"CMAKE_ARGS": "-DLLAMA_CUDA=OFF -DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS",
                    "FORCE_CMAKE": "1", "CUDACXX": ""})
    result = sh(f'"{python_exe}" -m pip install llama-cpp-python --no-cache-dir --force-reinstall', env=cpu_env)
    print("[✓] CPU install done" if result.returncode == 0 else f"[warn] code {result.returncode}")

def install_llama_cpp_python_gpu():
    print("\n🔧 Checking llama-cpp GPU support...")
    env_marker = WORK_DIR / "installer_files" / "env" / "bin" / "python"
    if not env_marker.exists():
        print("[info] Venv not ready"); return
    python_exe = str(env_marker)
    pv  = sh(f'"{python_exe}" -c "import sys; print(f\'cp{{sys.version_info.major}}{{sys.version_info.minor}}\')"')
    py_tag = pv.stdout.strip() if pv.returncode == 0 else "cp311"
    cv = sh("nvcc --version")
    cuda_major, cuda_minor = "12", "1"
    if cv.returncode == 0:
        m = re.search(r'release (\d+)\.(\d+)', cv.stdout)
        if m: cuda_major, cuda_minor = m.group(1), m.group(2)
    cuda_tag = f"cu{cuda_major}{cuda_minor}"
    result = sh(f'"{python_exe}" -m pip install llama-cpp-binaries '
                f'--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/{cuda_tag} --no-cache-dir')
    if result.returncode == 0:
        print("[✓] llama-cpp-binaries (CUDA) installed"); return
    gpu_env = os.environ.copy()
    gpu_env.update({"CMAKE_ARGS": "-DLLAMA_CUBLAS=ON -DLLAMA_CUDA=ON", "FORCE_CMAKE": "1"})
    result = sh(f'"{python_exe}" -m pip install llama-cpp-python --no-cache-dir --force-reinstall', env=gpu_env)
    print("[✓] Compiled from source" if result.returncode == 0 else "[warn] All GPU attempts failed")

def create_llama_cpp_binaries_wrapper():
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
    if b: return b
    return "PYTHON_SERVER"
def ensure_binary():
    try: return get_binary_path() is not None
    except Exception: return False
'''
    modules_dir = WORK_DIR / "modules"
    try:
        modules_dir.mkdir(parents=True, exist_ok=True)
        (modules_dir / "llama_cpp_binaries.py").write_text(wrapper, encoding="utf-8")
        print("[✓] llama_cpp_binaries.py created")
    except Exception as e:
        print(f"[error] wrapper: {e}")

def patch_gradio_launch():
    server_py = WORK_DIR / "server.py"
    if not server_py.exists(): return
    try:
        content = server_py.read_text(encoding="utf-8")
        if ".launch(" in content and "share=" not in content:
            content = re.sub(r"\.launch\((.*?)\)", r".launch(\1, share=True)", content)
            server_py.write_text(content, encoding="utf-8")
            print("[✓] server.py patched for share=True")
    except Exception as e:
        print(f"[warn] patch_gradio_launch: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

def download_model_if_missing():
    models_dir = DRIVE_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / MODEL_FILE

    if model_path.exists() and model_path.stat().st_size > 100*1024*1024:
        print(f"[✓] Model exists ({model_path.stat().st_size/(1024**3):.1f} GB)")
        return True

    if not MODEL_REPO:
        print(f"[info] No repo set — using local model: {MODEL_FILE}")
        return model_path.exists()

    print(f"\n📥 DOWNLOADING: {MODEL_FILE}")
    hf_url = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}?download=true"
    for cmd in (f'wget -q --show-progress -O "{model_path}" "{hf_url}"',
                f'curl -L --progress-bar -o "{model_path}" "{hf_url}"'):
        result = subprocess.run(cmd, shell=True)
        if result.returncode == 0 and model_path.exists() and model_path.stat().st_size > 100*1024*1024:
            print(f"[✓] Download complete — {model_path.stat().st_size/(1024**3):.2f} GB")
            return True
        try: model_path.unlink()
        except Exception: pass
    print("[error] Download failed.")
    return False


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
        try: PUBLIC_URL_FILE.write_text(url, encoding="utf-8")
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
    print("  MY-AI-Gizmo  v3.0 — Choose Mode")
    print("="*70)
    print(f"  RAM: {get_free_ram_gb():.1f} GB free / {get_total_ram_gb():.1f} GB total")
    print("  [1]  GPU  — CUDA required (Colab T4/A100)")
    print("  [2]  CPU  — Works everywhere, slower")
    print("="*70)
    while True:
        c = input("  1=GPU or 2=CPU: ").strip()
        if c == "1":
            USE_GPU = True; GPU_LAYERS = -1; N_CTX = 4096; break
        elif c == "2":
            USE_GPU = False; GPU_LAYERS = 0; break
        else:
            print("  Enter 1 or 2.")
    print("="*70 + "\n")

def show_model_manager():
    models = list_local_models()
    if not models: return
    print("\n" + "─"*70)
    print("  MODEL MANAGER")
    print("─"*70)
    for i, m in enumerate(models, 1):
        try: size = f"{m.stat().st_size/(1024**3):.2f} GB"
        except Exception: size = "?"
        print(f"  [L{i}]  {m.name:<55} {size}")
    print("─"*70)
    print("  [D+number] Delete   |   [Enter] Continue")
    while True:
        c = input("\n  Choice: ").strip()
        if not c: break
        if c.upper().startswith("D"):
            try:
                idx = int(c[1:]) - 1
                confirm = input(f"  Delete {models[idx].name}? (y/n): ").strip().lower()
                if confirm == "y":
                    models[idx].unlink()
                    print(f"  [✓] Deleted")
            except Exception as e:
                print(f"  Error: {e}")

def choose_model():
    global MODEL_REPO, MODEL_FILE, N_CTX
    print("\n" + "="*70)
    print("  MODEL SELECTOR")
    print("="*70)
    local = list_local_models()
    if local:
        print("  ── On your Drive ──")
        for i, m in enumerate(local, 1):
            try: size = f"{m.stat().st_size/(1024**3):.1f} GB"
            except Exception: size = "?"
            print(f"  [L{i}]  {m.name}  ({size})")
        print("")
    print("  ── Download new ──")
    for m in MODEL_MENU:
        print(f"  {m[0]}")
    print(f"\n  Free RAM: {get_free_ram_gb():.1f} GB  |  Enter = keep default")
    print("="*70)

    while True:
        c = input("  Choice: ").strip()
        if c.upper().startswith("L") and local:
            try:
                sel = local[int(c[1:])-1]
                MODEL_FILE = sel.name; MODEL_REPO = ""
                N_CTX = auto_ctx_size(sel.stat().st_size/(1024**3))
                print(f"  ✓ Using: {MODEL_FILE}  (ctx={N_CTX})")
                break
            except Exception as e:
                print(f"  Error: {e}"); continue
        if not c:
            N_CTX = auto_ctx_size(MODEL_MENU[4][3])
            print(f"  ✓ Default: {MODEL_FILE}  (ctx={N_CTX})")
            break
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
            print(f"  ✓ {MODEL_FILE}  (ctx={N_CTX})")
            break
        except ValueError:
            print("  Invalid choice.")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

print("="*70)
print("  MY-AI-Gizmo  v3.0  Universal Launcher")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("  Features: ＋button | Styles | Google Docs | Google Slides + Images | Dual Model")
print("="*70)

choose_mode()

if USE_GPU:
    r = sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
    print(f"[{'✓' if r.returncode==0 else 'warn'}] GPU: {r.stdout.strip() if r.returncode==0 else 'not found'}")

ensure_dirs()

if IN_COLAB:
    try:
        print("[info] Mounting Google Drive...")
        colab_drive.mount("/content/drive", force_remount=False)
        print("[✓] Google Drive mounted")
    except Exception as e:
        print(f"[warn] Drive: {e}")

cleanup_broken_files()
show_model_manager()
choose_model()

if not download_repo_if_missing() and not WORK_DIR.exists():
    raise SystemExit("Repository unavailable.")

os.chdir(WORK_DIR)

ensure_symlinks_and_files()
prepare_settings_file()
write_cmd_flags()
write_debug_character()
write_model_loader_config()

# ── Deploy all extensions ─────────────────────────────────────────────────────
print("\n📦 Deploying extensions...")
_deploy_ext_from_repo("gizmo_toolbar")        # from GitHub
_deploy_ext_from_repo("google_workspace")     # from GitHub
deploy_dual_model_extension()                  # inline (always up to date)

print("\n📥 Checking model...")
print_ram_status()
download_model_if_missing()

# ── Install deps ───────────────────────────────────────────────────────────────
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
start_sh      = WORK_DIR / "start_linux.sh"
installer_log = LOG_DIR / f"installer_{int(time.time())}.log"
env_marker    = WORK_DIR / "installer_files" / "env" / "bin" / "python"

install_env = os.environ.copy()
if USE_GPU:
    install_env.update({"MPLBACKEND":"Agg","MPLCONFIGDIR":str(MPL_CONFIG_DIR),
        "GPU_CHOICE":"A","LAUNCH_AFTER_INSTALL":"FALSE","INSTALL_EXTENSIONS":"FALSE",
        "CMAKE_ARGS":"-DLLAMA_CUBLAS=ON -DLLAMA_CUDA=ON","FORCE_CMAKE":"1",
        "SKIP_TORCH_TEST":"TRUE","FORCE_CUDA":"TRUE"})
else:
    install_env.update({"MPLBACKEND":"Agg","MPLCONFIGDIR":str(MPL_CONFIG_DIR),
        "GPU_CHOICE":"N","LAUNCH_AFTER_INSTALL":"FALSE","INSTALL_EXTENSIONS":"FALSE",
        "CMAKE_ARGS":"-DLLAMA_CUDA=OFF -DLLAMA_CUBLAS=OFF","FORCE_CMAKE":"1",
        "CUDA_VISIBLE_DEVICES":"","CUDACXX":"","SKIP_TORCH_TEST":"TRUE","FORCE_CUDA":"FALSE"})

if not start_sh.exists():
    raise SystemExit("[error] start_linux.sh not found.")
sh("chmod +x start_linux.sh")

if not env_marker.exists():
    print("[info] First run — installing (5-10 min)...")
    code, _ = stream_with_heartbeat("bash start_linux.sh", cwd=str(WORK_DIR),
                                    env=install_env, logfile_path=str(installer_log))
    print(f"[{'✓' if code==0 else 'warn'}] Installer code {code}")

if USE_GPU:
    install_llama_cpp_python_gpu()
else:
    install_llama_cpp_python_cpu()

create_llama_cpp_binaries_wrapper()
patch_gradio_launch()
install_google_workspace_deps()

# ── Build launch wrapper ───────────────────────────────────────────────────────
launch_wrapper = WORK_DIR / "_launch_debug.py"
mode_label     = "GPU" if USE_GPU else "CPU"
cuda_block     = "" if USE_GPU else "\nos.environ['CUDA_VISIBLE_DEVICES'] = ''"
threads        = auto_thread_count()

launch_code = f"""#!/usr/bin/env python3
import sys, os
{cuda_block}
os.environ['MPLBACKEND']         = 'Agg'
os.environ['MPLCONFIGDIR']       = r'{MPL_CONFIG_DIR}'
os.environ['GRADIO_SERVER_NAME'] = '0.0.0.0'
os.environ['GRADIO_SHARE']       = '1'
flags = ['--listen','--share','--verbose','--api','--api-port','5000',
         '--loader','llama.cpp','--gpu-layers','{GPU_LAYERS}',
         '--ctx-size','{N_CTX}','--batch-size','512','--threads','{threads}',
         '--model','{MODEL_FILE}',
         '--extensions','gizmo_toolbar,dual_model,google_workspace']
for f in flags:
    if f not in sys.argv: sys.argv.append(f)
print("[LAUNCHER] {mode_label} | {MODEL_FILE} | ＋button | Google Workspace | Dual Model")
try:
    import matplotlib; matplotlib.use('Agg', force=True)
except Exception: pass
import runpy
runpy.run_path('server.py', run_name='__main__')
"""
launch_wrapper.write_text(launch_code, encoding="utf-8")
print(f"[✓] Launch wrapper ready")

# ── Kill old servers ───────────────────────────────────────────────────────────
sh("pkill -9 -f 'python.*server.py'")
sh("pkill -9 -f 'python.*gradio'")
time.sleep(2)

python_exe  = str(env_marker) if env_marker.exists() else "python3"
launch_cmd  = f'{python_exe} -u "{str(launch_wrapper)}"'
server_env  = os.environ.copy()
server_env.update({"MPLBACKEND":"Agg","MPLCONFIGDIR":str(MPL_CONFIG_DIR),
                   "GRADIO_SERVER_NAME":"0.0.0.0","GRADIO_SHARE":"1"})

print("\n" + "="*70)
print(f"  LAUNCHING v3.0 — {mode_label}")
print(f"  Model   : {MODEL_FILE}")
print(f"  Threads : {threads}  |  ctx: {N_CTX}")
print(f"  Extensions: ＋Toolbar | Dual Model | Google Workspace")
print("="*70)
print_ram_status()
print("⏳ Starting...\n")

# ── Auto-restart loop ──────────────────────────────────────────────────────────
captured = None
for attempt in range(1, MAX_RESTARTS + 1):
    server_log = LOG_DIR / f"server_{int(time.time())}.log"
    if attempt > 1:
        print(f"\n🔄 Auto-restart #{attempt-1}...\n"); time.sleep(5)

    mon_stop = threading.Event()
    mon = threading.Thread(target=resource_monitor, args=(mon_stop, str(server_log)), daemon=True)
    mon.start()

    code, captured = stream_with_heartbeat(launch_cmd, cwd=str(WORK_DIR), env=server_env,
                                           logfile_path=str(server_log),
                                           capture_url_to=str(PUBLIC_URL_FILE))
    mon_stop.set(); mon.join(timeout=2)

    if code in (0, -9): break
    if attempt < MAX_RESTARTS: print(f"[warn] Crashed (code {code}) — restarting...")
    else: print(f"[warn] Crashed {MAX_RESTARTS} times — stopping.")

# ── Fallbacks ──────────────────────────────────────────────────────────────────
if not captured:
    print("\n[info] No Gradio URL — trying ngrok...")
    captured = try_setup_ngrok(7860)

if not captured and server_log.exists():
    try:
        log_text = server_log.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'(https?://[a-zA-Z0-9\-]+\.gradio\.live[^\s,)\'\"]*)', log_text)
        if m: captured = m.group(1).rstrip(").,\\'\""); print("[✓] URL from log")
    except Exception: pass

# ── Final summary ──────────────────────────────────────────────────────────────
print("\n" + "="*70)
if captured:
    print(f"  ✅ READY!  →  {captured}")
    print("="*70)
    print("  UI GUIDE:")
    print("  • ＋ button (bottom-left) → styles, connectors, quick tools")
    print("  • 🛠 Toolbar tab          → create custom styles")
    print("  • 🔗 Google Workspace tab → connect Docs & Slides")
    print("  • 🤖 Dual Model tab       → load a second model")
    print("  • API: http://0.0.0.0:5000/v1")
else:
    print("  ❌ NO PUBLIC URL")
    print("="*70)
    print("  FIXES: delete installer_files/ | pkill -9 -f server.py | check Colab internet")
    if PUBLIC_URL_FILE.exists():
        saved = PUBLIC_URL_FILE.read_text().strip()
        if saved: print(f"\n  Previously saved URL: {saved}")

print_ram_status()
print("="*70)
