#!/usr/bin/env python3
# ================================================================
# MY-AI-Gizmo • KAGGLE LAUNCHER v4.0.0
# ================================================================
# OPTIMIZED FOR KAGGLE NOTEBOOKS
# Supports Kaggle Secrets for secure token storage
# ================================================================

import os, sys, subprocess, shutil, re, time, threading
from pathlib import Path
from datetime import datetime

# ── Environment Detection ───────────────────────────────────────
IN_KAGGLE = os.path.exists('/kaggle/working')
ENVIRONMENT = "kaggle" if IN_KAGGLE else "colab"

# ── Repo ────────────────────────────────────────────────────────
GITHUB_USER = "leonlazdev-wq"
GITHUB_REPO = "Gizmo_MY_AI"
GITHUB_BRANCH = "main"

# ── Paths ───────────────────────────────────────────────────────
if IN_KAGGLE:
    BASE_DIR = Path("/kaggle/working")
else:
    BASE_DIR = Path("/content")

WORK_DIR = BASE_DIR / "text-generation-webui"
DRIVE_ROOT = BASE_DIR / "MY-AI-Gizmo"
LOG_DIR = DRIVE_ROOT / "logs"
MPL_CONFIG_DIR = DRIVE_ROOT / "matplotlib"
PUBLIC_URL_FILE = DRIVE_ROOT / "public_url.txt"

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
    ("0 START WITHOUT MODEL", "", "", 0),
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
]

# =============================================================================
# KAGGLE SECRETS & GITHUB TOKEN
# =============================================================================
def get_kaggle_secret(key):
    """Try to get a secret from Kaggle's UserSecrets"""
    try:
        from kaggle_secrets import UserSecrets
        secret = UserSecrets().get_secret(key)
        return secret if secret else None
    except Exception:
        return None

def setup_github_token():
    global GITHUB_TOKEN
    
    print("\n" + "=" * 70)
    print(f" MY-AI-Gizmo v4.0.0 — GitHub Authentication (KAGGLE)")
    print("=" * 70)
    
    # Try Kaggle Secrets first
    secret_token = get_kaggle_secret("GITHUB_TOKEN")
    if secret_token:
        GITHUB_TOKEN = secret_token
        print(f" [✓] Using GITHUB_TOKEN from Kaggle Secrets (...{secret_token[-3:]})")
        print("=" * 70)
        return
    
    # Check environment variable
    env_token = os.environ.get("GITHUB_TOKEN", "")
    if env_token and len(env_token) >= 20:
        GITHUB_TOKEN = env_token
        print(f" [✓] Using GITHUB_TOKEN from environment (...{env_token[-3:]})")
        print("=" * 70)
        return
    
    # Check saved token file
    token_file = DRIVE_ROOT / "github_token.txt"
    if token_file.exists():
        try:
            saved = token_file.read_text(encoding="utf-8").strip()
            if len(saved) >= 20:
                print(f" [💾] Saved token found (...{saved[-3:]})")
                ans = input(" Use this token? (y/n): ").strip().lower()
                if ans != "n":
                    GITHUB_TOKEN = saved
                    print(" [✓] Using saved token")
                    print("=" * 70)
                    return
        except Exception:
            pass
    
    # Manual entry
    print("\n ⚠️  NO TOKEN FOUND IN KAGGLE SECRETS")
    print()
    print(" RECOMMENDED: Use Kaggle Secrets (secure, no re-entry needed)")
    print(" 1. Get GitHub token: https://github.com/settings/tokens")
    print("    - Click 'Generate new token (classic)'")
    print("    - Select scope: ✓ repo")
    print(" 2. In Kaggle:")
    print("    - Click 'Add-ons' → 'Secrets'")
    print("    - Create secret: GITHUB_TOKEN = your_token")
    print("    - Toggle ON to activate")
    print(" 3. Restart this notebook")
    print()
    print(" OR enter token now (will be saved locally):")
    print("=" * 70)
    
    while True:
        token = input(" GitHub Token: ").strip()
        if not token:
            print(" [!] Token required to access private repo")
            retry = input(" Try again? (y/n): ").strip().lower()
            if retry != "y":
                raise SystemExit("❌ Token required to clone private repository")
            continue
        
        if not (token.startswith("ghp_") or token.startswith("github_pat_") or len(token) >= 20):
            print(f" [?] Token looks unusual (length: {len(token)})")
            confirm = input(" Continue anyway? (y/n): ").strip().lower()
            if confirm != "y":
                continue
        
        GITHUB_TOKEN = token
        break
    
    # Save for next time
    try:
        DRIVE_ROOT.mkdir(parents=True, exist_ok=True)
        token_file.write_text(GITHUB_TOKEN, encoding="utf-8")
        print(f"\n [✓] Token saved to {token_file}")
        print(" [💡] TIP: Add to Kaggle Secrets to avoid re-entering")
    except Exception as e:
        print(f" [warn] Could not save token: {e}")
    
    print("=" * 70)

# =============================================================================
# UTILITIES
# =============================================================================
def sh(cmd, cwd=None, env=None, capture=True):
    if capture:
        return subprocess.run(cmd, shell=True, cwd=cwd, env=env,
                            capture_output=True, text=True)
    else:
        return subprocess.run(cmd, shell=True, cwd=cwd, env=env)

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

def print_ram_status():
    free = get_free_ram_gb()
    total = get_total_ram_gb()
    used = total - free
    pct = (used / total) if total else 0
    bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
    print(f" RAM [{bar}] {used:.1f}/{total:.1f} GB ({free:.1f} GB free)")

# =============================================================================
# REPO CLONE
# =============================================================================
def clone_repo():
    """Clone repository with proper authentication"""
    print("\n[info] Cloning repository...")
    
    # Build authenticated URL
    clone_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"
    
    # Try git clone
    print(f"[info] Attempting git clone...")
    r = sh(f"git clone --depth=1 '{clone_url}' '{WORK_DIR}'")
    
    if r.returncode == 0 and WORK_DIR.exists():
        print(f"[✓] Repository cloned to {WORK_DIR}")
        return True
    
    # Show error (without exposing token)
    error = r.stderr.strip() if r.stderr else "Unknown error"
    # Remove token from error message
    error = error.replace(GITHUB_TOKEN, "***TOKEN***")
    print(f"[warn] git clone failed (code {r.returncode})")
    print(f"[debug] {error[:200]}")
    
    # Try zip fallback
    print("\n[info] Trying zip download fallback...")
    zip_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"
    tmp_zip = BASE_DIR / "repo.zip"
    
    try:
        tmp_zip.unlink()
    except Exception:
        pass
    
    # Try wget first
    print("[info] Downloading with wget...")
    r = sh(f"wget -q --show-progress -O '{tmp_zip}' '{zip_url}'", capture=False)
    
    if r.returncode != 0 or not tmp_zip.exists() or tmp_zip.stat().st_size < 1000:
        # Try curl
        print("[info] Trying curl...")
        r = sh(f"curl -s -L -o '{tmp_zip}' '{zip_url}'")
    
    if not tmp_zip.exists() or tmp_zip.stat().st_size < 1000:
        print("[error] Zip download failed")
        print("[help] Check:")
        print("  1. Token has 'repo' scope")
        print("  2. Internet is enabled in notebook settings")
        print("  3. Token is not expired")
        return False
    
    # Extract
    print(f"[info] Downloaded {tmp_zip.stat().st_size / 1024:.1f} KB")
    print("[info] Extracting...")
    sh(f"unzip -q '{tmp_zip}' -d '{BASE_DIR}'", capture=False)
    
    # Find extracted folder
    found = next(BASE_DIR.glob(f"{GITHUB_REPO}-*"), None)
    if not found:
        print(f"[error] Could not find extracted folder {GITHUB_REPO}-*")
        return False
    
    # Rename to target
    found.rename(WORK_DIR)
    print(f"[✓] Repository extracted to {WORK_DIR}")
    return True

# =============================================================================
# CONFIG FILES
# =============================================================================
def write_settings_yaml():
    threads = 2
    mode_label = "GPU" if USE_GPU else "CPU"
    model_line = f"model: {MODEL_FILE}" if (USE_MODEL and MODEL_FILE) else "model: None"
    
    content = f"""# MY-AI-Gizmo Settings — {mode_label} (v4.0.0 Kaggle)
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
    print(f"[✓] settings.yaml configured")

def write_cmd_flags():
    flags = [
        "--listen", "--share", "--verbose", "--api", "--api-port", "5000",
        "--loader", "llama.cpp", "--gpu-layers", str(GPU_LAYERS),
        "--ctx-size", str(N_CTX), "--batch-size", "512", "--threads", "2",
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
    print(f"[✓] CMD_FLAGS.txt configured")

# =============================================================================
# SIMPLIFIED SYMLINKS
# =============================================================================
def setup_directories():
    """Create necessary directories"""
    dirs = [
        DRIVE_ROOT / "models",
        DRIVE_ROOT / "settings",
        DRIVE_ROOT / "characters",
        DRIVE_ROOT / "logs",
        DRIVE_ROOT / "matplotlib",
        WORK_DIR / "user_data" / "models",
        WORK_DIR / "user_data" / "characters",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("[✓] Directories created")

# =============================================================================
# MODEL DOWNLOAD
# =============================================================================
def download_model_if_missing():
    if not USE_MODEL:
        print("[info] No model selected — will load from UI")
        return True
    
    models_dir = DRIVE_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / MODEL_FILE
    
    if model_path.exists() and model_path.stat().st_size > 100 * 1024 * 1024:
        print(f"[✓] Model exists ({model_path.stat().st_size/(1024**3):.1f} GB)")
        return True
    
    if not MODEL_REPO:
        print("[warn] No model repo specified")
        return False
    
    print(f"\n📥 DOWNLOADING: {MODEL_FILE}")
    hf_url = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}?download=true"
    
    print(f"[info] From: {MODEL_REPO}")
    r = sh(f'wget --show-progress -O "{model_path}" "{hf_url}"', capture=False)
    
    if r.returncode == 0 and model_path.exists() and model_path.stat().st_size > 100*1024*1024:
        print(f"[✓] Downloaded {model_path.stat().st_size/(1024**3):.2f} GB")
        return True
    
    print("[error] Download failed")
    try:
        model_path.unlink()
    except Exception:
        pass
    return False

# =============================================================================
# INTERACTIVE MENUS
# =============================================================================
def choose_mode():
    global USE_GPU, GPU_LAYERS, N_CTX
    
    print("\n" + "=" * 70)
    print(" MY-AI-Gizmo v4.0.0 — Mode Selection (KAGGLE)")
    print("=" * 70)
    print(f" RAM: {get_free_ram_gb():.1f} GB free / {get_total_ram_gb():.1f} GB total")
    
    # Check for GPU
    r = sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
    has_gpu = r.returncode == 0
    
    if has_gpu:
        print(f" GPU: {r.stdout.strip()}")
        print()
        print(" [1] GPU Mode (recommended if GPU enabled)")
        print(" [2] CPU Mode")
        print("=" * 70)
        
        while True:
            c = input(" Choice (1 or 2): ").strip()
            if c == "1":
                USE_GPU = True; GPU_LAYERS = -1; N_CTX = 4096; break
            elif c == "2":
                USE_GPU = False; GPU_LAYERS = 0; N_CTX = 2048; break
    else:
        print(" GPU: Not detected (enable in notebook settings)")
        print()
        print(" [✓] Using CPU Mode")
        print("=" * 70)
        USE_GPU = False
        GPU_LAYERS = 0
        N_CTX = 2048
        time.sleep(2)
    
    print("=" * 70)

def choose_model():
    global MODEL_REPO, MODEL_FILE, N_CTX, USE_MODEL
    
    print("\n" + "=" * 70)
    print(" MODEL SELECTOR")
    print("=" * 70)
    for entry in MODEL_MENU:
        print(f" {entry[0]}")
    print(f"\n Free RAM: {get_free_ram_gb():.1f} GB")
    print(" Enter = start without model (fastest)")
    print("=" * 70)
    
    while True:
        c = input(" Choice: ").strip()
        
        if not c or c == "0":
            USE_MODEL = False
            MODEL_FILE = ""
            MODEL_REPO = ""
            print(" [✓] Will start without model")
            break
        
        try:
            idx = int(c) - 1
            if idx < 0 or idx >= len(MODEL_MENU) - 1:
                raise ValueError()
            
            entry = MODEL_MENU[idx]
            MODEL_REPO = entry[1]
            MODEL_FILE = entry[2]
            N_CTX = 2048  # Conservative for Kaggle
            USE_MODEL = True
            print(f" [✓] Selected: {MODEL_FILE}")
            break
        except ValueError:
            print(" Invalid. Enter 1-5 or 0")

# =============================================================================
# MAIN
# =============================================================================
def main():
    print("\n" + "=" * 70)
    print(" MY-AI-Gizmo v4.0.0 — KAGGLE OPTIMIZED")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    if not IN_KAGGLE:
        print("\n [!] WARNING: Not running in Kaggle environment")
        print(f" [!] Detected path: {os.getcwd()}")
        print(" [!] This script is optimized for Kaggle notebooks")
        print()
    
    # Check internet
    print("\n[info] Checking internet access...")
    r = sh("ping -c 1 8.8.8.8")
    if r.returncode != 0:
        print("[error] No internet access!")
        print("[help] Enable internet in notebook settings:")
        print("  Settings → Internet → ON")
        raise SystemExit(1)
    print("[✓] Internet OK")
    
    # Step 1: GitHub Token
    setup_github_token()
    
    # Step 2: Mode
    choose_mode()
    
    # Step 3: Model
    choose_model()
    
    # Step 4: Setup directories
    setup_directories()
    
    # Step 5: Clone repo
    if WORK_DIR.exists():
        print(f"\n[info] Repository already exists at {WORK_DIR}")
        ans = input("Delete and re-clone? (y/n): ").strip().lower()
        if ans == "y":
            print("[info] Removing old repository...")
            shutil.rmtree(WORK_DIR)
    
    if not WORK_DIR.exists():
        if not clone_repo():
            raise SystemExit("❌ Repository clone failed")
    
    # Step 6: Model download
    if USE_MODEL:
        print("\n📥 Checking model...")
        print_ram_status()
        if not download_model_if_missing():
            print("[warn] Model download failed — will continue without model")
            USE_MODEL = False
    
    # Step 7: Config files
    print("\n🔧 Writing configuration...")
    write_settings_yaml()
    write_cmd_flags()
    
    # Final instructions
    print("\n" + "=" * 70)
    print(" ✅ SETUP COMPLETE!")
    print("=" * 70)
    print(f" Repository: {WORK_DIR}")
    print(f" Settings: {DRIVE_ROOT}")
    print(f" Model: {MODEL_FILE if USE_MODEL else 'None (load from UI)'}")
    print()
    print(" NEXT STEPS:")
    print(" 1. Review the repository structure")
    print(" 2. Install dependencies (if needed)")
    print(" 3. Run the server script")
    print()
    print(" To start the server, run:")
    print(f"   cd {WORK_DIR}")
    print("   bash start_linux.sh")
    print("=" * 70)
    print_ram_status()
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[info] Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[error] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
