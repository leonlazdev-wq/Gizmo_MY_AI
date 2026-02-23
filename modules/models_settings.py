import functools
import json
import re
import subprocess
from math import floor
from pathlib import Path

import gradio as gr
import yaml

from modules import chat, loaders, metadata_gguf, shared, ui
from modules.logging_colors import logger
from modules.utils import resolve_model_path


def get_fallback_settings():
    return {
        'bf16': False,
        'ctx_size': 8192,
        'rope_freq_base': 0,
        'compress_pos_emb': 1,
        'alpha_value': 1,
        'truncation_length': shared.settings['truncation_length'],
        'truncation_length_info': shared.settings['truncation_length'],
        'skip_special_tokens': shared.settings['skip_special_tokens'],
    }


def get_model_metadata(model):
    model_path = resolve_model_path(model)
    model_settings = {}

    settings = shared.model_config
    for pat in settings:
        if re.match(pat.lower(), Path(model).name.lower()):
            for k in settings[pat]:
                model_settings[k] = settings[pat][k]

    path = model_path / 'config.json'
    if path.exists():
        hf_metadata = json.loads(open(path, 'r', encoding='utf-8').read())
    else:
        hf_metadata = None

    if 'loader' not in model_settings:
        quant_method = None if hf_metadata is None else hf_metadata.get("quantization_config", {}).get("quant_method", None)
        model_settings['loader'] = infer_loader(
            model,
            model_settings,
            hf_quant_method=quant_method
        )

    # GGUF metadata
    if model_settings['loader'] == 'llama.cpp':
        path = model_path
        if path.is_file():
            model_file = path
        else:
            gguf_files = list(path.glob('*.gguf'))
            if not gguf_files:
                logger.warning(f"No .gguf models found in directory: {path}")
                return model_settings

            model_file = gguf_files[0]

        # ── FIX: load_gguf_metadata_with_cache can return None if file is missing ──
        metadata = load_gguf_metadata_with_cache(model_file)
        if not metadata:
            logger.warning(f"Could not read metadata from {model_file.name} — using defaults.")
            return model_settings

        for k in metadata:
            if k.endswith('.context_length'):
                model_settings['ctx_size'] = min(metadata[k], 8192)
                model_settings['truncation_length_info'] = metadata[k]
            elif k.endswith('rope.freq_base'):
                model_settings['rope_freq_base'] = metadata[k]
            elif k.endswith('rope.scale_linear'):
                model_settings['compress_pos_emb'] = metadata[k]
            elif k.endswith('rope.scaling.factor'):
                model_settings['compress_pos_emb'] = metadata[k]
            elif k.endswith('.block_count'):
                model_settings['gpu_layers'] = metadata[k] + 1
                model_settings['max_gpu_layers'] = metadata[k] + 1

        if 'tokenizer.chat_template' in metadata:
            template = metadata['tokenizer.chat_template']
            if 'tokenizer.ggml.eos_token_id' in metadata:
                eos_token = metadata['tokenizer.ggml.tokens'][metadata['tokenizer.ggml.eos_token_id']]
            else:
                eos_token = ""

            if 'tokenizer.ggml.bos_token_id' in metadata:
                bos_token = metadata['tokenizer.ggml.tokens'][metadata['tokenizer.ggml.bos_token_id']]
            else:
                bos_token = ""

            shared.bos_token = bos_token
            shared.eos_token = eos_token

            template = re.sub(r"\{\{-?\s*raise_exception\(.*?\)\s*-?\}\}", "", template, flags=re.DOTALL)
            template = re.sub(r'raise_exception\([^)]*\)', "''", template)
            model_settings['instruction_template'] = 'Custom (obtained from model metadata)'
            model_settings['instruction_template_str'] = template

    else:
        # Transformers metadata
        if hf_metadata is not None:
            metadata = json.loads(open(path, 'r', encoding='utf-8').read())
            if 'pretrained_config' in metadata:
                metadata = metadata['pretrained_config']

            for k in ['max_position_embeddings', 'model_max_length', 'max_seq_len']:
                if k in metadata:
                    value = metadata[k]
                elif k in metadata.get('text_config', {}):
                    value = metadata['text_config'][k]
                else:
                    continue

                model_settings['truncation_length'] = value
                model_settings['truncation_length_info'] = value
                model_settings['ctx_size'] = min(value, 8192)
                break

            if 'rope_theta' in metadata:
                model_settings['rope_freq_base'] = metadata['rope_theta']
            elif 'attn_config' in metadata and 'rope_theta' in metadata['attn_config']:
                model_settings['rope_freq_base'] = metadata['attn_config']['rope_theta']

            if 'rope_scaling' in metadata and isinstance(metadata['rope_scaling'], dict) and all(key in metadata['rope_scaling'] for key in ('type', 'factor')):
                if metadata['rope_scaling']['type'] == 'linear':
                    model_settings['compress_pos_emb'] = metadata['rope_scaling']['factor']

            if 'torch_dtype' in metadata and metadata['torch_dtype'] == 'bfloat16':
                model_settings['bf16'] = True

    # Try to find the Jinja instruct template
    path = model_path / 'tokenizer_config.json'
    template = None

    jinja_path = model_path / 'chat_template.jinja'
    if jinja_path.exists():
        with open(jinja_path, 'r', encoding='utf-8') as f:
            template = f.read()

    if template is None:
        json_template_path = model_path / 'chat_template.json'
        if json_template_path.exists():
            with open(json_template_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                if 'chat_template' in json_data:
                    template = json_data['chat_template']

    if path.exists():
        metadata = json.loads(open(path, 'r', encoding='utf-8').read())

        if template is None and 'chat_template' in metadata:
            template = metadata['chat_template']
            if isinstance(template, list):
                template = template[0]['template']

        if template:
            shared.bos_token = '<s>'
            shared.eos_token = '</s>'

            for k in ['eos_token', 'bos_token']:
                if k in metadata:
                    value = metadata[k]
                    if isinstance(value, dict):
                        value = value['content']

                    setattr(shared, k, value)

            template = re.sub(r"\{\{-?\s*raise_exception\(.*?\)\s*-?\}\}", "", template, flags=re.DOTALL)
            template = re.sub(r'raise_exception\([^)]*\)', "''", template)
            model_settings['instruction_template'] = 'Custom (obtained from model metadata)'
            model_settings['instruction_template_str'] = template

    if 'instruction_template' not in model_settings:
        model_settings['instruction_template'] = 'Alpaca'

    if 'rope_freq_base' in model_settings and model_settings['rope_freq_base'] == 10000:
        model_settings.pop('rope_freq_base')

    settings = shared.user_config
    for pat in settings:
        if re.match(pat.lower(), Path(model).name.lower()):
            for k in settings[pat]:
                new_k = k
                if k == 'n_gpu_layers':
                    new_k = 'gpu_layers'

                model_settings[new_k] = settings[pat][k]

    if model_settings['instruction_template'] != 'Custom (obtained from model metadata)':
        model_settings['instruction_template_str'] = chat.load_instruction_template(model_settings['instruction_template'])

    return model_settings


def infer_loader(model_name, model_settings, hf_quant_method=None):
    path_to_model = resolve_model_path(model_name)
    if not path_to_model.exists():
        loader = None
    elif shared.args.portable:
        loader = 'llama.cpp'
    elif len(list(path_to_model.glob('*.gguf'))) > 0:
        loader = 'llama.cpp'
    elif re.match(r'.*\.gguf', model_name.lower()):
        loader = 'llama.cpp'
    elif hf_quant_method == 'exl3':
        loader = 'ExLlamav3'
    elif hf_quant_method in ['exl2', 'gptq']:
        loader = 'ExLlamav2_HF'
    elif re.match(r'.*exl3', model_name.lower()):
        loader = 'ExLlamav3'
    elif re.match(r'.*exl2', model_name.lower()):
        loader = 'ExLlamav2_HF'
    else:
        loader = 'Transformers'

    return loader


def update_model_parameters(state, initial=False):
    elements = ui.list_model_elements()

    for i, element in enumerate(elements):
        if element not in state:
            continue

        value = state[element]
        if initial and element in shared.provided_arguments:
            continue

        if element == 'cpu_memory' and value == 0:
            value = vars(shared.args_defaults)[element]

        setattr(shared.args, element, value)


def apply_model_settings_to_state(model, state):
    model_settings = get_model_metadata(model)
    if 'loader' in model_settings:
        loader = model_settings.pop('loader')
        if not ((loader == 'ExLlamav2_HF' and state['loader'] == 'ExLlamav2') or (loader == 'ExLlamav3_HF' and state['loader'] == 'ExLlamav3')):
            state['loader'] = loader

    for k in model_settings:
        if k in state and k != 'gpu_layers':
            state[k] = model_settings[k]

    if state['loader'] == 'llama.cpp' and 'gpu_layers' in model_settings:
        vram_info, gpu_layers_update = update_gpu_layers_and_vram(
            state['loader'],
            model,
            model_settings['gpu_layers'],
            state['ctx_size'],
            state['cache_type'],
            auto_adjust=True
        )

        state['gpu_layers'] = gpu_layers_update
        state['vram_info'] = vram_info

    return state


def save_model_settings(model, state):
    if model == 'None':
        yield ("Not saving the settings because no model is selected in the menu.")
        return

    user_config = shared.load_user_config()
    model_regex = Path(model).name + '$'
    if model_regex not in user_config:
        user_config[model_regex] = {}

    for k in ui.list_model_elements():
        if k == 'loader' or k in loaders.loaders_and_params[state['loader']]:
            user_config[model_regex][k] = state[k]

    shared.user_config = user_config

    output = yaml.dump(user_config, sort_keys=False)
    p = Path(f'{shared.args.model_dir}/config-user.yaml')
    with open(p, 'w') as f:
        f.write(output)

    yield (f"Settings for `{model}` saved to `{p}`.")


def save_instruction_template(model, template):
    if model == 'None':
        yield ("Not saving the template because no model is selected in the menu.")
        return

    user_config = shared.load_user_config()
    model_regex = Path(model).name + '$'
    if model_regex not in user_config:
        user_config[model_regex] = {}

    if template == 'None':
        user_config[model_regex].pop('instruction_template', None)
    else:
        user_config[model_regex]['instruction_template'] = template

    shared.user_config = user_config

    output = yaml.dump(user_config, sort_keys=False)
    p = Path(f'{shared.args.model_dir}/config-user.yaml')
    with open(p, 'w') as f:
        f.write(output)

    if template == 'None':
        yield (f"Instruction template for `{model}` unset in `{p}`.")
    else:
        yield (f"Instruction template for `{model}` saved to `{p}` as `{template}`.")


@functools.lru_cache(maxsize=1)
def load_gguf_metadata_with_cache(model_file):
    """
    Load GGUF metadata with caching and full validation.
    Returns empty dict (not None) if file is missing/corrupt so callers don't crash.
    """
    model_file = Path(model_file) if not isinstance(model_file, Path) else model_file

    # File must exist
    if not model_file.exists():
        logger.warning(f"Model file not found: {model_file}")
        return {}

    # File must be large enough to be a real GGUF
    try:
        file_size = model_file.stat().st_size
    except Exception as e:
        logger.error(f"Cannot read file size for {model_file.name}: {e}")
        return {}

    MIN_VALID_SIZE = 1024  # 1 KB

    if file_size < MIN_VALID_SIZE:
        logger.warning(f"Model file too small ({file_size} bytes): {model_file.name} — skipping.")
        try:
            model_file.unlink()
            logger.info(f"Deleted corrupt file: {model_file.name}")
        except Exception as e:
            logger.error(f"Could not delete corrupt file: {e}")
        return {}

    # Delegate to metadata_gguf parser
    result = metadata_gguf.load_metadata(model_file)
    return result if result else {}


def get_model_size_mb(model_file: Path) -> float:
    filename = model_file.name

    match = re.match(r'(.+)-\d+-of-\d+\.gguf$', filename)

    if match:
        base_pattern = match.group(1)
        part_files = sorted(model_file.parent.glob(f'{base_pattern}-*-of-*.gguf'))
        total_size = sum(p.stat().st_size for p in part_files)
    else:
        total_size = model_file.stat().st_size

    return total_size / (1024 ** 2)


def estimate_vram(gguf_file, gpu_layers, ctx_size, cache_type):
    model_file = resolve_model_path(gguf_file)
        if not model_file.exists() or not model_file.is_file():
        raise FileNotFoundError(f"GGUF model file not found: {model_file}")

    try:
        model_file = resolve_model_path(gguf_file)

        # ── FIX: guard against missing file ───────────────────────────────────
        if not model_file.exists():
            logger.warning(f"estimate_vram: model file not found: {model_file}")
            return 0

        metadata = load_gguf_metadata_with_cache(model_file)

        # ── FIX: guard against empty/None metadata ─────────────────────────────
        if not metadata:
            logger.warning(f"estimate_vram: no metadata for {model_file.name} — returning 0")
            return 0

        size_in_mb = get_model_size_mb(model_file)

        n_layers = None
        n_kv_heads = None
        n_attention_heads = None
        embedding_dim = None

        for key, value in metadata.items():
            if key.endswith('.block_count'):
                n_layers = value
            elif key.endswith('.attention.head_count_kv'):
                n_kv_heads = max(value) if isinstance(value, list) else value
            elif key.endswith('.attention.head_count'):
                n_attention_heads = max(value) if isinstance(value, list) else value
            elif key.endswith('.embedding_length'):
                embedding_dim = value

        # ── FIX: guard against None values from metadata ───────────────────────
        if n_layers is None or embedding_dim is None:
            logger.warning("estimate_vram: incomplete metadata — returning 0")
            return 0

        if n_kv_heads is None:
            n_kv_heads = n_attention_heads or 1

        if gpu_layers > n_layers:
            gpu_layers = n_layers

        if cache_type == 'q4_0':
            cache_type_num = 4
        elif cache_type == 'q8_0':
            cache_type_num = 8
        else:
            cache_type_num = 16

        size_per_layer = size_in_mb / max(n_layers, 1e-6)
        kv_cache_factor = n_kv_heads * cache_type_num * ctx_size
        embedding_per_context = embedding_dim / max(ctx_size, 1)

        vram = (
            (size_per_layer - 17.99552795246051 + 3.148552680382576e-05 * kv_cache_factor)
            * (gpu_layers + max(0.9690636483914102, cache_type_num - (floor(50.77817218646521 * embedding_per_context) + 9.987899908205632)))
            + 1516.522943869404
        )

        return max(vram, 0)

    except Exception as e:
        logger.warning(f"estimate_vram: unexpected error — {e}")
        return 0


def get_nvidia_vram(return_free=True):
    try:
        result = subprocess.run(
            ['nvidia-smi'],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            return -1

        output = result.stdout
        matches = re.findall(r"(\d+)\s*MiB\s*/\s*(\d+)\s*MiB", output)

        if not matches:
            return 0

        total_vram_mib = 0
        total_free_vram_mib = 0

        for used_mem_str, total_mem_str in matches:
            try:
                used_mib = int(used_mem_str)
                total_mib = int(total_mem_str)
                total_vram_mib += total_mib
                total_free_vram_mib += (total_mib - used_mib)
            except ValueError:
                pass

        return total_free_vram_mib if return_free else total_vram_mib

    except FileNotFoundError:
        return -1
    except Exception:
        return -1


def update_gpu_layers_and_vram(loader, model, gpu_layers, ctx_size, cache_type, auto_adjust=False, for_ui=True):
    """
    Unified function to handle GPU layers and VRAM updates.
    Safe — will never crash even if model file is missing.
    """
    BLANK_VRAM = "<div id=\"vram-info\">Estimated VRAM to load the model:</div>"

    # ── FIX: early-out if model is not a valid GGUF ────────────────────────────
    if loader != 'llama.cpp' or model in ["None", None] or not model.endswith(".gguf"):
        if for_ui:
            return (BLANK_VRAM, gr.update()) if auto_adjust else BLANK_VRAM
        else:
            return (0, gpu_layers) if auto_adjust else 0

    model_path = resolve_model_path(model)
    if not model_path.exists() or not model_path.is_file():
        logger.error(f"GGUF model file was not found: {model_path}")
        vram_info = (
            f"<div id=\"vram-info\"'>Model file not found: "
            f"<span class=\"value\">{model_path}</span></div>"
        )
        if for_ui:
            return (vram_info, gr.update()) if auto_adjust else vram_info
        else:
            return (0, gpu_layers) if auto_adjust else 0

    # ── FIX: check file exists before doing anything ───────────────────────────
    try:
        model_file = resolve_model_path(model)
        if not model_file.exists():
            logger.warning(f"update_gpu_layers_and_vram: model not found: {model}")
            if for_ui:
                return (BLANK_VRAM, gr.update()) if auto_adjust else BLANK_VRAM
            else:
                return (0, gpu_layers) if auto_adjust else 0
    except Exception:
        if for_ui:
            return (BLANK_VRAM, gr.update()) if auto_adjust else BLANK_VRAM
        else:
            return (0, gpu_layers) if auto_adjust else 0

    try:
        model_settings = get_model_metadata(model)
    except Exception as e:
        logger.warning(f"update_gpu_layers_and_vram: get_model_metadata failed: {e}")
        if for_ui:
            return (BLANK_VRAM, gr.update()) if auto_adjust else BLANK_VRAM
        else:
            return (0, gpu_layers) if auto_adjust else 0

    current_layers = gpu_layers
    max_layers = model_settings.get('max_gpu_layers', 256)

    if auto_adjust:
        user_config = shared.user_config
        model_regex = Path(model).name + '$'
        has_user_setting = model_regex in user_config and 'gpu_layers' in user_config[model_regex]

        if not has_user_setting:
            current_layers = max_layers

            return_free = False if (for_ui and shared.model_name not in [None, 'None']) else True
            available_vram = get_nvidia_vram(return_free=return_free)
            if available_vram > 0:
                tolerance = 577
                while current_layers > 0 and estimate_vram(model, current_layers, ctx_size, cache_type) > available_vram - tolerance:
                    current_layers -= 1

    vram_usage = estimate_vram(model, current_layers, ctx_size, cache_type)

    if for_ui:
        vram_info = f"<div id=\"vram-info\">Estimated VRAM to load the model: <span class=\"value\">{vram_usage:.0f} MiB</span></div>"
        if auto_adjust:
            return vram_info, gr.update(value=current_layers, maximum=max_layers)
        else:
            return vram_info
    else:
        if auto_adjust:
            return vram_usage, current_layers
        else:
            return vram_usage
