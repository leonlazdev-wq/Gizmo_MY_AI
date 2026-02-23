import json
import torch
import os
import pprint
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, List

try:
    import llama_cpp_binaries
except ImportError:
    # If llama_cpp_binaries is not available, create a fallback
    class llama_cpp_binaries:
        @staticmethod
        def get_binary_path():
            import shutil
            binary = shutil.which("llama-server") or shutil.which("llama-cpp-server")
            if binary:
                return binary
            return "PYTHON_SERVER"

import requests

from modules import shared
from modules.image_utils import (
    convert_image_attachments_to_pil,
    convert_openai_messages_to_images,
    convert_pil_to_base64
)
from modules.logging_colors import logger
from modules.utils import resolve_model_path

llamacpp_valid_cache_types = {"fp16", "q8_0", "q4_0"}


class LlamaServer:
    def __init__(self, model_path, server_path=None):
        """
        Initialize and start a server for llama.cpp models.
        """
        self.model_path = model_path
        self.server_path = server_path
        self.port = self._find_available_port()
        self.process = None
        self.session = requests.Session()
        self.vocabulary_size = None
        self.bos_token = "~~"
        self.last_prompt_token_count = 0

        # Start the server
        self._start_server()

    def encode(self, text, add_bos_token=False, **kwargs):
        if self.bos_token and text.startswith(self.bos_token):
            add_bos_token = False

        url = f"http://127.0.0.1:{self.port}/tokenize"
        payload = {
            "content": text,
            "add_special": add_bos_token,
        }

        response = self.session.post(url, json=payload)
        result = response.json()
        return result.get("tokens", [])

    def decode(self, token_ids, **kwargs):
        url = f"http://127.0.0.1:{self.port}/detokenize"
        payload = {
            "tokens": token_ids,
        }

        response = self.session.post(url, json=payload)
        result = response.json()
        return result.get("content", "")

    def prepare_payload(self, state):
        payload = {
            "temperature": state["temperature"] if not state["dynamic_temperature"] else (state["dynatemp_low"] + state["dynatemp_high"]) / 2,
            "dynatemp_range": 0 if not state["dynamic_temperature"] else (state["dynatemp_high"] - state["dynatemp_low"]) / 2,
            "dynatemp_exponent": state["dynatemp_exponent"],
            "top_k": state["top_k"],
            "top_p": state["top_p"],
            "min_p": state["min_p"],
            "top_n_sigma": state["top_n_sigma"] if state["top_n_sigma"] > 0 else -1,
            "typical_p": state["typical_p"],
            "repeat_penalty": state["repetition_penalty"],
            "repeat_last_n": state["repetition_penalty_range"],
            "presence_penalty": state["presence_penalty"],
            "frequency_penalty": state["frequency_penalty"],
            "dry_multiplier": state["dry_multiplier"],
            "dry_base": state["dry_base"],
            "dry_allowed_length": state["dry_allowed_length"],
            "dry_penalty_last_n": state["repetition_penalty_range"],
            "xtc_probability": state["xtc_probability"],
            "xtc_threshold": state["xtc_threshold"],
            "mirostat": state["mirostat_mode"],
            "mirostat_tau": state["mirostat_tau"],
            "mirostat_eta": state["mirostat_eta"],
            "grammar": state["grammar_string"],
            "seed": state["seed"],
            "ignore_eos": state["ban_eos_token"],
        }

        # DRY
        dry_sequence_breakers = state['dry_sequence_breakers']
        if not dry_sequence_breakers.startswith("["):
            dry_sequence_breakers = "[" + dry_sequence_breakers + "]"

        dry_sequence_breakers = json.loads(dry_sequence_breakers)
        payload["dry_sequence_breakers"] = dry_sequence_breakers

        # Sampler order
        if state["sampler_priority"]:
            samplers = state["sampler_priority"]
            samplers = samplers.split("\n") if isinstance(samplers, str) else samplers
            filtered_samplers = []
            penalty_found = False

            for s in samplers:
                if s.strip() in ["dry", "top_k", "top_p", "top_n_sigma", "min_p", "temperature", "xtc"]:
                    filtered_samplers.append(s.strip())
                elif s.strip() == "typical_p":
                    filtered_samplers.append("typ_p")
                elif not penalty_found and s.strip() == "repetition_penalty":
                    filtered_samplers.append("penalties")
                    penalty_found = True

            # Move temperature to the end if temperature_last is true and temperature exists in the list
            if state["temperature_last"] and "temperature" in samplers:
                samplers.remove("temperature")
                samplers.append("temperature")

            payload["samplers"] = filtered_samplers

        if state['custom_token_bans']:
            to_ban = [[int(token_id), False] for token_id in state['custom_token_bans'].split(',')]
            payload["logit_bias"] = to_ban

        return payload

    def _process_images_for_generation(self, state: dict) -> List[Any]:
        """
        Process all possible image inputs and return PIL images
        """
        pil_images = []

        # Source 1: Web UI (from chatbot_wrapper)
        if 'image_attachments' in state and state['image_attachments']:
            pil_images.extend(convert_image_attachments_to_pil(state['image_attachments']))

        # Source 2: Chat Completions API (/v1/chat/completions)
        elif 'history' in state and state.get('history', {}).get('messages'):
            pil_images.extend(convert_openai_messages_to_images(state['history']['messages']))

        # Source 3: Legacy Completions API (/v1/completions)
        elif 'raw_images' in state and state['raw_images']:
            pil_images.extend(state.get('raw_images', []))

        return pil_images

    def is_multimodal(self) -> bool:
        """Check if this model supports multimodal input."""
        return shared.args.mmproj not in [None, 'None']

    def generate_with_streaming(self, prompt, state):
        url = f"http://127.0.0.1:{self.port}/completion"
        payload = self.prepare_payload(state)

        pil_images = []
        if shared.is_multimodal:
            pil_images = self._process_images_for_generation(state)

        if pil_images:
            # Multimodal case
            IMAGE_TOKEN_COST_ESTIMATE = 600  # A safe, conservative estimate per image
            base64_images = [convert_pil_to_base64(img) for img in pil_images]

            payload["prompt"] = {
                "prompt_string": prompt,
                "multimodal_data": base64_images
            }

            # Calculate an estimated token count
            text_tokens = self.encode(prompt, add_bos_token=state["add_bos_token"])
            self.last_prompt_token_count = len(text_tokens) + (len(pil_images) * IMAGE_TOKEN_COST_ESTIMATE)
        else:
            # Text only case
            token_ids = self.encode(prompt, add_bos_token=state["add_bos_token"])
            self.last_prompt_token_count = len(token_ids)
            payload["prompt"] = token_ids

        if state['auto_max_new_tokens']:
            max_new_tokens = state['truncation_length'] - self.last_prompt_token_count
        else:
            max_new_tokens = state['max_new_tokens']

        payload.update({
            "n_predict": max_new_tokens,
            "stream": True,
            "cache_prompt": True
        })

        if shared.args.verbose:
            logger.info("GENERATE_PARAMS=")
            printable_payload = {k: v for k, v in payload.items() if k != "prompt"}
            pprint.PrettyPrinter(indent=4, sort_dicts=False).pprint(printable_payload)
            print()

        # Make the generation request
        response = self.session.post(url, json=payload, stream=True)

        try:
            if response.status_code == 400 and response.json()["error"]["type"] == "exceed_context_size_error":
                logger.error("The request exceeds the available context size, try increasing it")
            else:
                response.raise_for_status()  # Raise an exception for HTTP errors

            full_text = ""

            # Process the streaming response
            for line in response.iter_lines():
                if shared.stop_everything:
                    break

                if not line:
                    continue

                try:
                    line = line.decode('utf-8')

                    # Check if the line starts with "data: " and remove it
                    if line.startswith('data: '):
                        line = line[6:]  # Remove the "data: " prefix

                    # Parse the JSON data
                    data = json.loads(line)

                    # Extract the token content
                    if data.get('content', ''):
                        full_text += data['content']
                        yield full_text

                    # Check if generation is complete
                    if data.get('stop', False):
                        break

                except json.JSONDecodeError as e:
                    # Log the error and the problematic line
                    print(f"JSON decode error: {e}")
                    print(f"Problematic line: {line}")
                    continue

        finally:
            response.close()

    def generate(self, prompt, state):
        output = ""
        for output in self.generate_with_streaming(prompt, state):
            pass

        return output

    def get_logits(self, prompt, state, n_probs=128, use_samplers=False):
        """Get the logits/probabilities for the next token after a prompt"""
        url = f"http://127.0.0.1:{self.port}/completion"
        payload = self.prepare_payload(state)

        payload.update({
            "prompt": self.encode(prompt, add_bos_token=state["add_bos_token"]),
            "n_predict": 0,
            "logprobs": True,
            "n_probs": n_probs,
            "stream": False,
            "post_sampling_probs": use_samplers,
        })

        if shared.args.verbose and use_samplers:
            logger.info("GENERATE_PARAMS=")
            printable_payload = {k: v for k, v in payload.items() if k != "prompt"}
            pprint.PrettyPrinter(indent=4, sort_dicts=False).pprint(printable_payload)
            print()

        for retry in range(5):
            response = self.session.post(url, json=payload)
            result = response.json()

            if "completion_probabilities" in result:
                if use_samplers:
                    return result["completion_probabilities"][0]["top_probs"]
                else:
                    return result["completion_probabilities"][0]["top_logprobs"]
            else:
                raise Exception(f"Unexpected response format: 'completion_probabilities' not found in {result}")

    def _get_vocabulary_size(self):
        """Get and store the model's maximum context length."""
        url = f"http://127.0.0.1:{self.port}/v1/models"
        response = self.session.get(url).json()

        if "data" in response and len(response["data"]) > 0:
            model_info = response["data"][0]
            if "meta" in model_info and "n_vocab" in model_info["meta"]:
                self.vocabulary_size = model_info["meta"]["n_vocab"]

    def _get_bos_token(self):
        """Get and store the model's BOS token."""
        url = f"http://127.0.0.1:{self.port}/props"
        response = self.session.get(url).json()

        if "bos_token" in response:
            self.bos_token = response["bos_token"]

    def _find_available_port(self):
        """Find an available port by letting the OS assign one."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))  # Bind to port 0 to get an available port
            return s.getsockname()[1]

    def _start_server(self):
        """Start the llama.cpp server and wait until it's ready."""

        # Resolve server binary
        if self.server_path is None:
            self.server_path = llama_cpp_binaries.get_binary_path()
        
        # Check if we got a valid binary path
        if self.server_path == "PYTHON_SERVER" or not Path(self.server_path).exists():
            raise RuntimeError(
                "llama-server binary not found!\n\n"
                "Please install llama-cpp-python:\n"
                "  pip install llama-cpp-python\n\n"
                "Or build llama.cpp and place the binary in:\n"
                f"  {Path(__file__).parent.parent}/repositories/llama.cpp/build/bin/"
            )

        # --- GPU auto-detection ---
        has_gpu = torch.cuda.is_available()
        gpu_layers = shared.args.gpu_layers if has_gpu else 0

        if not has_gpu:
            logger.warning("No GPU detected → running llama.cpp in CPU-only mode")
            # Force CPU settings
            if shared.args.gpu_layers > 0:
                logger.info(f"Overriding gpu_layers from {shared.args.gpu_layers} to 0 (CPU mode)")
                gpu_layers = 0

        # Build base command
        cmd = [
            str(self.server_path),
            "--model", str(self.model_path),
            "--ctx-size", str(shared.args.ctx_size),
            "--batch-size", str(shared.args.batch_size),
            "--ubatch-size", str(shared.args.ubatch_size),
            "--port", str(self.port),
            "--no-webui",
        ]

        # GPU flags ONLY if GPU exists and gpu_layers > 0
        if has_gpu and gpu_layers > 0:
            cmd += ["--gpu-layers", str(gpu_layers)]
            # Flash attention only works on GPU
            try:
                cmd += ["--flash-attn"]
            except:
                pass

        # Optional performance flags
        if shared.args.threads > 0:
            cmd += ["--threads", str(shared.args.threads)]
        if shared.args.threads_batch > 0:
            cmd += ["--threads-batch", str(shared.args.threads_batch)]
        if shared.args.cpu_moe:
            cmd.append("--cpu-moe")
        if shared.args.no_mmap:
            cmd.append("--no-mmap")
        if shared.args.mlock:
            cmd.append("--mlock")

        # Tensor split (GPU multi-GPU only)
        if has_gpu and shared.args.tensor_split:
            cmd += ["--tensor-split", shared.args.tensor_split]

        # NUMA / memory
        if shared.args.numa:
            cmd += ["--numa", "distribute"]

        # KV cache
        if shared.args.no_kv_offload:
            cmd.append("--no-kv-offload")

        # Row split (multi-GPU)
        if has_gpu and shared.args.row_split:
            cmd += ["--split-mode", "row"]

        # Cache type
        cache_type = "fp16"
        if shared.args.cache_type in llamacpp_valid_cache_types:
            cmd += [
                "--cache-type-k", shared.args.cache_type,
                "--cache-type-v", shared.args.cache_type
            ]
            cache_type = shared.args.cache_type

        # Rope scaling
        if shared.args.compress_pos_emb != 1:
            cmd += ["--rope-freq-scale", str(1.0 / shared.args.compress_pos_emb)]
        if shared.args.rope_freq_base > 0:
            cmd += ["--rope-freq-base", str(shared.args.rope_freq_base)]

        # Multimodal projector
        if shared.args.mmproj not in [None, "None"]:
            path = Path(shared.args.mmproj)
            if not path.exists():
                path = Path("user_data/mmproj") / shared.args.mmproj
            if path.exists():
                cmd += ["--mmproj", str(path)]

        # Speculative decoding / draft model
        if shared.args.model_draft not in [None, 'None']:
            path = resolve_model_path(shared.args.model_draft)
            if path.is_file():
                model_file = path
            else:
                gguf_files = sorted(path.glob('*.gguf'))
                if gguf_files:
                    model_file = gguf_files[0]
                else:
                    logger.warning(f"No GGUF files found for draft model: {path}")
                    model_file = None

            if model_file:
                cmd += ["--model-draft", str(model_file)]

                if shared.args.draft_max > 0:
                    cmd += ["--draft-max", str(shared.args.draft_max)]
                if shared.args.gpu_layers_draft > 0:
                    cmd += ["--gpu-layers-draft", str(shared.args.gpu_layers_draft)]
                if shared.args.device_draft:
                    cmd += ["--device-draft", shared.args.device_draft]
                if shared.args.ctx_size_draft > 0:
                    cmd += ["--ctx-size-draft", str(shared.args.ctx_size_draft)]

        # Streaming LLM
        if shared.args.streaming_llm:
            cmd += ["--cache-reuse", "1"]
            cmd += ["--swa-full"]

        # Extra flags
        if shared.args.extra_flags:
            # Clean up the input
            extra_flags = shared.args.extra_flags.strip()
            if extra_flags.startswith('"') and extra_flags.endswith('"'):
                extra_flags = extra_flags[1:-1].strip()
            elif extra_flags.startswith("'") and extra_flags.endswith("'"):
                extra_flags = extra_flags[1:-1].strip()

            for flag_item in extra_flags.split(','):
                if '=' in flag_item:
                    flag, value = flag_item.split('=', 1)
                    if len(flag) <= 3:
                        cmd += [f"-{flag}", value]
                    else:
                        cmd += [f"--{flag}", value]
                else:
                    if len(flag_item) <= 3:
                        cmd.append(f"-{flag_item}")
                    else:
                        cmd.append(f"--{flag_item}")

        # Environment fix (Linux)
        env = os.environ.copy()
        if os.name == "posix":
            current_path = env.get('LD_LIBRARY_PATH', '')
            server_dir = os.path.dirname(str(self.server_path))
            if current_path:
                env['LD_LIBRARY_PATH'] = f"{current_path}:{server_dir}"
            else:
                env['LD_LIBRARY_PATH'] = server_dir

        # Log launch config
        logger.info(
            f"llama.cpp launch | GPU={has_gpu} | gpu_layers={gpu_layers} | "
            f"ctx={shared.args.ctx_size} | cache={cache_type}"
        )

        if shared.args.verbose:
            logger.info("llama-server command-line flags:")
            print(' '.join(str(item) for item in cmd[1:]))
            print()

        # Launch process
        try:
            self.process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,  # Suppress stdout
                bufsize=0,
                env=env
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Failed to start llama-server: Binary not found at {self.server_path}\n"
                "Please install llama-cpp-python or build llama.cpp manually."
            )

        threading.Thread(
            target=filter_stderr_with_progress,
            args=(self.process.stderr,),
            daemon=True
        ).start()

        # Wait for health endpoint
        health_url = f"http://127.0.0.1:{self.port}/health"
        max_wait = 120  # 2 minutes max
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"llama.cpp server exited with code {self.process.returncode}\n"
                    f"Check the server log for errors."
                )

            try:
                response = self.session.get(health_url, timeout=1)
                if response.status_code == 200:
                    break
            except Exception:
                pass

            time.sleep(1)
        else:
            # Timeout reached
            self.stop()
            raise RuntimeError(
                f"llama.cpp server failed to start within {max_wait} seconds\n"
                "The server may be taking too long to load the model."
            )

        # Fetch model metadata
        self._get_vocabulary_size()
        self._get_bos_token()

        logger.info(f"llama.cpp server ready on port {self.port}")
        return self.port

    def __enter__(self):
        """Support for context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager."""
        self.stop()

    def __del__(self):
        """Cleanup when the object is deleted."""
        self.stop()

    def stop(self):
        """Stop the server process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None


def filter_stderr_with_progress(process_stderr):
    """
    Reads stderr lines from a process, filters out noise, and displays progress updates 
    inline (overwriting the same line) until completion.
    """
    progress_re = re.compile(r'slot update_slots: id.*progress = (\d+\.\d+)')
    last_was_progress = False

    try:
        # Read in binary mode and decode manually
        buffer = b""
        while True:
            # Read chunks aggressively to prevent buffer overflow
            chunk = process_stderr.read(4096)
            if not chunk:
                break

            buffer += chunk

            # Process complete lines
            while b'\n' in buffer:
                line_bytes, buffer = buffer.split(b'\n', 1)
                try:
                    line = line_bytes.decode('utf-8', errors='replace').strip('\r\n')
                    if line:
                        # Process non-empty lines
                        match = progress_re.search(line)
                        if match:
                            progress = float(match.group(1))

                            # Extract just the part from "prompt processing" onwards
                            prompt_processing_idx = line.find('prompt processing')
                            if prompt_processing_idx != -1:
                                display_line = line[prompt_processing_idx:]
                            else:
                                display_line = line  # fallback to full line

                            # choose carriage return for in-progress or newline at completion
                            end_char = '\r' if progress < 1.0 else '\n'
                            print(display_line, end=end_char, file=sys.stderr, flush=True)
                            last_was_progress = (progress < 1.0)

                        # skip noise lines
                        elif not (line.startswith(('srv ', 'slot ')) or 'log_server_r: request: GET /health' in line):
                            # if we were in progress, finish that line first
                            if last_was_progress:
                                print(file=sys.stderr)
                            print(line, file=sys.stderr, flush=True)
                            last_was_progress = False

                except Exception:
                    continue

    except (ValueError, IOError):
        pass
    finally:
        try:
            process_stderr.close()
        except:
            pass
