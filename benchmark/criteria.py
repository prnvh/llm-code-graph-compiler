"""
benchmark/criteria.py

Shared success criteria checker used by both harness.py and baseline.py.

Supported criterion types:
    file_exists             — file must exist
    file_row_count          — exact row count
    file_row_count_gte      — row count >= expected (for filtered outputs)
    file_has_column         — column must be present
    stdout_contains         — substring must appear in stdout

All checks are additive — every defined criterion must pass.
"""

import os
import pandas as pd


def _read_tabular(path: str) -> pd.DataFrame:
    """Read CSV or JSON file into DataFrame."""
    if path.endswith(".json"):
        return pd.read_json(path)
    return pd.read_csv(path)


def check_criteria(
    criteria: list,
    stdout: str,
    run_dir: str,
) -> tuple[bool, list[str]]:
    """
    Evaluates all criteria against run artifacts.

    Returns:
        (all_passed: bool, failure_messages: list[str])
    """
    failures = []

    for c in criteria:
        ctype = c["type"]

        # ── file_exists ────────────────────────────────────────────
        if ctype == "file_exists":
            full_path = os.path.join(run_dir, c["path"])
            if not os.path.exists(full_path):
                failures.append(
                    f"file_exists: '{c['path']}' not found"
                )

        # ── file_row_count (exact) ─────────────────────────────────
        elif ctype == "file_row_count":
            full_path = os.path.join(run_dir, c["path"])
            try:
                df = _read_tabular(full_path)
                if len(df) != c["expected"]:
                    failures.append(
                        f"file_row_count: '{c['path']}' has {len(df)} rows, "
                        f"expected {c['expected']}"
                    )
            except Exception as e:
                failures.append(
                    f"file_row_count: could not read '{c['path']}': {e}"
                )

        # ── file_row_count_gte (at least N rows) ───────────────────
        elif ctype == "file_row_count_gte":
            full_path = os.path.join(run_dir, c["path"])
            try:
                df = _read_tabular(full_path)
                if len(df) < c["expected"]:
                    failures.append(
                        f"file_row_count_gte: '{c['path']}' has {len(df)} rows, "
                        f"expected >= {c['expected']}"
                    )
            except Exception as e:
                failures.append(
                    f"file_row_count_gte: could not read '{c['path']}': {e}"
                )

        # ── file_has_column ────────────────────────────────────────
        elif ctype == "file_has_column":
            full_path = os.path.join(run_dir, c["path"])
            try:
                df = _read_tabular(full_path)
                if c["column"] not in df.columns:
                    failures.append(
                        f"file_has_column: column '{c['column']}' not in "
                        f"'{c['path']}' (got: {list(df.columns)})"
                    )
            except Exception as e:
                failures.append(
                    f"file_has_column: could not read '{c['path']}': {e}"
                )

        # ── stdout_contains ────────────────────────────────────────
        elif ctype == "stdout_contains":
            if c["expected"] not in (stdout or ""):
                failures.append(
                    f"stdout_contains: expected '{c['expected']}' not found in output"
                )

        else:
            failures.append(f"unknown criterion type: '{ctype}'")

    return len(failures) == 0, failures