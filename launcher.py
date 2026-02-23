#!/usr/bin/env python3
"""
MY-AI-Gizmo Colab launcher (fixed):
- correctly links user_data/models (the path webui actually reads)
- supports running with no startup model
- avoids writing/forcing --model when no model is selected
- handles already-mounted Drive gracefully
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

try:
    from google.colab import drive as colab_drive
    IN_COLAB = True
except Exception:
    colab_drive = None
    IN_COLAB = False

WORK_DIR = Path("/content/text-generation-webui")
DRIVE_ROOT = Path("/content/drive/MyDrive/MY-AI-Gizmo")

MODEL_MENU = [
    ("1  TinyLlama-1.1B  Q4_K_M  [~0.7 GB]", "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF", "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf", 0.7),
    ("2  Phi-3-mini-4k   Q4_K_M  [~2.2 GB]", "bartowski/Phi-3-mini-4k-instruct-GGUF", "Phi-3-mini-4k-instruct-Q4_K_M.gguf", 2.2),
    ("3  Mistral-7B-v0.3 Q4_K_M  [~4.4 GB]", "bartowski/Mistral-7B-v0.3-GGUF", "Mistral-7B-v0.3-Q4_K_M.gguf", 4.4),
    ("4  Qwen2.5-Coder-7B Q4_K_M [~4.7 GB]", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", "qwen2.5-coder-7b-instruct-q4_k_m.gguf", 4.7),
    ("5  Qwen2.5-Coder-14B Q4_K_M [~8.9 GB]", "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF", "qwen2.5-coder-14b-instruct-q4_k_m.gguf", 8.9),
    ("6  DeepSeek-Coder-33B Q4_K_M [~19 GB]", "TheBloke/deepseek-coder-33B-instruct-GGUF", "deepseek-coder-33b-instruct.Q4_K_M.gguf", 19.0),
]

MODEL_REPO = ""
MODEL_FILE = ""
USE_MODEL = False


def sh(cmd, cwd=None, env=None):
    return subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)


def mount_drive_if_needed():
    if not IN_COLAB:
        return

    # If already mounted, don't try to remount (prevents "mountpoint must not already contain files").
    if Path("/content/drive/MyDrive").exists():
        print("[info] Google Drive appears mounted already; skipping mount.")
        return

    try:
        colab_drive.mount("/content/drive", force_remount=False)
        print("[✓] Google Drive mounted")
    except Exception as e:
        print(f"[warn] Drive mount skipped: {e}")


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

    for local, drive_rel, is_file in links_map:
        drive_path = DRIVE_ROOT / drive_rel
        local_path = WORK_DIR / local

        if is_file:
            drive_path.parent.mkdir(parents=True, exist_ok=True)
            if not drive_path.exists():
                drive_path.write_text("", encoding="utf-8")
        else:
            drive_path.mkdir(parents=True, exist_ok=True)

        if local_path.exists() or local_path.is_symlink():
            if local_path.is_symlink() or local_path.is_file():
                local_path.unlink()
            else:
                shutil.rmtree(local_path)

        local_path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(str(drive_path), str(local_path), target_is_directory=not is_file)


def choose_model():
    global MODEL_REPO, MODEL_FILE, USE_MODEL

    print("\n0  Start with NO model loaded")
    for item in MODEL_MENU:
        print(item[0])

    choice = input("Choice (0-6): ").strip() or "0"
    if choice == "0":
        USE_MODEL = False
        MODEL_REPO = ""
        MODEL_FILE = ""
        print("[✓] Starting without loading a model.")
        return

    idx = int(choice) - 1
    if idx < 0 or idx >= len(MODEL_MENU):
        raise ValueError("Invalid model selection")

    _, MODEL_REPO, MODEL_FILE, _ = MODEL_MENU[idx]
    USE_MODEL = True
    print(f"[✓] Selected: {MODEL_FILE}")


def download_model_if_missing():
    if not USE_MODEL:
        return True

    models_dir = DRIVE_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / MODEL_FILE

    if model_path.exists() and model_path.stat().st_size > 100 * 1024 * 1024:
        print(f"[✓] Model exists: {model_path}")
        return True

    hf_url = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}?download=true"
    print(f"[info] Downloading: {hf_url}")

    for cmd in [
        f'wget -q --show-progress -O "{model_path}" "{hf_url}"',
        f'curl -L --progress-bar -o "{model_path}" "{hf_url}"',
    ]:
        r = subprocess.run(cmd, shell=True)
        if r.returncode == 0 and model_path.exists() and model_path.stat().st_size > 100 * 1024 * 1024:
            print(f"[✓] Downloaded: {model_path}")
            return True

    print("[error] Failed to download model")
    return False


def write_cmd_flags():
    flags = [
        "--listen", "--share", "--verbose", "--api", "--api-port", "5000",
        "--loader", "llama.cpp", "--gpu-layers", "-1", "--ctx-size", "4096",
        "--batch-size", "512", "--threads", "2",
        "--extensions", "gizmo_toolbar,dual_model,google_workspace",
    ]

    if USE_MODEL and MODEL_FILE:
        flags += ["--model", MODEL_FILE]

    content = " ".join(flags)
    path = WORK_DIR / "user_data" / "CMD_FLAGS.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[✓] CMD_FLAGS.txt -> {content}")


def write_settings_yaml():
    model_line = f"model: {MODEL_FILE}" if USE_MODEL and MODEL_FILE else "model: None"
    settings = f"""listen: true
share: true
loader: llama.cpp
n_ctx: 4096
n_batch: 512
n_gpu_layers: -1
threads: 2
{model_line}
api: true
api_port: 5000
"""
    p = WORK_DIR / "user_data" / "settings.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(settings, encoding="utf-8")
    print("[✓] settings.yaml written")


def launch():
    env_python = WORK_DIR / "installer_files" / "env" / "bin" / "python"
    python_exe = str(env_python) if env_python.exists() else "python3"

    cmd = [python_exe, "server.py"]
    if USE_MODEL and MODEL_FILE:
        cmd += ["--model", MODEL_FILE]

    # If no model chosen, do not pass --model, allowing clean startup with model menu at None.
    cmd += [
        "--listen", "--share", "--api", "--api-port", "5000",
        "--loader", "llama.cpp", "--gpu-layers", "-1", "--ctx-size", "4096",
        "--batch-size", "512", "--threads", "2",
        "--extensions", "gizmo_toolbar,dual_model,google_workspace",
    ]

    print("[info] Launch command:", " ".join(cmd))
    os.chdir(WORK_DIR)
    os.execv(cmd[0], cmd)


if __name__ == "__main__":
    mount_drive_if_needed()
    ensure_symlinks_and_files()
    choose_model()
    if not download_model_if_missing():
        raise SystemExit(1)
    write_settings_yaml()
    write_cmd_flags()
    launch()
