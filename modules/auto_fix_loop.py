"""The Auto-Fix Pipeline.

Orchestrates the 'Code -> Test -> Fix -> Loop' autonomous system.
Since execution on the user's machine is dangerous, this module is currently
designed to pair with a secure sandbox environment like Piston, OR execute
pure function validation (doctests) rather than raw shell commands.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

from modules.dev_team import run_coder_phase
from modules.code_tutor import execute_code  # Reuse existing secure Piston API sandbox

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Prompts
# ------------------------------------------------------------------

AUTO_FIX_PROMPT = (
    "You are the Coder agent in an autonomous testing loop. Your previous code failed to run.\n"
    "Analyze the execution error below and rewrite the code so that it works correctly.\n\n"
    "Ensure you return ONLY the corrected code.\n"
)

# ------------------------------------------------------------------
# The Loop
# ------------------------------------------------------------------

def autonomous_loop(
    initial_prompt: str,
    context: str = "",
    language: str = "python",
    max_retries: int = 3
) -> Dict:
    """Generate code, execute it securely, and auto-fix errors heavily.
    
    Returns a dict with: status, iterations, final_code, error_history, execution_output
    """
    history = []
    
    # Initial generation via the default Coder
    # Assume Architect skipped for simplicity in small loop tests
    current_code, err = run_coder_phase(initial_prompt, "No architecture layout provided.", context)
    if err:
        return {"status": "error", "message": f"Initial generation failed: {err}"}
    
    # Strip markdown blocks if present (LLMs like providing ```python ... ```)
    def _strip_markdown(txt):
        if txt.startswith("```"):
            lines = txt.splitlines()[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines)
        return txt

    current_code = _strip_markdown(current_code)

    for attempt in range(max_retries):
        logger.info(f"Auto-Fix Loop Attempt {attempt + 1}/{max_retries}...")
        
        # We reuse the Piston sandbox from Code Tutor so we aren't executing raw
        # shell commands on the user's local hardware (Security First!)
        output_txt, err_txt, exit_code, success_flag = execute_code(language, current_code)
        
        # If execution failed (API error, not code error)
        if not success_flag:
            history.append({"attempt": attempt + 1, "action": "Execution API Failed", "result": output_txt})
            break
            
        # Code executed successfully with no stderr (exit code 0 usually means success)
        if exit_code == 0 and not err_txt:
            history.append({"attempt": attempt + 1, "action": "Success", "result": output_txt})
            return {
                "status": "success",
                "iterations": attempt + 1,
                "final_code": current_code,
                "execution_output": output_txt,
                "history": history
            }
            
        # Code failed with an error
        error_info = err_txt or output_txt
        history.append({
            "attempt": attempt + 1, 
            "action": f"Failed with Exit Code {exit_code}",
            "result": error_info
        })
        
        logger.info(f"Execution failed. Prompting LLM with Stderr: {error_info[:100]}...")
        
        # Generate fix based on traceback
        fix_prompt = (
            f"--- ORIGINAL PROMPT ---\n{initial_prompt}\n\n"
            f"--- FAILED CODE ---\n{current_code}\n\n"
            f"--- EXECUTION ERROR / STDERR ---\n{error_info}\n\n"
            f"{AUTO_FIX_PROMPT}"
        )
        
        from modules.ai_helper import call_ai
        fixed_code, model_err = call_ai(fix_prompt)
        
        if model_err:
            history.append({"attempt": attempt + 1, "action": "Model Error on Fix", "result": str(model_err)})
            break
            
        current_code = _strip_markdown(fixed_code)

    return {
        "status": "failed",
        "iterations": max_retries,
        "final_code": current_code,  # The last attempt
        "history": history,
        "message": f"Failed to produce working code after {max_retries} attempts."
    }
