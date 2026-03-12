"""
benchmark/baseline.py

Direct LLM baseline for benchmark comparison.

Prompts an LLM to write a complete Python script for the task,
then executes it and checks the same success criteria.
The prompt deliberately gives the model no scaffolding — pure generation.

Supported models: "gpt-4.1" (default), "claude-sonnet-4-6"

Token tracking:
    run_baseline returns (success, error, usage, timed_out) where:
        usage     = {"input_tokens": int, "output_tokens": int,
                     "total_tokens": int, "cost_usd": float}
        timed_out = True if execution hit the timeout (e.g. Flask server).
                    Timed-out runs are excluded from latency averages in
                    run_baseline.py to avoid artificially inflating them.
"""

import os
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import requests as req
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────
# Pricing (per 1M tokens, USD)
# ─────────────────────────────────────────────────────────────────────
PRICING = {
    "gpt-4.1": {
        "input": 2.00,
        "output": 8.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
    },
    "MiniMax-M2.5": {
        "input": 1.10,
        "output": 4.40,
    },
}

BASELINE_SYSTEM_PROMPT = """You are an expert Python developer.
Write a complete, runnable Python script that accomplishes the task described.
Return only the Python code — no explanation, no markdown fences, no preamble.
The script must run as-is with standard Python libraries plus pandas, sqlalchemy 2.0, and flask."""


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING.get(model, {"input": 0.0, "output": 0.0})
    return round(
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"],
        6,
    )


# ─────────────────────────────────────────────────────────────────────
# Model calls — return (code, input_tokens, output_tokens)
# ─────────────────────────────────────────────────────────────────────

def _call_openai(prompt: str, model: str = "gpt-4.1", timeout: int = 60) -> tuple[str, int, int]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    for attempt in range(4):
        try:
            resp = req.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  [baseline-openai] rate limited, waiting {wait}s (attempt {attempt+1}/4)...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            body = resp.json()
            code = body["choices"][0]["message"]["content"].strip()
            usage = body.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            return code, input_tokens, output_tokens
        except req.exceptions.Timeout:
            if attempt == 3:
                raise RuntimeError(f"OpenAI baseline API call timed out after {timeout} seconds")
            print(f"  [baseline-openai] timeout, retrying (attempt {attempt+1}/4)...")
            time.sleep(5)
        except Exception as e:
            raise RuntimeError(f"OpenAI baseline API call failed: {e}") from e
    raise RuntimeError("OpenAI baseline failed after 4 attempts")


def _call_claude(prompt: str, timeout: int = 60) -> tuple[str, int, int]:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "temperature": 0,
        "system": BASELINE_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }
    for attempt in range(4):
        try:
            resp = req.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  [baseline-claude] rate limited, waiting {wait}s (attempt {attempt+1}/4)...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            body = resp.json()
            content = body.get("content", [])
            code = "".join(
                block["text"] for block in content if block.get("type") == "text"
            ).strip()
            usage = body.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            return code, input_tokens, output_tokens
        except req.exceptions.Timeout:
            if attempt == 3:
                raise RuntimeError(f"Claude API call timed out after {timeout} seconds")
            print(f"  [baseline-claude] timeout, retrying (attempt {attempt+1}/4)...")
            time.sleep(5)
        except Exception as e:
            raise RuntimeError(f"Claude baseline API call failed: {e}") from e
    raise RuntimeError("Claude baseline failed after 4 attempts")


def _call_minimax(prompt: str, timeout: int = 60) -> tuple[str, int, int]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('MINIMAX_API_KEY', '')}",
    }
    payload = {
        "model": "MiniMax-M2.5",
        "messages": [
            {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.01,
    }
    for attempt in range(4):
        try:
            resp = req.post(
                "https://api.minimax.io/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  [baseline-minimax] rate limited, waiting {wait}s (attempt {attempt+1}/4)...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            body = resp.json()
            code = body["choices"][0]["message"]["content"].strip()
            usage = body.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            return code, input_tokens, output_tokens
        except req.exceptions.Timeout:
            if attempt == 3:
                raise RuntimeError(f"MiniMax baseline API call timed out after {timeout} seconds")
            print(f"  [baseline-minimax] timeout, retrying (attempt {attempt+1}/4)...")
            time.sleep(5)
        except Exception as e:
            raise RuntimeError(f"MiniMax baseline API call failed: {e}") from e
    raise RuntimeError("MiniMax baseline failed after 4 attempts")


# ─────────────────────────────────────────────────────────────────────
# Process execution with hard kill
# ─────────────────────────────────────────────────────────────────────

def _kill_process_group(proc: subprocess.Popen) -> None:
    try:
        if sys.platform == "win32":
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _communicate_with_timeout(
    proc: subprocess.Popen,
    timeout_secs: int,
) -> tuple[str, str, bool]:
    result: dict = {"stdout": "", "stderr": ""}

    def _target():
        try:
            out, err = proc.communicate()
            result["stdout"] = out or ""
            result["stderr"] = err or ""
        except Exception:
            pass

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=timeout_secs)

    if t.is_alive():
        _kill_process_group(proc)
        t.join(timeout=5)
        return result["stdout"], result["stderr"], True

    return result["stdout"], result["stderr"], False


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────

def run_baseline(
    task: dict,
    model: str = "gpt-4.1",
) -> tuple[bool, str | None, dict, bool]:
    """
    Runs an LLM directly on the task description, executes the result,
    and checks the same success criteria as the compiler.

    Args:
        task:  Task dict from tasks.json
        model: "gpt-4.1" (default) or "claude-sonnet-4-6"

    Returns:
        (success: bool, error: str | None, usage: dict, timed_out: bool)

        usage keys:
            input_tokens  : int
            output_tokens : int
            total_tokens  : int
            cost_usd      : float

        timed_out:
            True if the subprocess hit the execution timeout.
            These runs are excluded from latency averages by run_baseline.py.
            A timed-out run is always scored as a failure unless
            timeout_is_expected is set on the task (e.g. Flask servers).
    """
    empty_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
    }

    try:
        if model == "claude-sonnet-4-6":
            code, input_tokens, output_tokens = _call_claude(task["description"])
        elif model == "gpt-4.1":
            code, input_tokens, output_tokens = _call_openai(task["description"], model=model)
        elif model == "MiniMax-M2.5":
            code, input_tokens, output_tokens = _call_minimax(task["description"])
        else:
            return False, f"Unsupported baseline model: {model}", empty_usage, False

        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": _compute_cost(model, input_tokens, output_tokens),
        }

        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    except Exception as e:
        return False, f"Baseline generation failed ({model}): {e}", empty_usage, False

    with tempfile.TemporaryDirectory() as run_dir:
        app_path = os.path.join(run_dir, "app.py")
        with open(app_path, "w", encoding="utf-8") as f:
            f.write(code)

        for dest_name, src_path in task.get("fixtures", {}).items():
            try:
                shutil.copy(src_path, os.path.join(run_dir, dest_name))
            except Exception as e:
                return False, f"Fixture copy failed ({dest_name}): {e}", usage, False

        try:
            popen_kwargs = dict(
                cwd=run_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if sys.platform != "win32":
                popen_kwargs["start_new_session"] = True

            proc = subprocess.Popen([sys.executable, app_path], **popen_kwargs)
        except Exception as e:
            return False, f"Baseline launch error: {e}", usage, False

        timeout = task.get("timeout_seconds", 30)
        stdout, stderr, timed_out = _communicate_with_timeout(proc, timeout)
        returncode = proc.returncode

        if timed_out:
            if not task.get("timeout_is_expected"):
                return False, "Baseline execution timed out", usage, True
        elif returncode != 0:
            return False, f"Baseline runtime error (exit {returncode}):\n{stderr[:500]}", usage, False

        criteria = task.get("success_criteria", [])
        if not criteria:
            return True, None, usage, timed_out

        from benchmark.criteria import check_criteria

        passed, failures = check_criteria(criteria, stdout, run_dir)
        if not passed:
            return False, "Criteria failures:\n" + "\n".join(failures), usage, timed_out

        return True, None, usage, timed_out
