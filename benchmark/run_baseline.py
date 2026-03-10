"""
benchmark/run_baseline.py

Runs LLM baselines separately from the compiler benchmark.
Run AFTER the compiler benchmark completes.

Usage:
    # Run both baselines in one pass (default)
    python benchmark/run_baseline.py \
        --results benchmark/results/results_set_d.json \
        --tasks   benchmark/tasks/tasks_set_d.json

    # Run a single baseline model
    python benchmark/run_baseline.py \
        --results benchmark/results/results_set_d.json \
        --tasks   benchmark/tasks/tasks_set_d.json \
        --model   gpt-4.1

Latency note:
    Runs where the subprocess hit the execution timeout (e.g. Flask servers
    not killed cleanly) are excluded from avg_duration_s calculations.
    They are counted separately as timeout_count and reported in the summary.
    This prevents artificially inflated latency averages.
"""

import argparse
import json
import os
import sys
import threading
import time
from glob import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.baseline import run_baseline

N_RUNS = 3

MODEL_PREFIX = {
    "gpt-4.1": "baseline_gpt41",
    "claude-sonnet-4-6": "baseline_claude",
}

ALL_MODELS = list(MODEL_PREFIX.keys())


def run_baseline_with_hard_timeout(
    task: dict,
    model: str,
    hard_timeout: int = 120,
) -> tuple[bool, str | None, dict, bool]:
    empty_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
    }
    result: dict = {
        "success": False,
        "error": "Hard timeout — task never completed",
        "usage": empty_usage,
        "timed_out": True,
        "done": False,
    }

    def _target():
        try:
            success, error, usage, timed_out = run_baseline(task, model=model)
            result["success"] = success
            result["error"] = error
            result["usage"] = usage
            result["timed_out"] = timed_out
            result["done"] = True
        except Exception as e:
            result["error"] = f"Unhandled exception: {e}"
            result["done"] = True

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=hard_timeout)

    if not result["done"]:
        print(f"  [!] Hard timeout ({hard_timeout}s) — abandoning task")

    return result["success"], result["error"], result["usage"], result["timed_out"]


def _write_summary(data: dict, prefix: str) -> None:
    all_results = data.get("results", [])
    if not all_results:
        return

    n = len(all_results)
    passes = sum(1 for r in all_results if r.get(f"{prefix}_success"))
    costs = [r.get(f"{prefix}_cost_usd", 0.0) for r in all_results]
    input_tokens = [r.get(f"{prefix}_input_tokens", 0) for r in all_results]
    output_tokens = [r.get(f"{prefix}_output_tokens", 0) for r in all_results]
    valid_durations = [
        r[f"{prefix}_avg_duration_s"]
        for r in all_results
        if r.get(f"{prefix}_avg_duration_s") is not None
    ]
    total_runs = sum(r.get(f"{prefix}_run_count", 0) for r in all_results)
    timeout_runs = sum(r.get(f"{prefix}_timeout_count", 0) for r in all_results)

    data[f"{prefix}_first_pass_rate"] = passes / n
    data[f"{prefix}_total_cost_usd"] = round(sum(costs), 6)
    data[f"{prefix}_avg_cost_per_task_usd"] = round(sum(costs) / n, 6) if n else 0
    data[f"{prefix}_avg_input_tokens"] = round(sum(input_tokens) / n, 1) if n else 0
    data[f"{prefix}_avg_output_tokens"] = round(sum(output_tokens) / n, 1) if n else 0
    data[f"{prefix}_avg_duration_s"] = (
        round(sum(valid_durations) / len(valid_durations), 2) if valid_durations else None
    )
    data[f"{prefix}_timeout_rate"] = round(timeout_runs / total_runs, 4) if total_runs else 0
    data[f"{prefix}_timeout_count"] = timeout_runs


def _run_single_model(
    data: dict,
    task_map: dict,
    results: list,
    model: str,
    hard_timeout: int,
) -> None:
    prefix = MODEL_PREFIX[model]
    n = len(results)

    print(f"\nBaseline model:   {model}")
    print(f"Tasks:            {n}")
    print(f"Runs per task:    {N_RUNS}  (passes only if all {N_RUNS} pass)")
    print(f"Hard timeout:     {hard_timeout}s per run")
    print(f"Latency:          timed-out runs excluded from avg_duration_s")
    print(f"Result prefix:    {prefix}_*")
    print("=" * 60)

    for i, result in enumerate(results):
        task_id = result["task_id"]
        task = task_map.get(task_id)

        if not task:
            print(f"\n[{i+1}/{n}] SKIP: no task definition for '{task_id}'")
            continue

        print(f"\n[{i+1}/{n}] {task_id}  ({N_RUNS} runs)")
        print(f"  {task['description'][:100]}")

        if task.get("skip_baseline"):
            print("  → SKIPPED (skip_baseline flag set)")
            result[f"{prefix}_success"] = None
            result[f"{prefix}_error"] = "skipped"
            result[f"{prefix}_pass_count"] = None
            result[f"{prefix}_run_count"] = N_RUNS
            result[f"{prefix}_timeout_count"] = 0
            result[f"{prefix}_duration_seconds"] = 0.0
            result[f"{prefix}_avg_duration_s"] = None
            result[f"{prefix}_input_tokens"] = 0
            result[f"{prefix}_output_tokens"] = 0
            result[f"{prefix}_total_tokens"] = 0
            result[f"{prefix}_cost_usd"] = 0.0
            result[f"{prefix}_runs"] = []
            if model == "gpt-4.1":
                result["baseline_success"] = None
            continue

        baseline_runs = []
        total_duration = 0.0
        non_timeout_dur = 0.0
        non_timeout_count = 0
        task_timeout_count = 0
        total_input = 0
        total_output = 0
        total_cost = 0.0

        for run_idx in range(N_RUNS):
            print(f"    run {run_idx+1}/{N_RUNS} ...", end=" ", flush=True)
            t0 = time.time()
            success, error, usage, timed_out = run_baseline_with_hard_timeout(
                task, model, hard_timeout
            )
            duration = round(time.time() - t0, 2)
            total_duration += duration

            if timed_out:
                task_timeout_count += 1
                timeout_marker = " [TIMEOUT — excluded from latency]"
            else:
                non_timeout_dur += duration
                non_timeout_count += 1
                timeout_marker = ""

            total_input += usage["input_tokens"]
            total_output += usage["output_tokens"]
            total_cost += usage["cost_usd"]

            status = "✓" if success else "✗"
            print(
                f"{status} ({duration}s | "
                f"in={usage['input_tokens']} out={usage['output_tokens']} "
                f"${usage['cost_usd']:.4f}){timeout_marker}"
            )
            if error and not success:
                print(f"      ! {str(error)[:120]}")

            baseline_runs.append({
                "run": run_idx + 1,
                "success": success,
                "error": error,
                "timed_out": timed_out,
                "duration_seconds": duration,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "total_tokens": usage["total_tokens"],
                "cost_usd": usage["cost_usd"],
            })

            if run_idx < N_RUNS - 1:
                time.sleep(2)

        pass_count = sum(1 for r in baseline_runs if r["success"])
        success = pass_count == N_RUNS
        avg_duration = round(non_timeout_dur / non_timeout_count, 2) if non_timeout_count > 0 else None
        last_error = next(
            (r["error"] for r in reversed(baseline_runs) if r["error"] and not r["success"]),
            None,
        )

        result[f"{prefix}_success"] = success
        result[f"{prefix}_error"] = last_error
        result[f"{prefix}_pass_count"] = pass_count
        result[f"{prefix}_run_count"] = N_RUNS
        result[f"{prefix}_timeout_count"] = task_timeout_count
        result[f"{prefix}_duration_seconds"] = round(total_duration, 2)
        result[f"{prefix}_avg_duration_s"] = avg_duration
        result[f"{prefix}_input_tokens"] = total_input
        result[f"{prefix}_output_tokens"] = total_output
        result[f"{prefix}_total_tokens"] = total_input + total_output
        result[f"{prefix}_cost_usd"] = round(total_cost, 6)
        result[f"{prefix}_runs"] = baseline_runs
        if model == "gpt-4.1":
            result["baseline_success"] = success

        overall = "✓ PASS" if success else "✗ FAIL"
        latency_str = f"{avg_duration}s/run" if avg_duration is not None else "N/A (all timed out)"
        print(
            f"  → {overall} ({pass_count}/{N_RUNS} passed | "
            f"timeouts={task_timeout_count}/{N_RUNS} | "
            f"avg latency={latency_str} | "
            f"cost=${total_cost:.4f})"
        )

        _write_summary(data, prefix)

    _write_summary(data, prefix)


def main():
    parser = argparse.ArgumentParser(
        description="Run LLM baseline(s) and merge results into existing results.json"
    )
    parser.add_argument("--results", required=True, help="Path to existing results.json from compiler run")
    parser.add_argument("--tasks", required=True, help="Path to tasks.json file or directory")
    parser.add_argument(
        "--model",
        default="all",
        choices=ALL_MODELS + ["all"],
        help="Which LLM baseline to run (default: all)",
    )
    parser.add_argument("--hard-timeout", type=int, default=120, help="Max seconds per run before abandoning (default: 120)")
    parser.add_argument("--task-id", help="Run baseline for a single task only (debugging)")
    args = parser.parse_args()

    models = ALL_MODELS if args.model == "all" else [args.model]

    if "gpt-4.1" in models and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set in environment / .env")
        sys.exit(1)
    if "claude-sonnet-4-6" in models and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set in environment / .env")
        sys.exit(1)

    with open(args.results) as f:
        data = json.load(f)

    tasks = []
    task_path = Path(args.tasks)
    if task_path.is_dir():
        for file in sorted(glob(str(task_path / "*.json"))):
            with open(file) as f:
                tasks.extend(json.load(f))
    else:
        with open(task_path) as f:
            tasks = json.load(f)

    task_map = {t["task_id"]: t for t in tasks}
    results = data["results"]

    if args.task_id:
        results = [r for r in results if r["task_id"] == args.task_id]
        if not results:
            print(f"No result found with task_id '{args.task_id}'")
            sys.exit(1)

    print(f"\nRunning baseline models: {', '.join(models)}")
    print(f"Tasks selected:          {len(results)}")

    for model in models:
        _run_single_model(data, task_map, results, model, args.hard_timeout)
        with open(args.results, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n[saved after {model}] {args.results}")
        if model != models[-1]:
            time.sleep(2)

    all_results = data["results"]
    total = len(all_results)
    compiler_passes = sum(1 for r in all_results if r.get("first_pass_success"))

    print(f"\n{'='*60}")
    print(f"Compiler passes:    {compiler_passes}/{total} ({100*compiler_passes//total}%)")
    for model in models:
        prefix = MODEL_PREFIX[model]
        baseline_passes = sum(1 for r in all_results if r.get(f"{prefix}_success"))
        total_cost = data.get(f"{prefix}_total_cost_usd", 0.0)
        avg_dur = data.get(f"{prefix}_avg_duration_s")
        timeout_rate = data.get(f"{prefix}_timeout_rate", 0)
        print(f"{model} passes:     {baseline_passes}/{total} ({100*baseline_passes//total}%)")
        print(f"{model} total cost: ${total_cost:.4f}")
        if total:
            print(f"{model} avg cost:   ${total_cost/total:.4f}")
        print(f"{model} avg lat:    {avg_dur}s  (timed-out runs excluded)")
        print(f"{model} timeout:    {timeout_rate*100:.1f}% of all runs")
        print("-" * 60)
    print(f"Results saved to:   {args.results}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
