#!/usr/bin/env python3
# ================================================================
# MY-AI-Gizmo • UNIVERSAL LAUNCHER v3.6.0 - COLAB & KAGGLE READY
# ================================================================
# v3.6.0 CHANGES:
# 🔧 FIX: Git clone URL now properly ends with .git
# 🔧 FIX: Added Kaggle environment detection
# 🔧 FIX: Proper path handling for both Colab and Kaggle
# 🔧 FIX: Drive mounting works correctly in both environments
# ✅ All v3.5.2 features kept
# ================================================================

import os, sys, subprocess, shutil, re, time, threading
from pathlib import Path
from datetime import datetime

# ── Environment Detection ───────────────────────────────────────
IN_COLAB = False
IN_KAGGLE = False
ENVIRONMENT = "local"

try:
    from google.colab import drive as colab_drive
    IN_COLAB = True
    ENVIRONMENT = "colab"
except Exception:
    colab_drive = None

if not IN_COLAB and os.path.exists('/kaggle/working'):
    IN_KAGGLE = True
    ENVIRONMENT = "kaggle"

# ── Repo ────────────────────────────────────────────────────────
GITHUB_USER = "leonlazdev-wq"
GITHUB_REPO = "Gizmo_MY_AI"
GITHUB_BRANCH = "main"
REPO_ZIP = ""
REPO_CLONE_URL = ""

# ── Paths (Environment-aware) ───────────────────────────────────
if IN_KAGGLE:
    BASE_DIR = Path("/kaggle/working")
elif IN_COLAB:
    BASE_DIR = Path("/content")
else:
    BASE_DIR = Path.cwd()

WORK_DIR = BASE_DIR / "text-generation-webui"
DRIVE_ROOT = None
LOG_DIR = None
MPL_CONFIG_DIR = None
PUBLIC_URL_FILE = None

HEARTBEAT_INTERVAL = 30
MAX_RESTARTS = 3

# ── Model menu ──────────────────────────────────────────────────
MODEL_MENU = [
    ("1 TinyLlama-1.1B Q4_K_M [~0.7 GB] <- fastest",
     "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
     "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf", 0.7),
    ("2 Phi-3-mini-4k Q4_K_M [~2.2 GB] <- great quality/speed",
     "bartowski/Phi-3-mini-4k-instruct-GGUF",
     "Phi-3-mini-4k-instruct-Q4_K_M.gguf", 2.2),
    ("3 Mistral-7B-v0.3 Q4_K_M [~4.4 GB] <- best general 7B",
     "bartowski/Mistral-7B-v0.3-GGUF",
     "Mistral-7B-v0.3-Q4_K_M.gguf", 4.4),
    ("4 Qwen2.5-Coder-7B Q4_K_M [~4.7 GB] <- best coding 7B",
     "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
     "qwen2.5-coder-7b-instruct-q4_k_m.gguf", 4.7),
    ("5 Qwen2.5-Coder-14B Q4_K_M [~8.9 GB] <- needs 10+ GB RAM",
     "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
     "qwen2.5-coder-14b-instruct-q4_k_m.gguf", 8.9),
    ("6 DeepSeek-Coder-33B Q4_K_M [~19 GB] <- GPU only",
     "TheBloke/deepseek-coder-33B-instruct-GGUF",
     "deepseek-coder-33b-instruct.Q4_K_M.gguf", 19.0),
    ("7 Custom — enter your own HF repo + filename", "", "", 0),
]

# ── Globals ─────────────────────────────────────────────────────
GITHUB_TOKEN = ""
MODEL_REPO = ""
MODEL_FILE = ""
USE_MODEL = False
GPU_LAYERS = -1
N_CTX = 4096
USE_GPU = True

URL_PATTERNS = [
    re.compile(r'Running on public URL:\s*(https?://\S+)', re.IGNORECASE),
    re.compile(r'(https?://[a-zA-Z0-9\-]+\.gradio\.live\S*)', re.IGNORECASE),
    re.compile(r'(https?://[a-zA-Z0-9\-]+\.trycloudflare\.com\S*)', re.IGNORECASE),
    re.compile(r'(https?://[a-zA-Z0-9\-]+\.ngrok\S*)', re.IGNORECASE),
    re.compile(r'(?:public|share|tunnel|external)[^\n]{0,40}(https?://\S+)', re.IGNORECASE),
]
URL_KEYWORDS = ("gradio.live", "trycloudflare.com", "ngrok", "loca.lt")

# =============================================================================
# GITHUB TOKEN
# =============================================================================
def _token_file_path():
    if DRIVE_ROOT and (DRIVE_ROOT.parent.exists()):
        return DRIVE_ROOT / "github_token.txt"
    return BASE_DIR / "MY-AI-Gizmo" / "github_token.txt"

def _load_saved_token():
    for candidate in (
        BASE_DIR / "MY-AI-Gizmo" / "github_token.txt",
        Path("/content/drive/MyDrive/MY-AI-Gizmo/github_token.txt"),
        Path("/kaggle/working/MY-AI-Gizmo/github_token.txt"),
    ):
        if candidate.exists():
            try:
                tok = candidate.read_text(encoding="utf-8").strip()
                if len(tok) >= 10:
                    return tok
            except Exception:
                pass
    return ""

def _save_token(token):
    path = _token_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
    except Exception as e:
        print(f" [warn] Could not save token: {e}")

def _build_urls():
    global REPO_ZIP, REPO_CLONE_URL
    if GITHUB_TOKEN:
        REPO_ZIP = (f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}"
                   f"/archive/refs/heads/{GITHUB_BRANCH}.zip")
        REPO_CLONE_URL = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"
    else:
        REPO_ZIP = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"
        REPO_CLONE_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}.git"

def setup_github_token():
    global GITHUB_TOKEN
    print("=" * 70)
    print(f" MY-AI-Gizmo v3.6.0 — GitHub Auth ({ENVIRONMENT.upper()})")
    print("=" * 70)
    print()
    saved = _load_saved_token()
    if saved:
        last3 = saved[-3:]
        print(f" [💾] Token found ( ends in: ...{last3} )")
        ans = input(" Use this saved token? (y = yes / n = enter a new one): ").strip().lower()
        if ans != "n":
            GITHUB_TOKEN = saved
            print(f" [✓] Using saved token ...{last3}")
            print("=" * 70)
            _build_urls()
            return
    print(" Your repo is PRIVATE. A Personal Access Token is required.")
    print()
    print(" How to get a token:")
    print("  1. Go to https://github.com/settings/tokens")
    print("  2. Personal Access Tokens → Tokens (classic)")
    print("  3. Generate new token (classic)")
    print("  4. Set scope: ✓ repo (full control of private repos)")
    print("  5. Copy the token (starts with ghp_...)")
    print()
    while True:
        token = input(" Paste your GitHub token here: ").strip()
        if not token:
            print(" [!] Token cannot be empty. Try again.")
            continue
        if not (token.startswith("ghp_") or token.startswith("github_pat_") or len(token) >= 20):
            confirm = input(" [?] Token looks unusual. Continue anyway? (y/n): ").strip().lower()
            if confirm != "y":
                continue
        GITHUB_TOKEN = token
        break
    _build_urls()
    _save_token(GITHUB_TOKEN)
    last3 = GITHUB_TOKEN[-3:]
    print()
    print(f" [✓] Token accepted & saved ( ends in: ...{last3} )")
    print(" 💾 Token saved — next launch will ask if you want to reuse it.")
    print("=" * 70)
    print()

# =============================================================================
# DRIVE SETUP
# =============================================================================
def mount_drive_if_needed():
    if IN_COLAB:
        if Path("/content/drive/MyDrive").exists():
            print("[info] Google Drive already mounted")
            return True
        try:
            colab_drive.mount("/content/drive", force_remount=False)
            print("[✓] Google Drive mounted")
            return True
        except Exception as e:
            print(f"[warn] Drive mount failed ({e}) — using local storage")
            return False
    elif IN_KAGGLE:
        print("[info] Kaggle detected — using local storage")
        print("       (Google Drive requires PyDrive2 OAuth setup)")
        return False
    return False

def setup_drive_root(drive_ok):
    global DRIVE_ROOT, LOG_DIR, MPL_CONFIG_DIR, PUBLIC_URL_FILE
    if IN_COLAB and drive_ok:
        DRIVE_ROOT = Path("/content/drive/MyDrive/MY-AI-Gizmo")
    elif IN_KAGGLE:
        DRIVE_ROOT = Path("/kaggle/working/MY-AI-Gizmo")
    else:
        DRIVE_ROOT = BASE_DIR / "MY-AI-Gizmo"
    LOG_DIR = DRIVE_ROOT / "logs"
    MPL_CONFIG_DIR = DRIVE_ROOT / "matplotlib"
    PUBLIC_URL_FILE = DRIVE_ROOT / "public_url.txt"
    if not drive_ok:
        print(f"[info] Storage: {DRIVE_ROOT}")

# =============================================================================
# UTILITIES
# =============================================================================
def sh(cmd, cwd=None, env=None):
    return subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)

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

def auto_thread_count():
    try:
        import multiprocessing
        return max(1, min(multiprocessing.cpu_count() - 1, 4))
    except Exception:
        return 2

def auto_ctx_size(model_gb):
    free = get_free_ram_gb() - model_gb - 0.5
    if free >= 2.0:
        return 4096
    if free >= 1.0:
        return 2048
    if free >= 0.5:
        return 1024
    return 512

def print_ram_status():
    free = get_free_ram_gb()
    total = get_total_ram_gb()
    used = total - free
    pct = (used / total) if total else 0
    bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
    print(f" RAM [{bar}] {used:.1f}/{total:.1f} GB ({free:.1f} GB free)")

def list_local_models():
    d = DRIVE_ROOT / "models"
    if not d.exists():
        return []
    found = []
    for ext in ["*.gguf", "*.safetensors", "*.bin"]:
        found.extend(d.rglob(ext))
    return sorted(found)

def cleanup_broken_files():
    d = DRIVE_ROOT / "models"
    if not d.exists():
        return
    broken = [f for ext in ["*.gguf", "*.safetensors", "*.bin"] for f in d.rglob(ext) if f.stat().st_size < 100 * 1024]
    if broken:
        print(f"[info] Removing {len(broken)} broken model file(s)")
        for f in broken:
            try:
                f.unlink()
            except Exception:
                pass

# =============================================================================
# STREAM + HEARTBEAT
# =============================================================================
def stream_with_heartbeat(cmd, cwd=None, env=None, logfile_path=None):
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env, text=True, bufsize=1)
    stop = threading.Event()
    last_t = [time.time()]
    def heartbeat():
        while not stop.wait(HEARTBEAT_INTERVAL):
            if time.time() - last_t[0] >= HEARTBEAT_INTERVAL:
                print("[heartbeat] still working...")
    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    logfile = open(logfile_path, "a", encoding="utf-8") if logfile_path else None
    try:
        for line in proc.stdout:
            last_t[0] = time.time()
            print(line, end="")
            if logfile:
                try:
                    logfile.write(line)
                except Exception:
                    pass
    except Exception as e:
        print(f"[stream error] {e}")
    finally:
        proc.wait()
        stop.set()
        hb.join(timeout=1)
        if logfile:
            try:
                logfile.close()
            except Exception:
                pass
    return proc.returncode

# =============================================================================
# REPO UPDATE CHECK
# =============================================================================
def _kill_old_servers():
    print(" [🛑] Killing old servers...")
    sh("pkill -9 -f 'python.*server.py'")
    sh("pkill -9 -f 'python.*gradio'")
    sh("pkill -9 -f '_gizmo_launch'")
    time.sleep(2)
    print(" [✓] Servers stopped")

def check_repo_update():
    if not WORK_DIR.exists():
        return 'new'
    print("\n" + "=" * 70)
    print(" REPO UPDATE CHECK")
    print("=" * 70)
    print(" Did you update / push changes to your GitHub repo?")
    print()
    print(" y — YES, re-clone fresh (new tabs/features will appear)")
    print(" n — NO, keep existing files (2 min launch, no reinstall)")
    print("=" * 70)
    while True:
        ans = input(" Updated repo? (y/n): ").strip().lower()
        if ans in ("y", "yes"):
            return 'fresh'
        elif ans in ("n", "no"):
            return 'keep'
        print(" Please type y or n")

def apply_repo_update(mode):
    if mode == 'fresh':
        print("\n [🔄] Wiping old repo so your updates load correctly...")
        _kill_old_servers()
        if WORK_DIR.exists():
            print(f" [🗑️] Removing {WORK_DIR} ...")
            try:
                shutil.rmtree(WORK_DIR)
                print(" [✓] Old repo removed")
            except Exception as e:
                print(f" [warn] shutil failed ({e}) — trying shell rm...")
                sh(f"rm -rf '{WORK_DIR}'")
                if not WORK_DIR.exists():
                    print(" [✓] Old repo removed")
                else:
                    print(" [warn] Could not fully remove — will overwrite")
        print(" [✓] Ready for fresh clone")

# =============================================================================
# SYMLINKS
# =============================================================================
def ensure_symlinks_and_files():
    links_map = [
        ("user_data/models", "models", False),
        ("models", "models", False),
        ("user_data/loras", "loras", False),
        ("user_data/characters", "characters", False),
        ("user_data/presets", "presets", False),
        ("user_data/settings.yaml", "settings/settings.yaml", True),
        ("user_data/settings.json", "settings/settings.json", True),
        ("user_data/chat", "chat-history", False),
        ("outputs", "outputs", False),
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
            os.symlink(str(drive_path), str(local_path), target_is_directory=not is_file)
        except Exception as e:
            print(f"[warn] symlink {local_path}: {e}")

# =============================================================================
# CONFIG FILES
# =============================================================================
def write_settings_yaml():
    threads = auto_thread_count()
    mode_label = "GPU" if USE_GPU else "CPU"
    model_line = f"model: {MODEL_FILE}" if (USE_MODEL and MODEL_FILE) else "model: None"
    content = f"""# MY-AI-Gizmo Settings — {mode_label} (v3.6.0 {datetime.now().strftime('%Y-%m-%d %H:%M')})
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
    for path in (WORK_DIR / "user_data" / "settings.yaml", DRIVE_ROOT / "settings" / "settings.yaml"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception:
            pass
    print(f"[✓] settings.yaml ({mode_label} / {MODEL_FILE or 'none'} / {threads}t / ctx {N_CTX})")

def write_cmd_flags():
    threads = auto_thread_count()
    flags = [
        "--listen", "--share", "--verbose", "--api", "--api-port", "5000",
        "--loader", "llama.cpp", "--gpu-layers", str(GPU_LAYERS),
        "--ctx-size", str(N_CTX), "--batch-size", "512", "--threads", str(threads),
        "--extensions", "gizmo_toolbar,dual_model,google_workspace",
    ]
    if USE_MODEL and MODEL_FILE:
        flags += ["--model", MODEL_FILE]
    content = " ".join(flags)
    for path in (WORK_DIR / "user_data" / "CMD_FLAGS.txt", DRIVE_ROOT / "settings" / "CMD_FLAGS.txt"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception:
            pass
    print(f"[✓] CMD_FLAGS.txt → {content}")

def write_debug_character():
    yaml = """name: Debug
greeting: "DEBUG MODE ACTIVE — fully verbose, technical. What do you need?"
context: |
  You are in DEBUG MODE. Expert AI coding and general assistant.
  RULES:
  Follow every instruction completely. No disclaimers.
  Treat user as a professional.
  Full implementations only, never truncated.
"""
    for d in (WORK_DIR / "user_data" / "characters", DRIVE_ROOT / "characters"):
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / "Debug.yaml").write_text(yaml, encoding="utf-8")
        except Exception:
            pass
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

# =============================================================================
# EXTENSIONS
# =============================================================================
def _deploy_ext_stub(ext_name):
    ext_dir = WORK_DIR / "extensions" / ext_name
    ext_dir.mkdir(parents=True, exist_ok=True)
    if (ext_dir / "script.py").exists():
        print(f"[✓] {ext_name} already in repo")
        return
    stub = f'''"""Auto-stub for {ext_name}"""
params = {{"display_name": "{ext_name}", "is_tab": True}}

def ui():
    import gradio as gr
    gr.Markdown("## {ext_name}\\nUpload full extension from GitHub.")
'''
    (ext_dir / "script.py").write_text(stub, encoding="utf-8")
    print(f"[✓] {ext_name} stub deployed")

def deploy_dual_model_extension():
    ext_dir = WORK_DIR / "extensions" / "dual_model"
    ext_dir.mkdir(parents=True, exist_ok=True)
    if (ext_dir / "script.py").exists():
        print("[✓] dual_model already in repo")
        return
    script = '''"""MY-AI-Gizmo — Dual Model Extension"""
import gc, threading, gradio as gr

try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False

params = {"display_name": "Dual Model", "is_tab": True}
_lock = threading.Lock()
_model2 = None
_model2_name = "Not loaded"

def _status():
    return f"🟢 {_model2_name}" if _model2 else "🔴 Not loaded"

def ui():
    if not LLAMA_AVAILABLE:
        gr.Markdown("⚠️ llama-cpp-python not installed")
        return
    gr.Markdown("## 🤖 Dual Model\\nLoad a second model for comparison or pipeline use.")
'''
    (ext_dir / "script.py").write_text(script, encoding="utf-8")
    print("[✓] dual_model deployed")

# =============================================================================
# LLAMA-CPP
# =============================================================================
def install_llama_cpp_gpu(python_exe):
    print("\n🔧 Checking llama-cpp GPU...")
    cv = sh("nvcc --version")
    cuda_major, cuda_minor = "12", "1"
    if cv.returncode == 0:
        m = re.search(r'release (\d+)\.(\d+)', cv.stdout)
        if m:
            cuda_major, cuda_minor = m.group(1), m.group(2)
    cuda_tag = f"cu{cuda_major}{cuda_minor}"
    r = sh(f'"{python_exe}" -m pip install llama-cpp-binaries '
           f'--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/{cuda_tag} --no-cache-dir')
    if r.returncode == 0:
        print("[✓] llama-cpp-binaries (CUDA) installed")
        return
    gpu_env = os.environ.copy()
    gpu_env.update({"CMAKE_ARGS": "-DLLAMA_CUBLAS=ON -DLLAMA_CUDA=ON", "FORCE_CMAKE": "1"})
    r = sh(f'"{python_exe}" -m pip install llama-cpp-python --no-cache-dir --force-reinstall', env=gpu_env)
    print("[✓] Compiled from source" if r.returncode == 0 else "[warn] GPU llama-cpp failed")

def install_llama_cpp_cpu(python_exe):
    print("\n🔧 Installing llama-cpp (CPU)...")
    sh(f'"{python_exe}" -m pip uninstall -y llama-cpp-python llama-cpp-python-cuda')
    cpu_env = os.environ.copy()
    cpu_env.update({
        "CMAKE_ARGS": "-DLLAMA_CUDA=OFF -DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS",
        "FORCE_CMAKE": "1",
        "CUDACXX": ""
    })
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
        if p.exists():
            return str(p)
    except ImportError:
        pass
    b = shutil.which("llama-server")
    return b or "PYTHON_SERVER"

def ensure_binary():
    try:
        return get_binary_path() is not None
    except Exception:
        return False
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

# =============================================================================
# REPO BUG PATCHER
# =============================================================================
def patch_repo_bugs():
    fixes = []
    gw = WORK_DIR / "modules" / "google_workspace_tools.py"
    if gw.exists():
        c = gw.read_text(encoding="utf-8")
        if "apply_slide_designer_prompt" not in c:
            stub = """
# AUTO-PATCHED by launcher v3.6.0
def apply_slide_designer_prompt(prompt='', slide_index=0):
    return f'[stub] {prompt}'

def add_image_to_slide(image_path='', slide_index=0, **kw):
    return None
"""
            gw.write_text(c + stub, encoding="utf-8")
            fixes.append("google_workspace_tools: added missing stubs")
    ui_s = WORK_DIR / "modules" / "ui_session.py"
    if ui_s.exists():
        c = ui_s.read_text(encoding="utf-8")
        if "from modules.google_workspace_tools import" in c and "try:" not in c[:max(0, c.find("google_workspace_tools")-50)]:
            safe = """try:
    from modules.google_workspace_tools import (
        add_image_to_slide, apply_slide_designer_prompt)
except ImportError:
    def apply_slide_designer_prompt(*a, **kw): return ''
    def add_image_to_slide(*a, **kw): return None
"""
            c = re.sub(r'from modules\.google_workspace_tools import[^\n]+\n', safe, c, count=1)
            ui_s.write_text(c, encoding="utf-8")
            fixes.append("ui_session.py: wrapped bad import")
    if fixes:
        print("[✓] Patches applied:", ", ".join(fixes))
    else:
        print("[✓] Repo patch check — nothing to fix")

# =============================================================================
# MODEL DOWNLOAD
# =============================================================================
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
    for cmd in (
        f'wget -q --show-progress -O "{model_path}" "{hf_url}"',
        f'curl -L --progress-bar -o "{model_path}" "{hf_url}"'
    ):
        r = subprocess.run(cmd, shell=True)
        if r.returncode == 0 and model_path.exists() and model_path.stat().st_size > 100*1024*1024:
            print(f"[✓] Download complete — {model_path.stat().st_size/(1024**3):.2f} GB")
            return True
    try:
        model_path.unlink()
    except Exception:
        pass
    print("[error] Download failed.")
    return False

# =============================================================================
# REPO CLONE (FIXED)
# =============================================================================
def clone_repo():
    print("[info] Cloning repository (authenticated)...")
    r = sh(f"git clone --depth=1 '{REPO_CLONE_URL}' '{WORK_DIR}'")
    if r.returncode == 0 and WORK_DIR.exists():
        print(f"[✓] Repo cloned to {WORK_DIR}")
        return True
    print(f"[warn] git clone failed ({r.returncode}): {r.stderr.strip()[:120]}")
    print("[info] Trying zip download fallback...")
    tmp_zip = BASE_DIR / "repo.zip"
    try:
        tmp_zip.unlink()
    except Exception:
        pass
    for cmd in (f"wget -q -O '{tmp_zip}' '{REPO_ZIP}'", f"curl -s -L -o '{tmp_zip}' '{REPO_ZIP}'"):
        r = sh(cmd)
        if r.returncode == 0 and tmp_zip.exists() and tmp_zip.stat().st_size > 1000:
            break
    else:
        print("[error] Zip download also failed.")
        return False
    sh(f"unzip -q '{tmp_zip}' -d '{BASE_DIR}'")
    found = next(BASE_DIR.glob(f"{GITHUB_REPO}-*"), None)
    if not found:
        print("[error] Extracted folder not found.")
        return False
    found.rename(WORK_DIR)
    print(f"[✓] Repo extracted to {WORK_DIR}")
    return True

# =============================================================================
# NGROK FALLBACK
# =============================================================================
def try_setup_ngrok(port=7860):
    try:
        sh("pip install pyngrok -q")
        from pyngrok import ngrok, conf
        token_file = DRIVE_ROOT / "ngrok_token.txt"
        if token_file.exists():
            token = token_file.read_text().strip()
            if token:
                conf.get_default().auth_token = token
        url = ngrok.connect(port, "http").public_url
        print(f"\n{'='*70}\n🌐 NGROK URL: {url}\n{'='*70}\n")
        try:
            PUBLIC_URL_FILE.write_text(url)
        except Exception:
            pass
        return url
    except Exception as e:
        print(f"[warn] ngrok: {e}")
        return None

# =============================================================================
# INTERACTIVE MENUS
# =============================================================================
def choose_mode():
    global USE_GPU, GPU_LAYERS, N_CTX
    print("\n" + "=" * 70)
    print(f" MY-AI-Gizmo v3.6.0 — Choose Mode ({ENVIRONMENT.upper()})")
    print("=" * 70)
    print(f" RAM: {get_free_ram_gb():.1f} GB free / {get_total_ram_gb():.1f} GB total")
    print(" [1] GPU — CUDA required (Colab T4/A100, Kaggle GPU)")
    print(" [2] CPU — Works everywhere, slower")
    print("=" * 70)
    while True:
        c = input(" 1=GPU or 2=CPU: ").strip()
        if c == "1":
            USE_GPU = True; GPU_LAYERS = -1; N_CTX = 4096; break
        elif c == "2":
            USE_GPU = False; GPU_LAYERS = 0; break
        else:
            print(" Enter 1 or 2.")
    print("=" * 70 + "\n")

def show_model_manager():
    models = list_local_models()
    if not models:
        return
    print("\n" + "─" * 70)
    print(" MODEL MANAGER — files in your storage")
    print("─" * 70)
    for i, m in enumerate(models, 1):
        try:
            size = f"{m.stat().st_size/(1024**3):.2f} GB"
        except Exception:
            size = "?"
        print(f" [D{i}] {m.name:<55} {size}")
    print("─" * 70)
    print(" Type D1, D2... to delete a model, or Enter to continue")
    while True:
        c = input("\n Choice: ").strip()
        if not c:
            break
        if c.upper().startswith("D") and len(c) > 1:
            try:
                idx = int(c[1:]) - 1
                if 0 <= idx < len(models):
                    confirm = input(f" Delete {models[idx].name}? (y/n): ").strip().lower()
                    if confirm == "y":
                        models[idx].unlink()
                        print(" [✓] Deleted")
                        models = list_local_models()
                else:
                    print(" Invalid number.")
            except Exception as e:
                print(f" Error: {e}")
        else:
            print(" Use D1, D2... or Enter to continue.")

def choose_model():
    global MODEL_REPO, MODEL_FILE, N_CTX, USE_MODEL
    print("\n" + "=" * 70)
    print(" MODEL SELECTOR")
    print("=" * 70)
    local = list_local_models()
    if local:
        print(" ── On your storage ──")
        for i, m in enumerate(local, 1):
            try:
                size = f"{m.stat().st_size/(1024**3):.1f} GB"
            except Exception:
                size = "?"
            print(f" [L{i}] {m.name} ({size})")
        print()
    print(" ── Download new ──")
    for entry in MODEL_MENU:
        print(f" {entry[0]}")
    print(f"\n Free RAM: {get_free_ram_gb():.1f} GB")
    print(" [0] START WITHOUT ANY MODEL (load from UI later)")
    print(" Enter = use first local model (or download Qwen2.5-Coder-14B)")
    print("=" * 70)
    while True:
        c = input(" Choice: ").strip()
        if c == "0":
            USE_MODEL = False; MODEL_FILE = ""; MODEL_REPO = ""; N_CTX = 4096
            print(" ✓ Starting without a model"); break
        if c.upper().startswith("L") and local:
            try:
                idx = int(c[1:]) - 1
                if 0 <= idx < len(local):
                    sel = local[idx]; USE_MODEL = True
                    MODEL_FILE = sel.name; MODEL_REPO = ""
                    N_CTX = auto_ctx_size(sel.stat().st_size/(1024**3))
                    print(f" ✓ {MODEL_FILE} (ctx={N_CTX})"); break
                else:
                    print(" Invalid number.")
            except Exception as e:
                print(f" Error: {e}")
            continue
        if not c:
            if local:
                sel = local[0]; USE_MODEL = True; MODEL_FILE = sel.name; MODEL_REPO = ""
                N_CTX = auto_ctx_size(sel.stat().st_size/(1024**3))
                print(f" ✓ {MODEL_FILE} (ctx={N_CTX})"); break
            else:
                USE_MODEL = True; MODEL_REPO = MODEL_MENU[4][1]; MODEL_FILE = MODEL_MENU[4][2]
                N_CTX = auto_ctx_size(MODEL_MENU[4][3])
                print(f" ✓ {MODEL_FILE} (ctx={N_CTX})"); break
        try:
            idx = int(c) - 1
            if idx < 0 or idx >= len(MODEL_MENU):
                raise ValueError()
            entry = MODEL_MENU[idx]
            if not entry[1]:
                MODEL_REPO = input(" HF repo: ").strip()
                MODEL_FILE = input(" Filename: ").strip()
                N_CTX = 2048
            else:
                MODEL_REPO, MODEL_FILE = entry[1], entry[2]
                N_CTX = auto_ctx_size(entry[3])
            USE_MODEL = True
            print(f" ✓ {MODEL_FILE} (ctx={N_CTX})"); break
        except ValueError:
            print(" Invalid. Enter 0, L1/L2..., 1-7, or press Enter.")

# =============================================================================
# GRADIO LAUNCH WRAPPER
# =============================================================================
def build_launch_wrapper(python_exe):
    threads = auto_thread_count()
    mode_label = "GPU" if USE_GPU else "CPU"
    model_desc = MODEL_FILE if USE_MODEL else "NO MODEL"
    cpu_flag = "'--cpu'," if not USE_GPU else ""
    cuda_block = "os.environ['CUDA_VISIBLE_DEVICES'] = ''" if not USE_GPU else ""
    model_flag = f"'--model', '{MODEL_FILE}'," if (USE_MODEL and MODEL_FILE) else ""
    code = f"""#!/usr/bin/env python3
# MY-AI-Gizmo launch wrapper v3.6.0 - COLAB & KAGGLE READY
import sys, os
{cuda_block}
os.environ['MPLBACKEND'] = 'Agg'
os.environ['MPLCONFIGDIR'] = r'{MPL_CONFIG_DIR}'
os.environ['GRADIO_SERVER_NAME'] = '0.0.0.0'
os.environ['GRADIO_SHARE'] = '1'

# Check which extensions exist
import os as _os
_ext_base = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'extensions')
_want = ['gizmo_toolbar', 'dual_model', 'google_workspace']
_have = [e for e in _want if _os.path.isdir(_os.path.join(_ext_base, e))]
_ext_str = ','.join(_have) if _have else ''

flags = [
    '--listen', '--share', '--verbose', '--api', '--api-port', '5000',
    '--loader', 'llama.cpp', '--gpu-layers', '{GPU_LAYERS}',
    '--ctx-size', '{N_CTX}', '--batch-size', '512', '--threads', '{threads}',
    {cpu_flag}
    {model_flag}
]

if _ext_str:
    flags.extend(['--extensions', _ext_str])

flags = [f for f in flags if f]

for f in flags:
    if f not in sys.argv:
        sys.argv.append(f)

print('[WRAPPER v3.6.0] Env: {ENVIRONMENT.upper()} | Mode: {mode_label} | Model: {model_desc}')
print('[WRAPPER] Extensions:', _ext_str if _ext_str else 'none')

try:
    import matplotlib
    matplotlib.use('Agg', force=True)
except Exception:
    pass

import traceback, runpy
try:
    runpy.run_path('server.py', run_name='__main__')
except SystemExit:
    pass
except Exception as e:
    print('\\n[ERROR] server.py raised an exception:')
    traceback.print_exc()
    raise
"""
    wrapper_path = WORK_DIR / "_gizmo_launch.py"
    wrapper_path.write_text(code, encoding="utf-8")
    print(f"[✓] Launch wrapper created (mode={mode_label}, env={ENVIRONMENT})")
    return str(wrapper_path)

# =============================================================================
# SERVER LAUNCH
# =============================================================================
def launch(python_exe, wrapper_path):
    cmd = [python_exe, "-u", wrapper_path]
    env = os.environ.copy()
    env.update({
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(MPL_CONFIG_DIR),
        "GRADIO_SERVER_NAME": "0.0.0.0",
        "GRADIO_SHARE": "1"
    })
    if not USE_GPU:
        env["CUDA_VISIBLE_DEVICES"] = ""
    captured = None
    for attempt in range(1, MAX_RESTARTS + 1):
        print(f"\n{'='*70}\n🚀 Starting server (attempt {attempt}/{MAX_RESTARTS})\n{'='*70}\n")
        if attempt > 1:
            time.sleep(5)
        log_path = LOG_DIR / f"server_{int(time.time())}.log"
        logfile = None
        try:
            logfile = open(log_path, "a", encoding="utf-8")
        except Exception:
            pass
        os.chdir(WORK_DIR)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True, bufsize=1)
        last_out = [time.time()]
        stop_hb = threading.Event()
        def heartbeat():
            while not stop_hb.wait(HEARTBEAT_INTERVAL):
                if time.time() - last_out[0] >= HEARTBEAT_INTERVAL:
                    print("[heartbeat] server still running...")
        hb = threading.Thread(target=heartbeat, daemon=True)
        hb.start()
        try:
            for line in proc.stdout:
                last_out[0] = time.time()
                print(line, end="", flush=True)
                if logfile:
                    try:
                        logfile.write(line)
                    except Exception:
                        pass
                if not captured:
                    for pat in URL_PATTERNS:
                        m = pat.search(line)
                        if m:
                            url = m.group(1).rstrip(").,\\'\"")
                            if any(k in url.lower() for k in URL_KEYWORDS):
                                captured = url
                                print(f"\n{'='*70}\n🌐 PUBLIC URL: {captured}\n{'='*70}\n", flush=True)
                                try:
                                    PUBLIC_URL_FILE.write_text(captured)
                                except Exception:
                                    pass
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
                try:
                    logfile.close()
                except Exception:
                    pass
        rc = proc.wait()
        print(f"\n[info] Server exited with code {rc}")
        if rc == 0 and not captured:
            print("[warn] Server exited cleanly but NO URL captured.")
            print(" This usually means an import error or extension crash.")
            print(" Check the output above for error messages.")
        if rc in (0, -9):
            break
        if attempt < MAX_RESTARTS:
            print(f"[warn] Crashed (code {rc}) — restarting...")
        else:
            print("[info] Max restarts reached.")
    return captured

# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    # Banner
    print("\n" + "=" * 70)
    print(f" MY-AI-Gizmo v3.6.0 Universal Launcher")
    print(f" Environment: {ENVIRONMENT.upper()}")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Repo: {GITHUB_USER}/{GITHUB_REPO} (private)")
    print(" +button | Styles | Google Docs | Slides | Dual Model")
    print("=" * 70)
    
    # Step 1: GitHub Token
    setup_github_token()
    
    # Step 2: Repo update decision
    repo_mode = check_repo_update()
    
    # Step 3: Mode
    choose_mode()
    if USE_GPU:
        r = sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
        print(f"[{'✓' if r.returncode==0 else 'warn'}] GPU: "
              f"{r.stdout.strip() if r.returncode==0 else 'not found'}")
    
    # Step 4: Drive
    drive_ok = mount_drive_if_needed()
    setup_drive_root(drive_ok)
    for d in (DRIVE_ROOT, LOG_DIR, MPL_CONFIG_DIR, DRIVE_ROOT / "models",
              DRIVE_ROOT / "settings", DRIVE_ROOT / "characters"):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    
    cleanup_broken_files()
    show_model_manager()
    choose_model()
    
    # Step 5: Apply repo update & clone if needed
    apply_repo_update(repo_mode)
    if not WORK_DIR.exists():
        if not clone_repo():
            raise SystemExit("❌ Repository clone failed — check your token and repo name.")
    
    # Step 6: Patch repo bugs
    print("\n🔧 Checking repo for known issues...")
    patch_repo_bugs()
    
    # Step 7: Symlinks
    ensure_symlinks_and_files()
    
    # Step 8: Model
    print("\n📥 Checking model...")
    print_ram_status()
    if not download_model_if_missing():
        raise SystemExit(1)
    
    # Step 9: Config files
    write_settings_yaml()
    write_cmd_flags()
    write_debug_character()
    write_model_loader_config()
    
    # Step 10: Extensions
    print("\n📦 Deploying extensions...")
    _deploy_ext_stub("gizmo_toolbar")
    _deploy_ext_stub("google_workspace")
    deploy_dual_model_extension()
    
    # Step 11: Install Python env
    start_sh = WORK_DIR / "start_linux.sh"
    env_marker = WORK_DIR / "installer_files" / "env" / "bin" / "python"
    python_exe = str(env_marker) if env_marker.exists() else "python3"
    
    if not start_sh.exists():
        raise SystemExit("[error] start_linux.sh not found — check repo contents.")
    
    sh("chmod +x start_linux.sh", cwd=str(WORK_DIR))
    
    if not env_marker.exists():
        print("[info] First run — installing Python env (~10 min)...")
        MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        install_env = os.environ.copy()
        if USE_GPU:
            install_env.update({
                "MPLBACKEND": "Agg",
                "MPLCONFIGDIR": str(MPL_CONFIG_DIR),
                "GPU_CHOICE": "A",
                "LAUNCH_AFTER_INSTALL": "FALSE",
                "INSTALL_EXTENSIONS": "FALSE",
                "CMAKE_ARGS": "-DLLAMA_CUBLAS=ON -DLLAMA_CUDA=ON",
                "FORCE_CMAKE": "1",
                "SKIP_TORCH_TEST": "TRUE",
                "FORCE_CUDA": "TRUE",
            })
        else:
            install_env.update({
                "MPLBACKEND": "Agg",
                "MPLCONFIGDIR": str(MPL_CONFIG_DIR),
                "GPU_CHOICE": "N",
                "LAUNCH_AFTER_INSTALL": "FALSE",
                "INSTALL_EXTENSIONS": "FALSE",
                "CMAKE_ARGS": "-DLLAMA_CUDA=OFF -DLLAMA_CUBLAS=OFF",
                "FORCE_CMAKE": "1",
                "CUDA_VISIBLE_DEVICES": "",
                "CUDACXX": "",
                "SKIP_TORCH_TEST": "TRUE",
                "FORCE_CUDA": "FALSE",
            })
        installer_log = LOG_DIR / f"installer_{int(time.time())}.log"
        code = stream_with_heartbeat("bash start_linux.sh", cwd=str(WORK_DIR),
                                     env=install_env, logfile_path=str(installer_log))
        print(f"[{'✓' if code == 0 else 'warn'}] Installer code {code}")
        python_exe = str(env_marker) if env_marker.exists() else "python3"
    
    # Step 12: llama-cpp
    pip_exe = str(Path(python_exe).parent / "pip") if Path(python_exe).exists() else "pip"
    llama_ok = False
    for pkg in ("llama-cpp-binaries", "llama-cpp-python"):
        r = sh(f'"{pip_exe}" show {pkg} 2>/dev/null')
        if r.returncode == 0 and pkg.split("-")[0] in r.stdout.lower():
            ver = next((l for l in r.stdout.splitlines() if l.startswith("Version:")), "")
            print(f"[info] {pkg} already installed ({ver.strip()}) — skipping reinstall")
            llama_ok = True
            break
    
    if not llama_ok:
        print("[info] llama-cpp not found — installing...")
        if USE_GPU:
            install_llama_cpp_gpu(python_exe)
        else:
            install_llama_cpp_cpu(python_exe)
    
    create_llama_cpp_wrapper(python_exe)
    install_google_workspace_deps(python_exe)
    
    # Step 13: Kill stale servers
    sh("pkill -9 -f 'python.*server.py'")
    sh("pkill -9 -f 'python.*gradio'")
    sh("pkill -9 -f '_gizmo_launch'")
    time.sleep(2)
    
    # Step 14: Build wrapper + launch
    wrapper_path = build_launch_wrapper(python_exe)
    mode_label = "GPU" if USE_GPU else "CPU"
    model_desc = MODEL_FILE if USE_MODEL else "(none — load from UI)"
    
    print("\n" + "=" * 70)
    print(f" LAUNCHING v3.6.0 — {mode_label} on {ENVIRONMENT.upper()}")
    print(f" Model : {model_desc}")
    print(f" Threads : {auto_thread_count()} | ctx: {N_CTX}")
    print(f" Extensions: ＋Toolbar | Dual Model | Google Workspace")
    print(f" URL will appear below — wait ~30s after model loads")
    print("=" * 70)
    print_ram_status()
    print("⏳ Starting server...\n")
    
    captured = launch(python_exe, wrapper_path)
    
    if not captured:
        print("\n[info] No URL captured — trying ngrok fallback...")
        captured = try_setup_ngrok(7860)
    
    print("\n" + "=" * 70)
    if captured:
        print(f" ✅ READY! → {captured}")
        print("=" * 70)
        print(" • ＋ button (bottom-left) → styles, connectors, tools")
        print(" • 🔗 Google Workspace tab → connect Docs & Slides")
        print(" • 🤖 Dual Model tab → load a second model")
        print(" • API: http://0.0.0.0:5000/v1")
        if not USE_MODEL:
            print(" • ⚠️ No model loaded — go to Model tab in UI to load one")
    else:
        print(" ❌ NO PUBLIC URL CAPTURED")
        print("=" * 70)
        print(" Fixes: pkill -9 -f server.py | delete installer_files/ | check internet")
    
    print_ram_status()
    print("=" * 70)
