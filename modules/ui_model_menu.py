import importlib
import math
import queue
import threading
import traceback
from functools import partial
from pathlib import Path

import gradio as gr

from modules import loaders, shared, ui, utils
from modules.logging_colors import logger
from modules.LoRA import add_lora_to_model
from modules.model_hub import ModelHub
from modules.model_metrics import METRICS
from modules.models import load_model, unload_model
from modules.models_settings import (
    apply_model_settings_to_state,
    get_model_metadata,
    save_instruction_template,
    save_model_settings,
    update_gpu_layers_and_vram,
    update_model_parameters
)
from modules.utils import gradio


MODEL_HUB = ModelHub()


def refresh_metrics_dashboard():
    return METRICS.generate_dashboard_html()


def search_hub_models(query, size_filter, quant_filter):
    models = MODEL_HUB.search_models(query, {"size": size_filter, "quantization": quant_filter})
    return MODEL_HUB.format_model_results(models)


def get_model_info_html(model_id: str) -> str:
    """Return an HTML snippet showing model use cases."""
    clean = (model_id or "").strip()
    if not clean:
        return "<p style='color:#888'>Enter a model ID above to see use cases.</p>"
    info = MODEL_HUB.get_model_use_cases(clean)
    use_cases = info.get("use_cases", [])
    source = info.get("source", "")
    badges = "".join(
        f"<span style='background:#2a2a2a;border:1px solid #444;border-radius:12px;"
        f"padding:3px 10px;font-size:.82em;margin:2px;display:inline-block'>{uc}</span>"
        for uc in use_cases
    )
    source_note = f"<span style='font-size:.75em;color:#666'>(source: {source})</span>" if source else ""
    return (
        f"<div style='margin:6px 0'>"
        f"<b style='font-size:.88em;color:#aaa'>Use cases for <code>{clean}</code>:</b> {source_note}<br>"
        f"<div style='margin-top:4px'>{badges}</div>"
        f"</div>"
    )


def create_ui():
    mu = shared.args.multi_user

    with gr.Tab("Model", elem_id="model-tab"):
        with gr.Row():
            with gr.Column():
                with gr.Row():
                    shared.gradio['model_menu'] = gr.Dropdown(choices=utils.get_available_models(), value=lambda: shared.model_name, label='Model', elem_classes='slim-dropdown', interactive=not mu)
                    ui.create_refresh_button(shared.gradio['model_menu'], lambda: None, lambda: {'choices': utils.get_available_models()}, 'refresh-button', interactive=not mu)
                    shared.gradio['load_model'] = gr.Button("Load", elem_classes='refresh-button', interactive=not mu)
                    shared.gradio['unload_model'] = gr.Button("Unload", elem_classes='refresh-button', interactive=not mu)
                    shared.gradio['save_model_settings'] = gr.Button("Save settings", elem_classes='refresh-button', interactive=not mu)

                shared.gradio['loader'] = gr.Dropdown(label="Model loader", choices=loaders.loaders_and_params.keys() if not shared.args.portable else ['llama.cpp'], value=None)
                with gr.Accordion('⚡ Performance Dashboard', open=False):
                    shared.gradio['metrics_status'] = gr.Textbox(label='Metrics monitor', value='Idle', interactive=False)
                    with gr.Row():
                        shared.gradio['metrics_start_btn'] = gr.Button('▶️ Start metrics')
                        shared.gradio['metrics_stop_btn'] = gr.Button('⏹️ Stop metrics')
                        shared.gradio['metrics_refresh_btn'] = gr.Button('🔄 Refresh now', elem_id='metrics-refresh-btn')
                    shared.gradio['metrics_display'] = gr.HTML(value=refresh_metrics_dashboard())
                    if hasattr(gr, 'Timer'):
                        shared.gradio['metrics_timer'] = gr.Timer(value=2.0)
                    else:
                        shared.gradio['metrics_timer'] = None
                        gr.HTML("""
                        <script>
                        (() => {
                          if (window.__metricsRefreshInterval) return;
                          window.__metricsRefreshInterval = setInterval(() => {
                            const btn = document.querySelector('#metrics-refresh-btn button');
                            if (btn) btn.click();
                          }, 2000);
                        })();
                        </script>
                        """)

                with gr.Accordion('🌐 Model Hub', open=False):
                    shared.gradio['hub_query'] = gr.Textbox(label='Search Models', placeholder='llama, mistral, phi...')
                    with gr.Row():
                        shared.gradio['hub_size_filter'] = gr.Radio(choices=['All sizes', 'Small (<5GB)', 'Medium (5-20GB)', 'Large (>20GB)'], value='All sizes', label='Size')
                        shared.gradio['hub_quant_filter'] = gr.CheckboxGroup(choices=['GGUF', 'GPTQ', 'AWQ', 'EXL2'], label='Quantization')
                    shared.gradio['hub_search_btn'] = gr.Button('🔍 Search Hub', variant='primary')
                    shared.gradio['hub_results'] = gr.HTML(value='<p>Search Hugging Face models.</p>')
                    with gr.Row():
                        shared.gradio['hub_download_model_id'] = gr.Textbox(label='Model ID to download', placeholder='org/model', scale=4)
                        shared.gradio['hub_more_info_btn'] = gr.Button('ℹ️ More Info', size='sm', scale=1)
                    shared.gradio['hub_model_info'] = gr.HTML(value='')
                    shared.gradio['hub_download_btn'] = gr.Button('⬇️ Download model')
                    shared.gradio['hub_status'] = gr.Textbox(label='Hub status', interactive=False)

                with gr.Blocks():
                    gr.Markdown("## Main options")
                    with gr.Row():
                        with gr.Column():
                            shared.gradio['gpu_layers'] = gr.Slider(label="gpu-layers", minimum=0, maximum=get_initial_gpu_layers_max(), step=1, value=shared.args.gpu_layers, info='Must be greater than 0 for the GPU to be used. ⚠️ Lower this value if you can\'t load the model.')
                            shared.gradio['ctx_size'] = gr.Slider(label='ctx-size', minimum=256, maximum=131072, step=256, value=shared.args.ctx_size, info='Context length.')
                            shared.gradio['gpu_split'] = gr.Textbox(label='gpu-split', info='Comma-separated list of VRAM (in GB) to use per GPU. Example: 20,7,7')
                            shared.gradio['attn_implementation'] = gr.Dropdown(label="attn-implementation", choices=['sdpa', 'eager', 'flash_attention_2'], value=shared.args.attn_implementation, info='Attention implementation.')
                            shared.gradio['cache_type'] = gr.Dropdown(label="cache-type", choices=['fp16', 'q8_0', 'q4_0', 'fp8', 'q8', 'q7', 'q6', 'q5', 'q4', 'q3', 'q2'], value=shared.args.cache_type, allow_custom_value=True, info='KV cache type.')
                            shared.gradio['tp_backend'] = gr.Dropdown(label="tp-backend", choices=['native', 'nccl'], value=shared.args.tp_backend, info='The backend for tensor parallelism.')

                        with gr.Column():
                            shared.gradio['vram_info'] = gr.HTML(value=get_initial_vram_info())
                            shared.gradio['cpu_moe'] = gr.Checkbox(label="cpu-moe", value=shared.args.cpu_moe, info='Move the experts to the CPU. Saves VRAM on MoE models.')
                            shared.gradio['streaming_llm'] = gr.Checkbox(label="streaming-llm", value=shared.args.streaming_llm, info='Activate StreamingLLM.')
                            shared.gradio['load_in_8bit'] = gr.Checkbox(label="load-in-8bit", value=shared.args.load_in_8bit)
                            shared.gradio['load_in_4bit'] = gr.Checkbox(label="load-in-4bit", value=shared.args.load_in_4bit)
                            shared.gradio['use_double_quant'] = gr.Checkbox(label="use_double_quant", value=shared.args.use_double_quant)
                            shared.gradio['autosplit'] = gr.Checkbox(label="autosplit", value=shared.args.autosplit)
                            shared.gradio['enable_tp'] = gr.Checkbox(label="enable_tp", value=shared.args.enable_tp)
                            shared.gradio['cpp_runner'] = gr.Checkbox(label="cpp-runner", value=shared.args.cpp_runner)
                            shared.gradio['tensorrt_llm_info'] = gr.Markdown('* TensorRT-LLM requires a separate install.')

                            with gr.Accordion("Multimodal (vision)", open=False, elem_classes='tgw-accordion') as shared.gradio['mmproj_accordion']:
                                with gr.Row():
                                    shared.gradio['mmproj'] = gr.Dropdown(label="mmproj file", choices=utils.get_available_mmproj(), value=lambda: shared.args.mmproj or 'None', elem_classes='slim-dropdown', info='Must be placed in user_data/mmproj/', interactive=not mu)
                                    ui.create_refresh_button(shared.gradio['mmproj'], lambda: None, lambda: {'choices': utils.get_available_mmproj()}, 'refresh-button', interactive=not mu)

                            with gr.Accordion("Speculative decoding", open=False, elem_classes='tgw-accordion') as shared.gradio['speculative_decoding_accordion']:
                                with gr.Row():
                                    shared.gradio['model_draft'] = gr.Dropdown(label="model-draft", choices=['None'] + utils.get_available_models(), value=lambda: shared.args.model_draft, elem_classes='slim-dropdown', interactive=not mu)
                                    ui.create_refresh_button(shared.gradio['model_draft'], lambda: None, lambda: {'choices': ['None'] + utils.get_available_models()}, 'refresh-button', interactive=not mu)

                                shared.gradio['gpu_layers_draft'] = gr.Slider(label="gpu-layers-draft", minimum=0, maximum=256, value=shared.args.gpu_layers_draft)
                                shared.gradio['draft_max'] = gr.Number(label="draft-max", precision=0, step=1, value=shared.args.draft_max)
                                shared.gradio['device_draft'] = gr.Textbox(label="device-draft", value=shared.args.device_draft)
                                shared.gradio['ctx_size_draft'] = gr.Number(label="ctx-size-draft", precision=0, step=256, value=shared.args.ctx_size_draft)

                    gr.Markdown("## Other options")
                    with gr.Accordion("See more options", open=False, elem_classes='tgw-accordion'):
                        with gr.Row():
                            with gr.Column():
                                shared.gradio['threads'] = gr.Slider(label="threads", minimum=0, step=1, maximum=256, value=shared.args.threads)
                                shared.gradio['threads_batch'] = gr.Slider(label="threads_batch", minimum=0, step=1, maximum=256, value=shared.args.threads_batch)
                                shared.gradio['batch_size'] = gr.Slider(label="batch_size", minimum=1, maximum=4096, step=1, value=shared.args.batch_size)
                                shared.gradio['ubatch_size'] = gr.Slider(label="ubatch_size", minimum=1, maximum=4096, step=1, value=shared.args.ubatch_size)
                                shared.gradio['tensor_split'] = gr.Textbox(label='tensor_split')
                                shared.gradio['extra_flags'] = gr.Textbox(label='extra-flags', value=shared.args.extra_flags)
                                shared.gradio['cpu_memory'] = gr.Number(label="Maximum CPU memory in GiB.", value=shared.args.cpu_memory)
                                shared.gradio['alpha_value'] = gr.Number(label='alpha_value', value=shared.args.alpha_value, precision=2)
                                shared.gradio['rope_freq_base'] = gr.Number(label='rope_freq_base', value=shared.args.rope_freq_base, precision=0)
                                shared.gradio['compress_pos_emb'] = gr.Number(label='compress_pos_emb', value=shared.args.compress_pos_emb, precision=2)
                                shared.gradio['compute_dtype'] = gr.Dropdown(label="compute_dtype", choices=["bfloat16", "float16", "float32"], value=shared.args.compute_dtype)
                                shared.gradio['quant_type'] = gr.Dropdown(label="quant_type", choices=["nf4", "fp4"], value=shared.args.quant_type)
                                shared.gradio['num_experts_per_token'] = gr.Number(label="Number of experts per token", value=shared.args.num_experts_per_token)

                            with gr.Column():
                                shared.gradio['cpu'] = gr.Checkbox(label="cpu", value=shared.args.cpu)
                                shared.gradio['disk'] = gr.Checkbox(label="disk", value=shared.args.disk)
                                shared.gradio['row_split'] = gr.Checkbox(label="row_split", value=shared.args.row_split)
                                shared.gradio['no_kv_offload'] = gr.Checkbox(label="no_kv_offload", value=shared.args.no_kv_offload)
                                shared.gradio['no_mmap'] = gr.Checkbox(label="no-mmap", value=shared.args.no_mmap)
                                shared.gradio['mlock'] = gr.Checkbox(label="mlock", value=shared.args.mlock)
                                shared.gradio['numa'] = gr.Checkbox(label="numa", value=shared.args.numa)
                                shared.gradio['bf16'] = gr.Checkbox(label="bf16", value=shared.args.bf16)
                                shared.gradio['no_flash_attn'] = gr.Checkbox(label="no_flash_attn", value=shared.args.no_flash_attn)
                                shared.gradio['no_xformers'] = gr.Checkbox(label="no_xformers", value=shared.args.no_xformers)
                                shared.gradio['no_sdpa'] = gr.Checkbox(label="no_sdpa", value=shared.args.no_sdpa)
                                shared.gradio['cfg_cache'] = gr.Checkbox(label="cfg-cache", value=shared.args.cfg_cache)
                                shared.gradio['no_use_fast'] = gr.Checkbox(label="no_use_fast", value=shared.args.no_use_fast)
                                if not shared.args.portable:
                                    with gr.Row():
                                        shared.gradio['lora_menu'] = gr.Dropdown(multiselect=True, choices=utils.get_available_loras(), value=shared.lora_names, label='LoRA(s)', elem_classes='slim-dropdown', interactive=not mu)
                                        ui.create_refresh_button(shared.gradio['lora_menu'], lambda: None, lambda: {'choices': utils.get_available_loras(), 'value': shared.lora_names}, 'refresh-button', interactive=not mu)
                                        shared.gradio['lora_menu_apply'] = gr.Button(value='Apply LoRAs', elem_classes='refresh-button', interactive=not mu)

            with gr.Column():
                with gr.Tab("Download"):
                    shared.gradio['custom_model_menu'] = gr.Textbox(label="Download model or LoRA", info="Enter the Hugging Face username/model path, for instance: facebook/galactica-125m.", interactive=not mu)
                    shared.gradio['download_specific_file'] = gr.Textbox(placeholder="File name (for GGUF models)", show_label=False, max_lines=1, interactive=not mu)
                    with gr.Row():
                        shared.gradio['download_model_button'] = gr.Button("Download", variant='primary', interactive=not mu)
                        shared.gradio['get_file_list'] = gr.Button("Get file list", interactive=not mu)

                with gr.Tab("Customize instruction template"):
                    with gr.Row():
                        shared.gradio['customized_template'] = gr.Dropdown(choices=utils.get_available_instruction_templates(), value='None', label='Select the desired instruction template', elem_classes='slim-dropdown')
                        ui.create_refresh_button(shared.gradio['customized_template'], lambda: None, lambda: {'choices': utils.get_available_instruction_templates()}, 'refresh-button', interactive=not mu)

                    shared.gradio['customized_template_submit'] = gr.Button("Submit", variant="primary", interactive=not mu)
                    gr.Markdown("This allows you to set a customized template for the model currently selected in the \"Model loader\" menu.")

                with gr.Row():
                    shared.gradio['model_status'] = gr.Markdown('No model is loaded' if shared.model_name == 'None' else 'Ready')


def create_event_handlers():
    mu = shared.args.multi_user
    if mu:
        return

    shared.gradio['loader'].change(loaders.make_loader_params_visible, gradio('loader'), gradio(loaders.get_all_params()), show_progress=False)

    shared.gradio['model_menu'].change(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        handle_load_model_event_initial, gradio('model_menu', 'interface_state'), gradio(ui.list_interface_input_elements()) + gradio('interface_state') + gradio('vram_info'), show_progress=False).then(
        partial(load_model_wrapper, autoload=False), gradio('model_menu', 'loader'), gradio('model_status'), show_progress=True).success(
        handle_load_model_event_final, gradio('truncation_length', 'loader', 'interface_state'), gradio('truncation_length', 'filter_by_loader'), show_progress=False)

    shared.gradio['load_model'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        update_model_parameters, gradio('interface_state'), None).then(
        partial(load_model_wrapper, autoload=True), gradio('model_menu', 'loader'), gradio('model_status'), show_progress=True).success(
        handle_load_model_event_final, gradio('truncation_length', 'loader', 'interface_state'), gradio('truncation_length', 'filter_by_loader'), show_progress=False)

    shared.gradio['unload_model'].click(handle_unload_model_click, None, gradio('model_status'), show_progress=False).then(
        partial(update_gpu_layers_and_vram, auto_adjust=True), gradio('loader', 'model_menu', 'gpu_layers', 'ctx_size', 'cache_type'), gradio('vram_info', 'gpu_layers'), show_progress=False)

    shared.gradio['save_model_settings'].click(
        ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        save_model_settings, gradio('model_menu', 'interface_state'), gradio('model_status'), show_progress=False)

    for param in ['ctx_size', 'cache_type']:
        shared.gradio[param].change(
            partial(update_gpu_layers_and_vram, auto_adjust=True),
            gradio('loader', 'model_menu', 'gpu_layers', 'ctx_size', 'cache_type'),
            gradio('vram_info', 'gpu_layers'), show_progress=False)

    shared.gradio['gpu_layers'].change(
        partial(update_gpu_layers_and_vram, auto_adjust=False),
        gradio('loader', 'model_menu', 'gpu_layers', 'ctx_size', 'cache_type'),
        gradio('vram_info'), show_progress=False)

    if not shared.args.portable:
        shared.gradio['lora_menu_apply'].click(load_lora_wrapper, gradio('lora_menu'), gradio('model_status'), show_progress=False)

    shared.gradio['download_model_button'].click(download_model_wrapper, gradio('custom_model_menu', 'download_specific_file'), gradio('model_status'), show_progress=True)
    shared.gradio['get_file_list'].click(partial(download_model_wrapper, return_links=True), gradio('custom_model_menu', 'download_specific_file'), gradio('model_status'), show_progress=True)
    shared.gradio['customized_template_submit'].click(save_instruction_template, gradio('model_menu', 'customized_template'), gradio('model_status'), show_progress=True)

    shared.gradio['metrics_start_btn'].click(lambda: METRICS.start_monitoring(), None, gradio('metrics_status'), show_progress=False)
    shared.gradio['metrics_stop_btn'].click(lambda: METRICS.stop_monitoring(), None, gradio('metrics_status'), show_progress=False)
    shared.gradio['metrics_refresh_btn'].click(refresh_metrics_dashboard, None, gradio('metrics_display'), show_progress=False)
    if shared.gradio.get('metrics_timer') is not None:
        shared.gradio['metrics_timer'].tick(refresh_metrics_dashboard, None, gradio('metrics_display'), show_progress=False)

    shared.gradio['hub_search_btn'].click(
        search_hub_models,
        gradio('hub_query', 'hub_size_filter', 'hub_quant_filter'),
        gradio('hub_results'),
        show_progress=True,
    )
    shared.gradio['hub_download_btn'].click(
        lambda model_id: MODEL_HUB.download_model(model_id),
        gradio('hub_download_model_id'),
        gradio('hub_status'),
        show_progress=True,
    )
    shared.gradio['hub_more_info_btn'].click(
        get_model_info_html,
        gradio('hub_download_model_id'),
        gradio('hub_model_info'),
        show_progress=False,
    )


def load_model_wrapper(selected_model, loader, autoload=False):
    """Load model with full file validation before touching metadata."""
    from pathlib import Path

    if not selected_model or selected_model == 'None':
        yield "No model selected"
        return

    model_path = utils.resolve_model_path(selected_model)

    if not model_path.exists():
        yield (
            f"❌ Model file not found: **{selected_model}**\n\n"
            f"Expected path: `{model_path}`\n\n"
            f"Please re-download the model or check that the file is in `user_data/models/`."
        )
        return

    if selected_model.lower().endswith('.gguf'):
        if model_path.is_file():
            model_file = model_path
        else:
            gguf_files = list(model_path.glob('*.gguf'))
            if not gguf_files:
                yield f"❌ No GGUF files found in: `{model_path}`"
                return
            model_file = gguf_files[0]

        try:
            file_size = model_file.stat().st_size
            MIN_VALID_SIZE = 1024 * 1024  # 1 MB

            if file_size < MIN_VALID_SIZE:
                yield (
                    f"❌ Model file is too small ({file_size:,} bytes) and appears corrupt.\n\n"
                    f"File: `{model_file.name}`\n\n"
                    f"Please delete it and re-download the model."
                )
                return

        except Exception as e:
            yield f"❌ Cannot read file: {e}"
            return

    try:
        settings = get_model_metadata(selected_model)
    except FileNotFoundError:
        exc = traceback.format_exc()
        yield exc.replace('\n', '\n\n')
        return
    except Exception as e:
        yield f"❌ Error loading model metadata: {e}\n\nThe model file may be corrupt. Please re-download it."
        return

    if not settings:
        yield f"❌ Could not load metadata for `{selected_model}`. The file may be in an unsupported format."
        return

    if not autoload:
        yield "### {}\n\n- Settings updated — click **Load** to load the model\n- Max sequence length: {}".format(
            selected_model, settings.get('truncation_length_info', 'Unknown'))
        return

    try:
        yield f"Loading `{selected_model}`..."
        unload_model()
        if selected_model != '':
            shared.model, shared.tokenizer = load_model(selected_model, loader)

        if shared.model is not None:
            yield f"✅ Successfully loaded `{selected_model}`."
        else:
            yield f"❌ Failed to load `{selected_model}`."
    except Exception:
        exc = traceback.format_exc()
        logger.error('Failed to load the model.')
        print(exc)
        yield exc.replace('\n', '\n\n')


def load_lora_wrapper(selected_loras):
    yield ("Applying the following LoRAs to {}:\n\n{}".format(shared.model_name, '\n'.join(selected_loras)))
    add_lora_to_model(selected_loras)
    yield ("Successfully applied the LoRAs")


def download_model_wrapper(repo_id, specific_file, progress=gr.Progress(), return_links=False, check=False):
    downloader_module = importlib.import_module("download-model")
    downloader = downloader_module.ModelDownloader()
    update_queue = queue.Queue()

    try:
        if repo_id.startswith("https://") and ("huggingface.co" in repo_id) and (repo_id.endswith(".gguf") or repo_id.endswith(".gguf?download=true")):
            try:
                path = repo_id.split("huggingface.co/")[1]
                parts = path.split("/")
                if len(parts) >= 2:
                    extracted_repo_id = f"{parts[0]}/{parts[1]}"
                    filename = repo_id.split("/")[-1].replace("?download=true", "")
                    repo_id = extracted_repo_id
                    specific_file = filename
            except Exception as e:
                yield f"Error parsing GGUF URL: {e}"
                progress(0.0)
                return

        if not repo_id:
            yield "Please enter a model path."
            progress(0.0)
            return

        repo_id = repo_id.strip()
        specific_file = specific_file.strip()

        progress(0.0, "Preparing download...")

        model, branch = downloader.sanitize_model_and_branch_names(repo_id, None)
        yield "Getting download links from Hugging Face..."
        links, sha256, is_lora, is_llamacpp, file_sizes = downloader.get_download_links_from_huggingface(model, branch, text_only=False, specific_file=specific_file)

        if not links:
            yield "No files found to download for the given model/criteria."
            progress(0.0)
            return

        gguf_files = [link for link in links if link.lower().endswith('.gguf')]
        if len(gguf_files) > 1 and not specific_file:
            gguf_data = []
            for i, link in enumerate(links):
                if link.lower().endswith('.gguf'):
                    file_size = file_sizes[i]
                    gguf_data.append((file_size, link))

            gguf_data.sort(key=lambda x: x[0])

            output = "Multiple GGUF files found. Please copy one of the following filenames to the 'File name' field above:\n\n```\n"
            for file_size, link in gguf_data:
                size_str = format_file_size(file_size)
                output += f"{size_str} - {Path(link).name}\n"

            output += "```"
            yield output
            return

        if return_links:
            file_data = list(zip(file_sizes, links))
            file_data.sort(key=lambda x: x[0])

            output = "```\n"
            for file_size, link in file_data:
                size_str = format_file_size(file_size)
                output += f"{size_str} - {Path(link).name}\n"

            output += "```"
            yield output
            return

        yield "Determining output folder..."
        output_folder = downloader.get_output_folder(
            model, branch, is_lora, is_llamacpp=is_llamacpp,
            model_dir=shared.args.model_dir if shared.args.model_dir != shared.args_defaults.model_dir else None
        )

        if output_folder == Path("user_data/models"):
            output_folder = Path(shared.args.model_dir)
        elif output_folder == Path("user_data/loras"):
            output_folder = Path(shared.args.lora_dir)

        yield ""
        progress(0.0, "Download starting...")

        def downloader_thread_target():
            try:
                downloader.download_model_files(
                    model, branch, links, sha256, output_folder,
                    progress_queue=update_queue,
                    threads=4,
                    is_llamacpp=is_llamacpp,
                    specific_file=specific_file
                )
                update_queue.put(("COMPLETED", f"Model successfully saved to `{output_folder}/`."))
            except Exception as e:
                tb_str = traceback.format_exc().replace('\n', '\n\n')
                update_queue.put(("ERROR", tb_str))

        download_thread = threading.Thread(target=downloader_thread_target)
        download_thread.start()

        while True:
            try:
                message = update_queue.get(timeout=0.2)
                if not isinstance(message, tuple) or len(message) != 2:
                    continue

                msg_identifier, data = message

                if msg_identifier == "COMPLETED":
                    progress(1.0, "Download complete!")
                    yield data
                    break
                elif msg_identifier == "ERROR":
                    progress(0.0, "Error occurred")
                    yield data
                    break
                elif isinstance(msg_identifier, float):
                    progress(msg_identifier, f"Downloading: {data}")

            except queue.Empty:
                if not download_thread.is_alive():
                    yield "Download process finished."
                    break

        download_thread.join()

    except Exception:
        progress(0.0)
        tb_str = traceback.format_exc().replace('\n', '\n\n')
        yield tb_str


def update_truncation_length(current_length, state):
    if 'loader' in state:
        if state['loader'].lower().startswith('exllama') or state['loader'] == 'llama.cpp':
            return state['ctx_size']

    return current_length


def get_initial_vram_info():
    """
    ── FIX ──────────────────────────────────────────────────────────────────────
    Wrapped entirely in try/except so a missing or corrupt model file at startup
    NEVER crashes the server. Previously this called estimate_vram → load_metadata
    → open(file) which threw FileNotFoundError and killed the process.
    ─────────────────────────────────────────────────────────────────────────────
    """
    BLANK = "<div id=\"vram-info\">Estimated VRAM to load the model:</div>"

    try:
        if shared.model_name == 'None' or shared.args.loader != 'llama.cpp':
            return BLANK

        # Check the file actually exists before asking for VRAM
        from modules.utils import resolve_model_path
        model_file = resolve_model_path(shared.model_name)
        if not model_file.exists():
            logger.warning(
                f"get_initial_vram_info: model file not found: {shared.model_name} "
                f"— UI will start without VRAM estimate."
            )
            return BLANK

        return update_gpu_layers_and_vram(
            shared.args.loader,
            shared.model_name,
            shared.args.gpu_layers,
            shared.args.ctx_size,
            shared.args.cache_type,
            auto_adjust=False,
            for_ui=True
        )

    except Exception as e:
        # Log the problem but never let it kill the server
        logger.warning(f"get_initial_vram_info: non-fatal error — {e}")
        return BLANK


def get_initial_gpu_layers_max():
    """Return max GPU layers, safely — never crashes even if model is missing."""
    try:
        if shared.model_name != 'None' and shared.args.loader == 'llama.cpp':
            from modules.utils import resolve_model_path
            model_file = resolve_model_path(shared.model_name)
            if model_file.exists():
                model_settings = get_model_metadata(shared.model_name)
                return model_settings.get('max_gpu_layers', model_settings.get('gpu_layers', 256))
    except Exception as e:
        logger.warning(f"get_initial_gpu_layers_max: non-fatal error — {e}")

    return 256


def handle_load_model_event_initial(model, state):
    state = apply_model_settings_to_state(model, state)
    output = ui.apply_interface_values(state)
    update_model_parameters(state)

    vram_info = state.get('vram_info', "<div id=\"vram-info\">Estimated VRAM to load the model:</div>")
    return output + [state] + [vram_info]


def handle_load_model_event_final(truncation_length, loader, state):
    truncation_length = update_truncation_length(truncation_length, state)
    return [truncation_length, loader]


def handle_unload_model_click():
    unload_model()
    return "Model unloaded"


def format_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = size_bytes / p

    if i >= 3:
        return f"{s:.2f} {size_names[i]}"
    else:
        return f"{s:.1f} {size_names[i]}"

