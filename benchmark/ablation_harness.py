"""
benchmark/ablation_harness.py

Ablation study runner for LLM Code Graph Compiler.

Three ablation modes, each removing one constraint layer to isolate
its contribution to reliability.

Usage:
    # Run a specific ablation
    python benchmark/ablation_harness.py \\
        --tasks benchmark/tasks.json \\
        --output benchmark/ablation_results.json \\
        --mode blind-types

    # Run all three ablations and produce a merged comparison report
    python benchmark/ablation_harness.py \\
        --tasks benchmark/tasks.json \\
        --output benchmark/ablation_results.json \\
        --mode all

    # Single task debug
    python benchmark/ablation_harness.py \\
        --tasks benchmark/tasks_set_d.json \\
        --output benchmark/ablation_debug.json \\
        --mode no-registry \\
        --task-id set_d_01_monorepo_staged

Ablation modes:
    no-registry     Remove the node registry constraint entirely. The LLM
                    receives only the task description with no node list.
                    It is free to invent any nodes it wants. CHECK 1 in the
                    validator catches all hallucinated nodes. Measures tool
                    hallucination rate and taxonomy. Tests the core claim
                    that a fixed registry prevents hallucination failures.

    blind-types     Strip input/output types from the node summary sent to
                    the LLM. The validator still enforces type compatibility.
                    Tests whether communicating types to the LLM improves
                    plan quality, or whether the validator gate is doing all
                    the type-safety work.

    no-linearize    Remove edge linearization from normalize_plan. LLM-
                    proposed edges are used as-is instead of being enforced
                    to node[i] -> node[i+1] order. Tests whether normalize_
                    plan is silently carrying structural weight by fixing
                    bad LLM edge proposals before they reach the validator.

    all             Run all three ablations sequentially on the same task
                    set and write a merged comparison report.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable

# --- Allow imports from project root ---
sys.path.insert(0, str(Path(__file__).parent.parent))

from nodes.registry import NODE_REGISTRY
from nodes.types import NodeType
from core.compiler import compile_output
from benchmark.criteria import check_criteria

# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────

N_RUNS = 5  # Match harness.py default

ABLATION_MODES = [
    "no-registry",
    "blind-types",
    "no-linearize",
]


# ─────────────────────────────────────────────────────────────────────
# Patched planner functions (ablation variants)
# ─────────────────────────────────────────────────────────────────────

def build_node_summary_blind_types() -> str:
    """Strips input/output type info from the node summary."""
    lines = []
    for name, node in NODE_REGISTRY.items():
        lines.append(
            f"- {name}: {node.description} | required params: {node.required_params}"
        )
    return "\n".join(lines)


def build_node_summary_blind_params() -> str:
    """Strips required_params from the node summary."""
    lines = []
    for name, node in NODE_REGISTRY.items():
        lines.append(
            f"- {name}: {node.description} | input: {node.input_type} | output: {node.output_type}"
        )
    return "\n".join(lines)


def build_node_summary_blind_both() -> str:
    """Strips both types and params — description only. Useful as a control."""
    lines = []
    for name, node in NODE_REGISTRY.items():
        lines.append(f"- {name}: {node.description}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# no-registry planner — no node list given to the LLM
# ─────────────────────────────────────────────────────────────────────

NO_REGISTRY_SYSTEM_PROMPT = """
You are a code graph planner.

Design a node execution graph to solve the user's task.
You may use any nodes you think are appropriate.

Output STRICTLY raw JSON.

Response format must be:

{
  "nodes": [],
  "edges": [],
  "parameters": {},
  "flags": [],
  "glue_code": ""
}

Rules:
- nodes is a list of node type names you are selecting
- edges is a list of [source, target] pairs
- parameters maps node names to their configuration dicts
- Return raw JSON only.
"""


def get_plan_no_registry(task_description: str) -> dict:
    """
    Calls the LLM with no node registry — just the task description.
    The LLM is free to invent any nodes it wants.
    Hallucinated nodes will be caught by validator CHECK 1.
    """
    import requests as req
    from core.planner import normalize_plan

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": NO_REGISTRY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Task:\n{task_description}"},
        ],
        "temperature": 0,
    }

    for attempt in range(4):
        try:
            resp = req.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers, json=payload, timeout=45,
            )
            if resp.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            if 500 <= resp.status_code < 600:
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            break
        except Exception as e:
            if attempt == 3:
                raise RuntimeError(f"Planner failed: {e}")
            time.sleep(5)
    else:
        raise RuntimeError("Planner failed after 4 attempts")

    plan = json.loads(raw)
    return normalize_plan(plan)


def classify_hallucinated_nodes(nodes: list[str]) -> dict:
    """
    For no-registry runs: categorise which nodes are real vs hallucinated,
    and what the hallucinated ones look like.

    Returns a dict with:
        real          - nodes that exist in the registry
        hallucinated  - nodes that don't exist in the registry
        plausible     - hallucinated nodes that sound like real data ops
                        (contain words like Parser, Filter, Handler, etc.)
        invented      - hallucinated nodes with no resemblance to registry names
    """
    registry_names = set(NODE_REGISTRY.keys())
    plausible_keywords = {
        "parser", "filter", "handler", "connector", "engine", "exporter",
        "importer", "transformer", "validator", "selector", "sorter",
        "aggregator", "cleaner", "reader", "writer", "logger", "endpoint",
        "middleware", "caster", "joiner", "deduplicator", "summary",
    }

    real = [n for n in nodes if n in registry_names]
    hallucinated = [n for n in nodes if n not in registry_names]
    plausible = [n for n in hallucinated if any(k in n.lower() for k in plausible_keywords)]
    invented = [n for n in hallucinated if n not in plausible]

    return {
        "real": real,
        "hallucinated": hallucinated,
        "plausible": plausible,
        "invented": invented,
    }


# ─────────────────────────────────────────────────────────────────────
# Patched validator (broken-check3)
# ─────────────────────────────────────────────────────────────────────

def validate_plan_broken_check3(plan: dict) -> tuple[bool, list[str]]:
    """
    v4.x validator with the ANY wildcard bug.

    CHECK 3 only exempts target_input == ANY.
    Edges where source_output == ANY (e.g. Logger -> DataFilter) incorrectly
    raise TYPE_MISMATCH, making Logger unusable before any typed node.
    """
    from collections import deque

    errors: list[str] = []
    nodes = plan.get("nodes", [])
    edges = plan.get("edges", [])
    parameters = plan.get("parameters", {})

    # CHECK 1
    for node_name in nodes:
        if node_name not in NODE_REGISTRY:
            errors.append(f"NODE_NOT_FOUND: '{node_name}' not in registry.")
    if errors:
        return False, errors

    # CHECK 2
    for source, target in edges:
        if source not in nodes or target not in nodes:
            errors.append(f"EDGE_INVALID: [{source} -> {target}] references undefined node.")

    # CHECK 3 — BROKEN: only exempts target ANY, not source ANY
    for source, target in edges:
        if source not in NODE_REGISTRY or target not in NODE_REGISTRY:
            continue
        source_output = NODE_REGISTRY[source].output_type
        target_input = NODE_REGISTRY[target].input_type
        # v4.x bug: source_output == ANY is NOT exempted
        if target_input != NodeType.ANY and source_output != target_input:
            errors.append(
                f"TYPE_MISMATCH: [{source} -> {target}] "
                f"{source_output} != {target_input}"
            )

    # CHECK 4
    adj = defaultdict(list)
    in_degree = {node: 0 for node in nodes}
    for source, target in edges:
        adj[source].append(target)
        in_degree[target] += 1
    queue = deque([n for n in nodes if in_degree[n] == 0])
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    if visited != len(nodes):
        errors.append("CYCLE_DETECTED: graph contains a cycle.")

    # CHECK 5
    connected = set()
    for source, target in edges:
        connected.add(source)
        connected.add(target)
    for node in nodes:
        if len(nodes) > 1 and node not in connected:
            errors.append(f"ORPHAN_NODE: '{node}' is disconnected.")

    # CHECK 6
    in_degree = {node: 0 for node in nodes}
    for source, target in edges:
        in_degree[target] += 1
    for node_name in nodes:
        node = NODE_REGISTRY[node_name]
        if node.input_type != NodeType.FILE_PATH:
            if in_degree[node_name] != 1:
                errors.append(
                    f"INVALID_ARITY: '{node_name}' expects 1 inbound edge "
                    f"(input_type={node.input_type}), got {in_degree[node_name]}."
                )

    # CHECK 7
    for node_name in nodes:
        node = NODE_REGISTRY[node_name]
        provided = parameters.get(node_name, {})
        for param in node.required_params:
            if param not in provided:
                errors.append(f"MISSING_PARAM: '{node_name}' requires '{param}'.")

    return len(errors) == 0, errors


# ─────────────────────────────────────────────────────────────────────
# get_plan variants
# ─────────────────────────────────────────────────────────────────────

def _get_plan_with_summary(task_description: str, summary_fn: Callable) -> dict:
    """
    Calls the LLM with a custom node summary function.
    Mirrors planner.get_plan() structure exactly.
    """
    import re
    import requests as req

    SYSTEM_PROMPT = """
You are a code graph planner.

You select nodes from a fixed library and connect them to solve the user's task.

Output STRICTLY raw JSON.

Response format must be:

{
  "nodes": [],
  "edges": [],
  "parameters": {},
  "flags": [],
  "glue_code": ""
}

Rules:

- Only use nodes from the provided library.
- Never invent nodes.
- Every edge must be type-compatible.
- If a required node is missing, add flag MISSING_NODE.
- If credentials are needed, add flag REQUIRED_CREDENTIAL.
- Glue code must follow topological execution order.
- Return raw JSON only.
"""

    node_summary = summary_fn()
    user_message = f"""
Available Nodes:
{node_summary}

Task:
{task_description}
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0,
    }

    for attempt in range(4):
        try:
            resp = req.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=45,
            )
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  [planner] rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if 500 <= resp.status_code < 600:
                wait = 5 * (attempt + 1)
                print(f"  [planner] server error {resp.status_code}, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            break
        except req.exceptions.Timeout:
            if attempt == 3:
                raise RuntimeError("Planner API call timed out")
            time.sleep(5)
        except req.exceptions.RequestException as e:
            if attempt == 3:
                raise RuntimeError(f"Planner API call failed: {e}") from e
            time.sleep(5)
    else:
        raise RuntimeError("Planner failed after 4 attempts")

    # Import normalize_plan from core planner
    from core.planner import normalize_plan
    plan = json.loads(raw)
    return normalize_plan(plan)


def get_plan_no_linearize(task_description: str) -> dict:
    """
    Standard planner call but normalize_plan skips edge linearization.
    LLM-proposed edges are used as-is.
    """
    import re
    import requests as req
    from core.planner import SYSTEM_PROMPT

    node_summary_lines = []
    for name, node in NODE_REGISTRY.items():
        node_summary_lines.append(
            f"- {name}: {node.description} | input: {node.input_type} | output: {node.output_type} | required params: {node.required_params}"
        )
    node_summary = "\n".join(node_summary_lines)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Available Nodes:\n{node_summary}\n\nTask:\n{task_description}"},
        ],
        "temperature": 0,
    }

    for attempt in range(4):
        try:
            resp = req.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers, json=payload, timeout=45,
            )
            if resp.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            break
        except Exception as e:
            if attempt == 3:
                raise RuntimeError(f"Planner failed: {e}")
            time.sleep(5)
    else:
        raise RuntimeError("Planner failed after 4 attempts")

    plan = json.loads(raw)

    # Partial normalize_plan: do format normalization but SKIP edge linearization
    from core.planner import normalize_plan as _orig_normalize
    # Run the format normalization part only (node dict unwrapping, edge format cleanup)
    # by monkey-patching out the linearization block:
    plan = _normalize_no_linearize(plan)
    return plan


def _normalize_no_linearize(plan: dict) -> dict:
    """normalize_plan without the edge linearization override."""
    import re

    snake_to_camel = {node.function_name: name for name, node in NODE_REGISTRY.items()}

    raw_nodes = plan.get("nodes", [])
    if raw_nodes and isinstance(raw_nodes[0], dict):
        plan["nodes"] = [n["type"] for n in raw_nodes]
        if not plan.get("parameters"):
            plan["parameters"] = {n["type"]: n.get("params", {}) for n in raw_nodes}

    raw_nodes = plan.get("nodes", [])
    raw_edges = plan.get("edges", [])
    normalized_edges = []

    def resolve_node_ref(ref, nodes_list):
        if ref is None:
            return None
        if isinstance(ref, int):
            idx = ref - 1
            if 0 <= idx < len(nodes_list):
                return nodes_list[idx]
            if 0 <= ref < len(nodes_list):
                return nodes_list[ref]
            return None
        if isinstance(ref, str) and ref.isdigit():
            return resolve_node_ref(int(ref), nodes_list)
        return snake_to_camel.get(ref, ref)

    for edge in raw_edges:
        try:
            if isinstance(edge, dict):
                source = edge.get("from") or edge.get("source") or edge.get("start")
                target = edge.get("to") or edge.get("target") or edge.get("end")
            elif isinstance(edge, (list, tuple)) and len(edge) == 2:
                source, target = edge
            elif isinstance(edge, str) and "->" in edge:
                parts = edge.split("->")
                source, target = parts[0].strip(), parts[1].strip()
            else:
                continue
            source = resolve_node_ref(source, raw_nodes)
            target = resolve_node_ref(target, raw_nodes)
            if source is None or target is None:
                continue
            normalized_edges.append([source, target])
        except Exception:
            continue

    # Keep only non-self edges — but do NOT enforce linear order
    plan["edges"] = [e for e in normalized_edges if e[0] != e[1]]
    return plan


# ─────────────────────────────────────────────────────────────────────
# Result structure
# ─────────────────────────────────────────────────────────────────────

def empty_result(task_id: str, description: str, mode: str) -> dict:
    return {
        "task_id": task_id,
        "description": description,
        "ablation_mode": mode,
        "plan_success": False,
        "validation_success": False,
        "validation_skipped": False,
        "compile_success": False,
        "run_success": False,
        "criteria_passed": False,
        "first_pass_success": False,
        "pass_count": 0,
        "run_count": N_RUNS,
        "plan": None,
        "validation_errors": [],
        "compile_error": None,
        "run_stdout": "",
        "run_stderr": "",
        "run_returncode": None,
        "criteria_failures": [],
        "duration_seconds": None,
        "error": None,
        "runs": [],
        # no-registry only — hallucination taxonomy
        "hallucination": None,
    }


# ─────────────────────────────────────────────────────────────────────
# Single run per ablation mode
# ─────────────────────────────────────────────────────────────────────

def run_task_ablation(task: dict, mode: str) -> dict:
    result = empty_result(task["task_id"], task["description"], mode)
    start = time.time()

    with tempfile.TemporaryDirectory() as run_dir:
        try:
            # ── Stage 1: Plan (mode-specific) ─────────────────────────
            if mode == "no-registry":
                plan = get_plan_no_registry(task["description"])
            elif mode == "blind-types":
                plan = _get_plan_with_summary(task["description"], build_node_summary_blind_types)
            elif mode == "no-linearize":
                plan = get_plan_no_linearize(task["description"])
            else:
                from core.planner import get_plan
                plan = get_plan(task["description"])

            result["plan"] = plan
            result["plan_success"] = True

            # Hallucination taxonomy for no-registry runs
            if mode == "no-registry":
                result["hallucination"] = classify_hallucinated_nodes(
                    plan.get("nodes", [])
                )

        except Exception as e:
            result["error"] = f"Planner error: {e}"
            result["duration_seconds"] = round(time.time() - start, 2)
            return result

        # ── Stage 2: Validate (always runs — validator is not ablated) ─
        try:
            from core.validator import validate_plan
            ok, errors = validate_plan(plan)
            result["validation_errors"] = errors
            result["validation_success"] = ok

            if not ok:
                result["duration_seconds"] = round(time.time() - start, 2)
                return result

        except Exception as e:
            result["error"] = f"Validator error: {traceback.format_exc()}"
            result["duration_seconds"] = round(time.time() - start, 2)
            return result

        # ── Stage 3: Compile ──────────────────────────────────────────
        try:
            code = compile_output(plan)
            app_path = os.path.join(run_dir, "app.py")
            with open(app_path, "w") as f:
                f.write(code)
            result["compile_success"] = True

        except Exception as e:
            result["compile_error"] = str(e)
            result["duration_seconds"] = round(time.time() - start, 2)
            return result

        # ── Stage 4: Execute ──────────────────────────────────────────
        try:
            fixtures = task.get("fixtures", {})
            for dest_name, src_path in fixtures.items():
                import shutil
                shutil.copy(src_path, os.path.join(run_dir, dest_name))

            proc = subprocess.Popen(
                [sys.executable, app_path],
                cwd=run_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=task.get("timeout_seconds", 30))
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                result["run_stdout"] = stdout
                result["run_stderr"] = stderr
                if task.get("timeout_is_expected"):
                    result["run_success"] = True
                    result["run_returncode"] = None
                else:
                    result["error"] = "Execution timed out"
                    result["duration_seconds"] = round(time.time() - start, 2)
                    return result

            result["run_stdout"] = stdout
            result["run_stderr"] = stderr
            result["run_returncode"] = proc.returncode
            result["run_success"] = proc.returncode == 0

            if not result["run_success"]:
                result["duration_seconds"] = round(time.time() - start, 2)
                return result

        except Exception as e:
            result["error"] = f"Execution error: {e}"
            result["duration_seconds"] = round(time.time() - start, 2)
            return result

        # ── Stage 5: Criteria ─────────────────────────────────────────
        criteria = task.get("success_criteria", [])
        if criteria:
            passed, failures = check_criteria(criteria, result["run_stdout"], run_dir)
            result["criteria_passed"] = passed
            result["criteria_failures"] = failures
        else:
            result["criteria_passed"] = True

    result["first_pass_success"] = (
        result["plan_success"]
        and result["validation_success"]
        and result["compile_success"]
        and result["run_success"]
        and result["criteria_passed"]
    )
    result["duration_seconds"] = round(time.time() - start, 2)
    return result


# ─────────────────────────────────────────────────────────────────────
# Multi-run aggregator
# ─────────────────────────────────────────────────────────────────────

def run_task_repeated_ablation(task: dict, mode: str) -> dict:
    runs = []
    last_full = None

    for run_idx in range(N_RUNS):
        print(f"    run {run_idx + 1}/{N_RUNS} ...", end=" ", flush=True)
        single = run_task_ablation(task, mode)
        status = "✓" if single["first_pass_success"] else "✗"
        print(f"{status} ({single['duration_seconds']}s)")

        runs.append({
            "run": run_idx + 1,
            "first_pass_success": single["first_pass_success"],
            "plan_success": single["plan_success"],
            "validation_success": single["validation_success"],
            "validation_skipped": single["validation_skipped"],
            "compile_success": single["compile_success"],
            "run_success": single["run_success"],
            "criteria_passed": single["criteria_passed"],
            "duration_seconds": single["duration_seconds"],
            "error": single.get("error"),
            "criteria_failures": single.get("criteria_failures", []),
            "validation_errors": single.get("validation_errors", []),
            "hallucination": single.get("hallucination"),
        })
        last_full = single

        if run_idx < N_RUNS - 1:
            time.sleep(2)

    pass_count = sum(1 for r in runs if r["first_pass_success"])
    last_full["pass_count"] = pass_count
    last_full["run_count"] = N_RUNS
    last_full["first_pass_success"] = (pass_count == N_RUNS)
    last_full["runs"] = runs
    return last_full


# ─────────────────────────────────────────────────────────────────────
# Summary printer
# ─────────────────────────────────────────────────────────────────────

def print_ablation_summary(results: list[dict], mode: str):
    n = len(results)
    passes = sum(1 for r in results if r["first_pass_success"])

    print(f"\n{'=' * 72}")
    print(f"ABLATION RESULTS — mode: {mode.upper()}")
    print(f"{'=' * 72}")
    print(f"Tasks run:           {n}")
    print(f"Runs per task:       {N_RUNS}")
    print(f"First-pass rate:     {passes}/{n} ({100 * passes // n if n else 0}%)")
    print(f"  (task passes only if all {N_RUNS} runs pass)")

    # Stage-level failure breakdown
    stage_counts = defaultdict(int)
    for r in results:
        if not r["first_pass_success"]:
            if not r["plan_success"]:
                stage_counts["planner"] += 1
            elif not r["validation_success"] and not r.get("validation_skipped"):
                stage_counts["validator"] += 1
            elif not r["compile_success"]:
                stage_counts["compiler"] += 1
            elif not r["run_success"]:
                stage_counts["runtime"] += 1
            elif not r["criteria_passed"]:
                stage_counts["criteria"] += 1

    if stage_counts:
        print("\nFailure breakdown by stage:")
        for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
            print(f"  {stage:<15} {count} task(s)")

    # Hallucination report for no-registry runs
    if mode == "no-registry":
        all_hallucinated = []
        tasks_with_any_hallucination = 0
        tasks_all_hallucinated = 0
        for r in results:
            h = r.get("hallucination") or {}
            hallucinated = h.get("hallucinated", [])
            if hallucinated:
                tasks_with_any_hallucination += 1
                all_hallucinated.extend(hallucinated)
            nodes = (r.get("plan") or {}).get("nodes", [])
            if nodes and all(n not in NODE_REGISTRY for n in nodes):
                tasks_all_hallucinated += 1

        from collections import Counter
        top_hallucinated = Counter(all_hallucinated).most_common(10)
        print(f"\nHallucination report:")
        print(f"  Tasks with ≥1 hallucinated node:  {tasks_with_any_hallucination}/{n}")
        print(f"  Tasks with ALL nodes hallucinated: {tasks_all_hallucinated}/{n}")
        print(f"  Total hallucinated node instances: {len(all_hallucinated)}")
        if top_hallucinated:
            print(f"  Most common hallucinated nodes:")
            for node_name, count in top_hallucinated:
                print(f"    {node_name:<35} (×{count})")

    print(f"\n{'ID':<20} {'Passes':<10} {'Result':<12} Stage Failed")
    print("-" * 60)
    for r in results:
        pass_str = f"{r.get('pass_count', '?')}/{r.get('run_count', N_RUNS)}"
        result_str = "✓ PASS" if r["first_pass_success"] else "✗ FAIL"
        if not r["plan_success"]:
            stage = "planner"
        elif not r["validation_success"] and not r.get("validation_skipped"):
            stage = f"validator ({len(r['validation_errors'])} errors)"
        elif not r["compile_success"]:
            stage = "compiler"
        elif not r["run_success"]:
            stage = f"runtime (exit {r['run_returncode']})"
        elif not r["criteria_passed"]:
            stage = f"criteria ({len(r['criteria_failures'])} failures)"
        else:
            stage = "—"
        print(f"{r['task_id']:<20} {pass_str:<10} {result_str:<12} {stage}")

    print("=" * 72)


def print_comparison_summary(all_results: dict[str, list[dict]]):
    """Prints a side-by-side comparison when --mode all is used."""
    print(f"\n{'=' * 72}")
    print("ABLATION COMPARISON SUMMARY")
    print(f"{'=' * 72}")
    print(f"{'Mode':<20} {'Pass Rate':<15} {'Validator Fails':<20} {'Runtime Fails'}")
    print("-" * 72)

    for mode, results in all_results.items():
        n = len(results)
        passes = sum(1 for r in results if r["first_pass_success"])
        val_fails = sum(
            1 for r in results
            if not r["first_pass_success"] and not r.get("validation_skipped")
            and not r["validation_success"]
        )
        run_fails = sum(
            1 for r in results
            if not r["first_pass_success"] and not r["run_success"]
        )
        rate = f"{passes}/{n} ({100 * passes // n if n else 0}%)"
        print(f"{mode:<20} {rate:<15} {val_fails:<20} {run_fails}")

    print("=" * 72)


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM Code Graph Compiler — Ablation Harness")
    parser.add_argument("--tasks", required=True, help="Path to tasks.json")
    parser.add_argument("--output", default="benchmark/ablation_results.json", help="Output JSON path")
    parser.add_argument(
        "--mode",
        required=True,
        choices=ABLATION_MODES + ["all"],
        help="Ablation mode to run"
    )
    parser.add_argument("--task-id", help="Run a single task by ID (for debugging)")
    args = parser.parse_args()

    with open(args.tasks) as f:
        tasks = json.load(f)

    if args.task_id:
        tasks = [t for t in tasks if t["task_id"] == args.task_id]
        if not tasks:
            print(f"No task found with id '{args.task_id}'")
            sys.exit(1)

    modes_to_run = ABLATION_MODES if args.mode == "all" else [args.mode]
    all_mode_results: dict[str, list[dict]] = {}

    for mode in modes_to_run:
        print(f"\n{'#' * 72}")
        print(f"# ABLATION MODE: {mode.upper()}")
        print(f"{'#' * 72}")

        results = []
        for i, task in enumerate(tasks):
            print(f"\n[{i + 1}/{len(tasks)}] {task['task_id']} ({N_RUNS} runs) [{mode}]")
            print(f"  {task['description']}")
            result = run_task_repeated_ablation(task, mode)

            status = "✓ PASS" if result["first_pass_success"] else "✗ FAIL"
            print(f"  → {status} ({result['pass_count']}/{result['run_count']} runs, {result['duration_seconds']}s last run)")
            if result.get("error"):
                print(f"  ! {result['error']}")
            if result.get("criteria_failures"):
                for fail in result["criteria_failures"]:
                    print(f"  ! {fail}")
            if result.get("validation_errors") and not result.get("validation_skipped"):
                for err in result["validation_errors"][:3]:
                    print(f"  ~ {err}")

            results.append(result)

            if i < len(tasks) - 1:
                time.sleep(5)

        print_ablation_summary(results, mode)
        all_mode_results[mode] = results

    if args.mode == "all":
        print_comparison_summary(all_mode_results)

    # ── Write output ──────────────────────────────────────────────────
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)

    output = {
        "run_at": datetime.utcnow().isoformat(),
        "task_count": len(tasks),
        "runs_per_task": N_RUNS,
        "modes_run": modes_to_run,
        "ablations": {
            mode: {
                "first_pass_rate": sum(1 for r in results if r["first_pass_success"]) / len(results) if results else 0,
                "pass_count": sum(1 for r in results if r["first_pass_success"]),
                "task_count": len(results),
                "results": results,
            }
            for mode, results in all_mode_results.items()
        }
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()