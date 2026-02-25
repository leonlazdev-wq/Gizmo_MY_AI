MODEL_CATALOG = [
    {
        "id": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "file": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "name": "Qwen 2.5 Coder 7B",
        "size_gb": 4.5,
        "use_cases": ["coding", "programming", "debugging", "code review"],
        "description": "Excellent for coding tasks — code generation, debugging, explaining code, and code review.",
        "min_ram_gb": 6,
        "quality": "high",
        "speed": "fast",
        "languages": ["en", "multi"],
    },
    {
        "id": "meta-llama/Llama-3.1-8B-Instruct-GGUF",
        "file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "name": "Llama 3.1 8B",
        "size_gb": 4.9,
        "use_cases": ["chat", "general", "creative_writing", "brainstorming"],
        "description": "Great all-rounder for general chat, creative writing, and brainstorming.",
        "min_ram_gb": 6,
        "quality": "high",
        "speed": "fast",
        "languages": ["en", "multi"],
    },
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3-GGUF",
        "file": "mistral-7b-instruct-v0.3.Q4_K_M.gguf",
        "name": "Mistral 7B",
        "size_gb": 4.4,
        "use_cases": ["research", "analysis", "summarization", "academic"],
        "description": "Strong for research, analysis, and academic writing. Good reasoning skills.",
        "min_ram_gb": 6,
        "quality": "high",
        "speed": "fast",
        "languages": ["en", "fr", "multi"],
    },
    {
        "id": "TheBloke/Llama-2-13B-chat-GGUF",
        "file": "llama-2-13b-chat.Q4_K_M.gguf",
        "name": "Llama 2 13B",
        "size_gb": 8.5,
        "use_cases": ["chat", "tutoring", "education", "explanation"],
        "description": "Larger model with better quality — great for tutoring and detailed explanations.",
        "min_ram_gb": 12,
        "quality": "very_high",
        "speed": "medium",
        "languages": ["en"],
    },
    {
        "id": "Qwen/Qwen2.5-14B-Instruct-GGUF",
        "file": "qwen2.5-14b-instruct-q4_k_m.gguf",
        "name": "Qwen 2.5 14B",
        "size_gb": 9.0,
        "use_cases": ["coding", "research", "general", "multilingual"],
        "description": "Powerful multilingual model — excellent for coding AND general tasks.",
        "min_ram_gb": 12,
        "quality": "very_high",
        "speed": "medium",
        "languages": ["en", "zh", "multi"],
    },
]

USE_CASE_LABELS = {
    "coding": "💻 Coding & Programming",
    "chat": "💬 General Chat & Conversation",
    "research": "🔬 Research & Academic Work",
    "creative_writing": "✍️ Creative Writing & Stories",
    "education": "📚 Tutoring & Education",
    "multilingual": "🌍 Multilingual (multiple languages)",
    "summarization": "📝 Summarizing & Note-Taking",
}


def recommend_models(use_cases: list, available_ram_gb: float = None) -> list:
    """Recommend models based on desired use cases and available resources"""
    scored = []
    for model in MODEL_CATALOG:
        score = sum(1 for uc in use_cases if uc in model["use_cases"])
        if available_ram_gb and model["min_ram_gb"] > available_ram_gb:
            continue
        if score > 0:
            scored.append((score, model))
    scored.sort(key=lambda x: (-x[0], x[1]["size_gb"]))
    return [m for _, m in scored]


def get_system_resources() -> dict:
    """Detect available RAM/VRAM for recommendations"""
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        ram_gb = None

    gpu_info = "Unknown"
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            gpu_info = f"{int(result.stdout.strip()) / 1024:.1f} GB VRAM"
    except Exception:
        pass

    return {"ram_gb": ram_gb, "gpu_info": gpu_info}
