import html
import subprocess
import threading
from pathlib import Path

import gradio as gr

params = {
    "display_name": "📦 Model Hub",
    "is_tab": True,
}

MODELS = [
  {"name": "TinyLlama-1.1B-Chat", "file": "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf", "repo": "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF", "size_gb": 0.7, "hw": "CPU", "tag": "Chat", "desc": "Tiny and fast, great for low-RAM devices"},
  {"name": "Phi-3-Mini-4k", "file": "Phi-3-mini-4k-instruct-Q4_K_M.gguf", "repo": "bartowski/Phi-3-mini-4k-instruct-GGUF", "size_gb": 2.2, "hw": "CPU+GPU", "tag": "Chat", "desc": "Microsoft's efficient small model, punches above weight"},
  {"name": "Gemma-2B-Instruct", "file": "gemma-2b-it-Q4_K_M.gguf", "repo": "bartowski/gemma-2b-it-GGUF", "size_gb": 1.6, "hw": "CPU", "tag": "Chat", "desc": "Google's lightweight instruction model"},
  {"name": "Llama-3.2-3B-Instruct", "file": "Llama-3.2-3B-Instruct-Q4_K_M.gguf", "repo": "bartowski/Llama-3.2-3B-Instruct-GGUF", "size_gb": 2.0, "hw": "CPU", "tag": "Chat", "desc": "Meta's latest compact Llama, very capable for its size"},
  {"name": "Mistral-7B-Instruct-v0.3", "file": "Mistral-7B-v0.3-Q4_K_M.gguf", "repo": "bartowski/Mistral-7B-v0.3-GGUF", "size_gb": 4.4, "hw": "CPU+GPU", "tag": "Chat", "desc": "Best general-purpose 7B, fast and reliable"},
  {"name": "Llama-3.1-8B-Instruct", "file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "size_gb": 4.9, "hw": "CPU+GPU", "tag": "Chat", "desc": "Meta's flagship 8B, excellent instruction following"},
  {"name": "Phi-3-Medium-4k", "file": "Phi-3-medium-4k-instruct-Q4_K_M.gguf", "repo": "bartowski/Phi-3-medium-4k-instruct-GGUF", "size_gb": 7.8, "hw": "GPU", "tag": "Chat", "desc": "Microsoft's 14B model, strong reasoning in small package"},
  {"name": "Gemma-2-9B-Instruct", "file": "gemma-2-9b-it-Q4_K_M.gguf", "repo": "bartowski/gemma-2-9b-it-GGUF", "size_gb": 5.8, "hw": "CPU+GPU", "tag": "Chat", "desc": "Google's Gemma 2 9B, very strong for its size"},
  {"name": "Llama-3.1-70B-Instruct", "file": "Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf", "repo": "bartowski/Meta-Llama-3.1-70B-Instruct-GGUF", "size_gb": 42.5, "hw": "GPU", "tag": "Chat", "desc": "Meta's big 70B, near GPT-4 quality, needs lots of VRAM"},
  {"name": "Qwen2.5-Coder-7B", "file": "qwen2.5-coder-7b-instruct-q4_k_m.gguf", "repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", "size_gb": 4.7, "hw": "CPU+GPU", "tag": "Code", "desc": "Best open-source 7B coding model, beats Codex"},
  {"name": "Qwen2.5-Coder-14B", "file": "qwen2.5-coder-14b-instruct-q4_k_m.gguf", "repo": "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF", "size_gb": 8.9, "hw": "GPU", "tag": "Code", "desc": "Qwen's 14B coder, exceptional multi-language support"},
  {"name": "Qwen2.5-Coder-32B", "file": "qwen2.5-coder-32b-instruct-q4_k_m.gguf", "repo": "Qwen/Qwen2.5-Coder-32B-Instruct-GGUF", "size_gb": 19.8, "hw": "GPU", "tag": "Code", "desc": "Top-tier open coder, rivals GPT-4o for code tasks"},
  {"name": "DeepSeek-Coder-V2-Lite", "file": "DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf", "repo": "bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF", "size_gb": 9.7, "hw": "GPU", "tag": "Code", "desc": "DeepSeek's efficient coder, excellent for complex tasks"},
  {"name": "CodeLlama-7B-Instruct", "file": "codellama-7b-instruct.Q4_K_M.gguf", "repo": "TheBloke/CodeLlama-7B-Instruct-GGUF", "size_gb": 3.8, "hw": "CPU+GPU", "tag": "Code", "desc": "Meta's original code model, great Python and JS"},
  {"name": "CodeLlama-13B-Instruct", "file": "codellama-13b-instruct.Q4_K_M.gguf", "repo": "TheBloke/CodeLlama-13B-Instruct-GGUF", "size_gb": 7.3, "hw": "GPU", "tag": "Code", "desc": "Larger CodeLlama, better at long context code tasks"},
  {"name": "CodeGemma-7B-Instruct", "file": "codegemma-7b-it-Q4_K_M.gguf", "repo": "bartowski/codegemma-7b-it-GGUF", "size_gb": 5.0, "hw": "CPU+GPU", "tag": "Code", "desc": "Google's CodeGemma, strong at code completion"},
  {"name": "StarCoder2-7B", "file": "starcoder2-7b-Q4_K_M.gguf", "repo": "bartowski/starcoder2-7b-GGUF", "size_gb": 4.3, "hw": "CPU+GPU", "tag": "Code", "desc": "BigCode's open coder trained on 600+ languages"},
  {"name": "DeepSeek-R1-7B", "file": "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf", "repo": "bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF", "size_gb": 4.7, "hw": "CPU+GPU", "tag": "Reasoning", "desc": "Distilled R1 thinking model, shows its reasoning chain"},
  {"name": "DeepSeek-R1-14B", "file": "DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf", "repo": "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF", "size_gb": 9.0, "hw": "GPU", "tag": "Reasoning", "desc": "Larger R1 distill, excellent step-by-step math and logic"},
  {"name": "DeepSeek-R1-32B", "file": "DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf", "repo": "bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF", "size_gb": 19.8, "hw": "GPU", "tag": "Reasoning", "desc": "The best open reasoning model under 70B"},
  {"name": "QwQ-32B-Preview", "file": "QwQ-32B-Preview-Q4_K_M.gguf", "repo": "bartowski/QwQ-32B-Preview-GGUF", "size_gb": 19.8, "hw": "GPU", "tag": "Reasoning", "desc": "Qwen's thinking model, exceptional math and science"},
  {"name": "Phi-4", "file": "phi-4-Q4_K_M.gguf", "repo": "bartowski/phi-4-GGUF", "size_gb": 8.5, "hw": "GPU", "tag": "Reasoning", "desc": "Microsoft's Phi-4, strong reasoning in 14B package"},
  {"name": "Aya-23-8B", "file": "aya-23-8B-Q4_K_M.gguf", "repo": "bartowski/aya-23-8B-GGUF", "size_gb": 4.9, "hw": "CPU+GPU", "tag": "Multilingual", "desc": "Cohere's multilingual model, 23 languages"},
  {"name": "Qwen2.5-7B-Instruct", "file": "Qwen2.5-7B-Instruct-Q4_K_M.gguf", "repo": "Qwen/Qwen2.5-7B-Instruct-GGUF", "size_gb": 4.7, "hw": "CPU+GPU", "tag": "Multilingual", "desc": "Strong Chinese/English bilingual, good general chat"},
  {"name": "Qwen2.5-14B-Instruct", "file": "Qwen2.5-14B-Instruct-Q4_K_M.gguf", "repo": "Qwen/Qwen2.5-14B-Instruct-GGUF", "size_gb": 8.9, "hw": "GPU", "tag": "Multilingual", "desc": "Qwen 14B, excellent across Asian and European languages"},
  {"name": "Llama-3.1-8B-Multilingual", "file": "Llama-3.1-8B-Instruct-Q4_K_M.gguf", "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "size_gb": 4.9, "hw": "CPU+GPU", "tag": "Multilingual", "desc": "Meta 8B trained on 8 languages including French, German, Spanish"},
  {"name": "Mistral-Nemo-12B", "file": "Mistral-Nemo-Instruct-2407-Q4_K_M.gguf", "repo": "bartowski/Mistral-Nemo-Instruct-2407-GGUF", "size_gb": 7.1, "hw": "GPU", "tag": "Multilingual", "desc": "Mistral + NVIDIA collab, strong multilingual support"},
  {"name": "Dolphin-2.9-Llama3-8B", "file": "dolphin-2.9-llama3-8b.Q4_K_M.gguf", "repo": "cognitivecomputations/dolphin-2.9-llama3-8b-GGUF", "size_gb": 4.9, "hw": "CPU+GPU", "tag": "Uncensored", "desc": "Dolphin fine-tune, uncensored, good for creative tasks"},
  {"name": "Hermes-3-Llama3.1-8B", "file": "Hermes-3-Llama-3.1-8B.Q4_K_M.gguf", "repo": "NousResearch/Hermes-3-Llama-3.1-8B-GGUF", "size_gb": 4.9, "hw": "CPU+GPU", "tag": "Uncensored", "desc": "Nous Hermes 3, great for roleplay and creative writing"},
  {"name": "Llama-3-Groq-8B-Tool-Use", "file": "Llama-3-Groq-8B-Tool-Use-Q4_K_M.gguf", "repo": "bartowski/Llama-3-Groq-8B-Tool-Use-GGUF", "size_gb": 4.9, "hw": "CPU+GPU", "tag": "Uncensored", "desc": "Groq fine-tune optimized for function calling and tools"},
  {"name": "WizardLM-2-7B", "file": "WizardLM-2-7B.Q4_K_M.gguf", "repo": "bartowski/WizardLM-2-7B-GGUF", "size_gb": 4.2, "hw": "CPU+GPU", "tag": "Uncensored", "desc": "Microsoft WizardLM 2, strong instruction following"},
  {"name": "LLaVA-1.6-Mistral-7B", "file": "llava-v1.6-mistral-7b.Q4_K_M.gguf", "repo": "cjpais/llava-1.6-mistral-7b-gguf", "size_gb": 4.4, "hw": "GPU", "tag": "Vision", "desc": "See and chat about images, Mistral backbone"},
  {"name": "BakLLaVA-1", "file": "BakLLaVA-1-Q4_K_M.gguf", "repo": "SkunkworksAI/BakLLaVA-1-GGUF", "size_gb": 4.1, "hw": "GPU", "tag": "Vision", "desc": "Image understanding with Mistral-7B backbone"},
  {"name": "Mistral-7B-v0.2-32k", "file": "Mistral-7B-Instruct-v0.2.Q4_K_M.gguf", "repo": "TheBloke/Mistral-7B-Instruct-v0.2-GGUF", "size_gb": 4.1, "hw": "CPU+GPU", "tag": "Chat", "desc": "32k context window, great for long documents"},
  {"name": "Llama-3.1-8B-128k", "file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "size_gb": 4.9, "hw": "CPU+GPU", "tag": "Chat", "desc": "128k context, can read entire codebases at once"},
  {"name": "Qwen2.5-72B-Instruct", "file": "Qwen2.5-72B-Instruct-Q4_K_M.gguf", "repo": "Qwen/Qwen2.5-72B-Instruct-GGUF", "size_gb": 43.0, "hw": "GPU", "tag": "Chat", "desc": "Qwen's flagship 72B, one of the best open models"},
  {"name": "Llama-3.1-8B-Instruct-SciTech", "file": "Llama-3.1-8B-Instruct-Q4_K_M.gguf", "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "size_gb": 4.9, "hw": "CPU+GPU", "tag": "Reasoning", "desc": "Great for science, math, and technical Q&A"},
  {"name": "WizardMath-7B-v1.1", "file": "WizardMath-7B-V1.1.Q4_K_M.gguf", "repo": "TheBloke/WizardMath-7B-V1.1-GGUF", "size_gb": 4.1, "hw": "CPU+GPU", "tag": "Reasoning", "desc": "Specialized math reasoning, strong at word problems"},
  {"name": "MetaMath-Mistral-7B", "file": "MetaMath-Mistral-7B-Q4_K_M.gguf", "repo": "TheBloke/MetaMath-Mistral-7B-GGUF", "size_gb": 4.1, "hw": "CPU+GPU", "tag": "Reasoning", "desc": "Math-focused fine-tune on Mistral, great for students"},
  {"name": "Hermes-2-Pro-Mistral-7B", "file": "Hermes-2-Pro-Mistral-7B.Q4_K_M.gguf", "repo": "NousResearch/Hermes-2-Pro-Mistral-7B-GGUF", "size_gb": 4.1, "hw": "CPU+GPU", "tag": "Chat", "desc": "Creative writing and storytelling focused"},
  {"name": "OpenHermes-2.5-Mistral-7B", "file": "OpenHermes-2.5-Mistral-7B.Q4_K_M.gguf", "repo": "TheBloke/OpenHermes-2.5-Mistral-7B-GGUF", "size_gb": 4.1, "hw": "CPU+GPU", "tag": "Chat", "desc": "Very popular Hermes fine-tune, excellent all-rounder"},
  {"name": "Neural-Chat-7B-v3.3", "file": "neural-chat-7b-v3-3.Q4_K_M.gguf", "repo": "TheBloke/neural-chat-7b-v3-3-GGUF", "size_gb": 4.1, "hw": "CPU+GPU", "tag": "Chat", "desc": "Intel's chat model, very human conversational style"},
  {"name": "Phi-3.5-Mini-Instruct", "file": "Phi-3.5-mini-instruct-Q4_K_M.gguf", "repo": "bartowski/Phi-3.5-mini-instruct-GGUF", "size_gb": 2.2, "hw": "CPU", "tag": "Chat", "desc": "Microsoft's updated mini, excellent for CPU-only setups"},
  {"name": "SmolLM2-1.7B-Instruct", "file": "SmolLM2-1.7B-Instruct-Q4_K_M.gguf", "repo": "bartowski/SmolLM2-1.7B-Instruct-GGUF", "size_gb": 1.1, "hw": "CPU", "tag": "Chat", "desc": "HuggingFace's tiny model, runs on anything"},
  {"name": "Qwen2.5-0.5B-Instruct", "file": "Qwen2.5-0.5B-Instruct-Q4_K_M.gguf", "repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF", "size_gb": 0.4, "hw": "CPU", "tag": "Chat", "desc": "Half a gigabyte, still surprisingly capable"},
  {"name": "Qwen2.5-1.5B-Instruct", "file": "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf", "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF", "size_gb": 1.0, "hw": "CPU", "tag": "Chat", "desc": "Great RAM-constrained option from Qwen"},
  {"name": "Llama-2-13B-Chat", "file": "llama-2-13b-chat.Q4_K_M.gguf", "repo": "TheBloke/Llama-2-13B-chat-GGUF", "size_gb": 7.4, "hw": "GPU", "tag": "Chat", "desc": "Meta's original Llama 2 13B chat, reliable and well-tested"},
  {"name": "Mistral-22B-v0.3", "file": "Mistral-22B-v0.3-Q4_K_M.gguf", "repo": "bartowski/Mistral-22B-v0.3-GGUF", "size_gb": 13.5, "hw": "GPU", "tag": "Chat", "desc": "Mistral's 22B, strong upgrade from 7B for GPU users"},
  {"name": "Codestral-22B", "file": "Codestral-22B-v0.1-Q4_K_M.gguf", "repo": "bartowski/Codestral-22B-v0.1-GGUF", "size_gb": 13.5, "hw": "GPU", "tag": "Code", "desc": "Mistral's dedicated 22B code model, production quality"},
  {"name": "Yi-1.5-34B-Chat", "file": "Yi-1.5-34B-Chat-Q4_K_M.gguf", "repo": "bartowski/Yi-1.5-34B-Chat-GGUF", "size_gb": 20.0, "hw": "GPU", "tag": "Chat", "desc": "01.AI's 34B, very strong reasoning and long context"},
  {"name": "Mixtral-8x7B-Instruct", "file": "mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf", "repo": "TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF", "size_gb": 26.4, "hw": "GPU", "tag": "Chat", "desc": "Mistral's MoE model, GPT-3.5 quality at open weights"},
]

HW_COLOR = {"CPU": "#2d7a2d", "GPU": "#1a5fa8", "CPU+GPU": "#6a2d8a"}
TAG_COLOR = {"Chat": "#c45e00", "Code": "#0066cc", "Reasoning": "#aa0000", "Multilingual": "#007755", "Uncensored": "#884400", "Vision": "#550088"}

_active_download = {"file": None, "thread": None, "size_gb": 0.0}
_download_lock = threading.Lock()


def badge(text, color):
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:0.75em;font-weight:bold">{text}</span>'


def model_exists(model_file):
    path = Path("user_data/models") / model_file
    return path.exists() and path.stat().st_size > 50 * 1024 * 1024


def get_download_progress(model_file, expected_gb):
    path = Path("user_data/models") / model_file
    if not path.exists():
        return 0.0
    current = path.stat().st_size
    total = expected_gb * 1024 ** 3
    return min(current / total, 1.0)


def filter_models(search, tag_filter, size_filter, hw_filter):
    results = MODELS
    if search:
        q = search.lower()
        results = [m for m in results if q in m["name"].lower() or q in m["desc"].lower()]
    if tag_filter != "All":
        results = [m for m in results if m["tag"] == tag_filter]
    if hw_filter != "All hardware":
        results = [m for m in results if hw_filter in m["hw"]]
    if size_filter == "Under 2 GB":
        results = [m for m in results if m["size_gb"] < 2]
    elif size_filter == "2–5 GB":
        results = [m for m in results if 2 <= m["size_gb"] < 5]
    elif size_filter == "5–10 GB":
        results = [m for m in results if 5 <= m["size_gb"] < 10]
    elif size_filter == "10+ GB":
        results = [m for m in results if m["size_gb"] >= 10]
    return results


def start_download(index):
    model = MODELS[index]
    model_file = model["file"]
    if model_exists(model_file):
        return f"✅ {model['name']} is already downloaded."

    with _download_lock:
        active_thread = _active_download["thread"]
        if active_thread and active_thread.is_alive():
            if _active_download["file"] == model_file:
                return f"⏳ {model['name']} is already downloading..."
            return f"⚠️ Busy downloading {_active_download['file']}. Please wait."

        models_dir = Path("user_data/models")
        models_dir.mkdir(parents=True, exist_ok=True)
        out_path = models_dir / model_file
        url = f"https://huggingface.co/{model['repo']}/resolve/main/{model_file}?download=true"

        def run_download():
            subprocess.run(["wget", "-q", "-O", str(out_path), url], check=False)

        _active_download["file"] = model_file
        _active_download["size_gb"] = model["size_gb"]
        _active_download["thread"] = threading.Thread(target=run_download, daemon=True)
        _active_download["thread"].start()

    return f"⬇ Started download: {model['name']}"


def card_header(model):
    name = html.escape(model["name"])
    desc = html.escape(model["desc"])
    return (
        f"<div class='model-hub-title'>{name}</div>"
        f"<div class='model-hub-desc'><i>{desc}</i></div>"
        f"<div class='model-hub-badges'>"
        f"{badge(f'💾 {model['size_gb']:.1f} GB', '#555570')}"
        f"{badge(f'⚡ {model['hw']}', HW_COLOR.get(model['hw'], '#666666'))}"
        f"{badge(f'🎯 {model['tag']}', TAG_COLOR.get(model['tag'], '#aa5500'))}"
        f"</div>"
    )


def refresh_cards(search, tag_filter, size_filter, hw_filter):
    with _download_lock:
        if _active_download["thread"] and not _active_download["thread"].is_alive():
            _active_download["thread"] = None
            _active_download["file"] = None
            _active_download["size_gb"] = 0.0

        active_file = _active_download["file"]
        busy = bool(_active_download["thread"] and _active_download["thread"].is_alive())

    filtered_names = {m["name"] for m in filter_models(search, tag_filter, size_filter, hw_filter)}
    updates = []
    for model in MODELS:
        visible = model["name"] in filtered_names
        downloaded = model_exists(model["file"])
        downloading_this = busy and active_file == model["file"]
        progress = get_download_progress(model["file"], model["size_gb"]) if downloading_this else 0.0

        button_value = "⬇ Download"
        button_interactive = True
        if busy and not downloading_this:
            button_value = "⏳ Busy"
            button_interactive = False

        updates.extend([
            gr.update(visible=visible),
            gr.update(visible=visible and not downloaded, value=button_value, interactive=button_interactive),
            gr.update(visible=visible and downloading_this, value=int(progress * 100)),
            gr.update(visible=visible and downloaded),
        ])

    if busy and active_file:
        status = f"⏳ Download in progress: {active_file}"
    else:
        status = "Ready. Select a model and click Download."

    updates.append(status)
    return updates


def ui():
    gr.HTML(
        """
        <style>
        .model-hub-grid { display: grid !important; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
        @media (max-width: 1100px) { .model-hub-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @media (max-width: 760px) { .model-hub-grid { grid-template-columns: repeat(1, minmax(0, 1fr)); } }
        .model-hub-card { background: #1e1e2e; border: 1px solid #333355; border-radius: 12px; padding: 14px; min-height: 190px; color: #ffffff !important; }
        .model-hub-card:hover { box-shadow: 0 0 8px #5555aa; }
        .model-hub-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 6px; color: #ffffff !important; }
        .model-hub-desc { color: #d2d2e8 !important; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 10px; }
        .model-hub-badges { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
        .model-hub-card, .model-hub-card * { color: #ffffff; }
        #model-hub-status, #model-hub-status * { color: #ffffff !important; }
        .download-btn button { background: #4a90d9 !important; width: 100%; }
        .progress-thin .wrap .progress-text { display: none !important; }
        .progress-thin .wrap [role='progressbar'] { min-height: 6px !important; height: 6px !important; }
        </style>
        <script>
        (() => {
            if (window.__modelHubRefreshTimer) return;
            window.__modelHubRefreshTimer = setInterval(() => {
                const btn = document.querySelector('#model-hub-refresh button');
                if (btn) { btn.click(); }
            }, 2000);
        })();
        </script>
        """
    )

    with gr.Row():
        search = gr.Textbox(label="Search", placeholder="Search models by name or description")
        tag_filter = gr.Dropdown(["All", "Chat", "Code", "Reasoning", "Multilingual", "Uncensored"], value="All", label="Category")
        size_filter = gr.Dropdown(["All sizes", "Under 2 GB", "2–5 GB", "5–10 GB", "10+ GB"], value="All sizes", label="Size")
        hw_filter = gr.Dropdown(["All hardware", "CPU", "GPU", "CPU+GPU"], value="All hardware", label="Hardware")
        refresh_btn = gr.Button("🔄 Refresh", variant="secondary", elem_id="model-hub-refresh")

    status = gr.Markdown("Ready. Select a model and click Download.", elem_id="model-hub-status")

    cards = []
    buttons = []
    progress_bars = []
    downloaded_labels = []

    with gr.Group(elem_classes=["model-hub-grid"]):
        for i, model in enumerate(MODELS):
            with gr.Column(elem_classes=["model-hub-card"]) as card:
                gr.HTML(card_header(model))
                btn = gr.Button("⬇ Download", variant="primary", elem_classes=["download-btn"])
                prog = gr.Slider(minimum=0, maximum=100, value=0, step=1, show_label=False, interactive=False, visible=False, elem_classes=["progress-thin"])
                done = gr.Markdown("✅ Downloaded", visible=False)

                btn.click(lambda idx=i: start_download(idx), outputs=[status], show_progress=False)

            cards.append(card)
            buttons.append(btn)
            progress_bars.append(prog)
            downloaded_labels.append(done)

    outputs = []
    for i in range(len(MODELS)):
        outputs.extend([cards[i], buttons[i], progress_bars[i], downloaded_labels[i]])
    outputs.append(status)

    for trigger in [search.input, tag_filter.change, size_filter.change, hw_filter.change, refresh_btn.click]:
        trigger(refresh_cards, inputs=[search, tag_filter, size_filter, hw_filter], outputs=outputs, show_progress=False)

