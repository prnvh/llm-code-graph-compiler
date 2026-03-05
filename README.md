# LLM Code Graph Compiler

A constraint-guided program synthesis system that uses an LLM to generate typed execution graphs over a fixed node library, then deterministically compiles them into executable Python artifacts.

---

## The Problem

Free-form LLM code generation has structural failure modes that don't go away with better prompting. Given a complex multi-step data pipeline task, a model generates code that:

- Invents column names inconsistently across steps
- Imports libraries that aren't installed, or uses deprecated API patterns
- Produces logically correct but structurally broken pipelines at longer chain lengths
- Generates different code across runs at identical temperature settings

These aren't hallucination failures in the usual sense. They're **structural drift** — the model losing coherence across a long generation. The failures compound with pipeline length, which is why baseline performance collapses on complex tasks while simple ones pass fine.

---

## The Approach

Instead of asking the LLM to write code, confine it to a single role: **select and parameterise nodes from a pre-verified registry.**

```
Task description
      ↓
  LLM Planner          ← only LLM call in the system
      ↓
  JSON Plan            (nodes + edges + parameters)
      ↓
  Validator            ← 7 deterministic checks, hard abort on failure
      ↓
  Compiler             ← topological sort + template assembly
      ↓
  app.py               ← self-contained executable, no runtime LLM calls
```

The LLM cannot produce a wrong column name when the node implementation is fixed. It cannot import a library that doesn't exist in the template. It cannot construct a type-incompatible pipeline when the validator enforces edge types before compilation. The reliability guarantee is structural, not probabilistic.

---

## Results

First-pass success rate (plan → validate → compile → execute → criteria, zero human intervention, 5 runs per task):

| Set | Pipeline Length | Compiler | Baseline GPT-4o | Delta |
|-----|----------------|----------|-----------------|-------|
| A | 3–5 nodes | 50/50 (100%) | 36/50 (72%) | +28pts |
| B | 5–8 nodes | 50/50 (100%) | 28/50 (56%) | +44pts |
| C | 8–10 nodes | 44/50 (88%) | 21/50 (42%) | +46pts |
| D | 10–12 nodes | 50/50 (100%) | 17/50 (34%) | +66pts |
| E | Schema traps | 45/50 (90%) | 8/50 (16%) | +74pts |
| F | SQLite roundtrips | 45/50 (90%) | 22/50 (44%) | +46pts |

The compiler's advantage grows monotonically with pipeline complexity. The baseline collapses at high node counts; the compiler does not. Wilson score 95% CI for Set D compiler: [93%, 100%]. Baseline CI: [10.8%, 60.3%]. The intervals do not overlap.

---

## Architecture

Five components in a strictly ordered pipeline. Only one involves an LLM call.

### Node Registry

The ground truth of all available primitives. 26 nodes across six categories: ingestion, DataFrame processing, storage, exporters, API/HTTP, and observability. Each node declares:

- `input_type` and `output_type` — one of `FilePath`, `DataFrame`, `DBHandle`, `HTTPResponse`, `ANY`
- `required_params` — enforced by the validator before compilation
- `function_name` — stored explicitly, used directly by the compiler with no string manipulation
- `template_path` — pre-written, pre-verified Python implementation on disk

The LLM planner can only reference nodes that exist in the registry. The validator rejects any plan referencing an unregistered node.

### Planner

The only LLM call in the system. Uses `gpt-4o-mini`. Receives the task description plus a serialised representation of the node registry (names, descriptions, input/output types, required params). Returns a JSON plan:

```json
{
  "nodes": ["CSVParser", "DataFilter", "SQLiteConnector", "QueryEngine", "CSVExporter"],
  "edges": [["CSVParser", "DataFilter"], ["DataFilter", "SQLiteConnector"], ["SQLiteConnector", "QueryEngine"], ["QueryEngine", "CSVExporter"]],
  "parameters": {
    "CSVParser": {"file_path": "data.csv"},
    "DataFilter": {"condition": "salary > 35000"},
    "SQLiteConnector": {"db_path": "out.db", "table_name": "employees"},
    "QueryEngine": {"query": "SELECT * FROM employees"},
    "CSVExporter": {"output_path": "results.csv"}
  },
  "flags": [],
  "glue_code": ""
}
```

`normalize_plan()` handles non-standard LLM output formats — integer node references, dict-style edges, string arrow notation — before the plan reaches the validator.

### Validator

Seven ordered checks. Any failure aborts compilation. No structurally invalid plan reaches the compiler.

| Check | What it catches |
|-------|----------------|
| 1 — Node existence | Any node not in the registry |
| 2 — Edge validity | Edges referencing nodes not declared in the plan |
| 3 — Type compatibility | `source.output_type != target.input_type` (with ANY wildcard exemption) |
| 4 — Acyclic | Cycle detection via Kahn's algorithm |
| 5 — No orphans | Nodes not connected to any edge |
| 6 — Input arity | Non-entry-point nodes must have exactly one inbound edge |
| 7 — Required params | Every `required_param` must be present in plan parameters |

### Compiler

Assembles the final output deterministically. No LLM involvement.

1. Topological sort produces linear execution order from the DAG
2. For each node in order, reads the template file verbatim from disk — no interpolation, no string manipulation
3. Auto-generates the execution block: `out_{function_name} = {function_name}(out_{predecessor}, **params)`
4. Uses LLM-provided `glue_code` only if present and non-empty

Output is a single self-contained `app.py` with a standard `__main__` block.

### Execution

Single subprocess invocation of `app.py`. State passes strictly through function return values — no shared mutable state, no global context between nodes. No LLM calls after compilation. Given the same valid plan and input fixtures, the compiler always emits identical output.

---

## Type System

Every node edge is typed. An edge from A to B is valid only if `A.output_type == B.input_type`, or either side is `ANY`.

| Type | Semantics | Produced by | Consumed by |
|------|-----------|-------------|-------------|
| `FilePath` | Path string to a file on disk | CSVExporter, JSONExporter | CSVParser, JSONParser, ExcelParser, SQLiteReader |
| `DataFrame` | pandas DataFrame in memory | All ingestion nodes | All processing nodes, all exporters |
| `DBHandle` | Active database connection context | SQLiteConnector, PostgresConnector | QueryEngine, RESTEndpoint |
| `HTTPResponse` | Flask HTTP response object | RESTEndpoint | AuthMiddleware, HTTPToDataFrame |
| `ANY` | Wildcard — edge passes if either side is ANY | Logger | Logger, ErrorHandler |

`ANY` exists for `Logger` (passthrough — insert anywhere without breaking the type chain) and `ErrorHandler` (accepts any upstream output). The v5.0 fix corrected a validator bug where `Logger → TypedNode` edges were incorrectly rejected: the original check only exempted `target_input == ANY`, not `source_output == ANY`.

---

## Node Library

### Ingestion
`CSVParser` · `JSONParser` · `ExcelParser`

### DataFrame Processing
`SchemaValidator` · `DataTransformer` · `DataFilter` · `ColumnSelector` · `NullHandler` · `DataSorter` · `TypeCaster` · `DataFrameJoin` · `StatsSummary` · `DataDeduplicator` · `Aggregator`

### Storage
`SQLiteConnector` · `SQLiteReader` · `PostgresConnector` · `QueryEngine`

> **SQLiteReader vs SQLiteConnector:** `SQLiteReader` is an entry-point node — it opens a pre-existing `.db` file from disk and must only appear at the start of a pipeline. For write-then-query, use `SQLiteConnector → QueryEngine` directly. Placing `SQLiteReader` after `SQLiteConnector` produces `TYPE_MISMATCH (DBHandle != FilePath)`, which the validator correctly catches.

### Exporters
`CSVExporter` · `JSONExporter`

### API / HTTP
`RESTEndpoint` · `AuthMiddleware` · `ErrorHandler`

### Observability
`Logger` — passthrough, insert anywhere without breaking the type chain

### Adapters
`HTTPToDataFrame`

---

## Setup

```bash
git clone https://github.com/prnvh/llm-code-graph-compiler
cd llm-code-graph-compiler
python -m venv .venv

# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
echo "OPENAI_API_KEY=your_key_here" > .env
```

**Dependencies:** `openai`, `pydantic`, `python-dotenv`, `pandas`, `sqlalchemy>=2.0`, `psycopg2-binary`, `flask`, `requests`

---

## Usage

```bash
# Natural language task
python cli.py --task "Read CSV file, filter rows where salary > 35000, store into SQLite, and export results"

# Specify nodes manually
python cli.py --nodes CSVParser DataFilter SQLiteConnector QueryEngine CSVExporter

# Load a pre-written plan
python cli.py --plan plans/my_plan.json
```

Every run: resolve plan → print advisory flags → validate (abort on failure) → compile → emit `output/app.py` + `output/requirements.txt`.

---

## Benchmark

### Running

```bash
# Compiler only (recommended first pass)
python benchmark/harness.py \
    --tasks benchmark/tasks/tasks_set_d.json \
    --output benchmark/results/results_set_d.json \
    --skip-baseline

# With baseline comparison
python benchmark/harness.py \
    --tasks benchmark/tasks/tasks_set_d.json \
    --output benchmark/results/results_set_d.json

# Single task debug
python benchmark/harness.py \
    --tasks benchmark/tasks/tasks_set_d.json \
    --output benchmark/results/debug.json \
    --skip-baseline \
    --task-id set_d_01_monorepo_staged
```

### Task Sets

300 total tasks across six sets (50 per set: 30 original + 20 probe tasks targeting known failure modes).

Sets A–D form a complexity ladder by pipeline length. Sets E and F are stress tests: E targets schema trap failures (null handling, type casting chains), F targets SQLite roundtrip data integrity.

Probe tasks 31–50 per set directly stress-test two systematic failure patterns: QueryEngine evasion (aggregation pushed into SQL strings) and Logger placement (ANY wildcard handling).

### Ablation Study

```bash
python benchmark/ablations/ablation_harness.py \
    --tasks benchmark/tasks/tasks_set_d.json \
    --output benchmark/ablations/ablation_d_all.json \
    --mode all
```

Three ablation modes isolate individual constraint contributions:

- **`no-registry`** — LLM receives no node list, may invent freely. Validator CHECK 1 catches all hallucinated nodes. Tests hallucination prevention and logs hallucination taxonomy per task.
- **`blind-types`** — type info stripped from the prompt, validator still enforces types. Tests whether type communication in the prompt improves plan quality, or whether the validator gate is doing all the type-safety work.
- **`no-linearize`** — edge normalization removed from `normalize_plan`, LLM-proposed edges used as-is. Tests whether structural normalization is silently absorbing bad LLM edge proposals before they reach the validator.

---

## Known Limitations

**QueryEngine evasion** — the planner satisfies aggregation tasks by embedding `GROUP BY COUNT(*)` in the `QueryEngine` SQL string rather than routing through `Aggregator`. This produces column `COUNT(*)` not `count`, failing `file_has_column` criteria. `QueryEngine` is the single unconstrained surface in the system — it accepts arbitrary SQL — and the planner systematically exploits it. 7 confirmed instances across Sets C, D, E, F. Probe tasks 31–50 quantify the evasion rate per complexity tier.

**Node uniqueness** — the plan schema uses node names as unique keys with no aliasing. Any pipeline requiring two instances of the same node type (two sorts, two database legs) is structurally inexpressible. Affected tasks are replaced with Logger-padded equivalents. Documented as approximate complexity tiers, not hard boundaries.

**No-op padding** — `TypeCaster(mapping={})` and `DataTransformer` with no operations appear in some tasks to reach node-count tier targets. Complexity tiers are approximate.

**Baseline API drift** — GPT-4o generates `engine.execute("SELECT ...")` — a SQLAlchemy 1.x pattern removed in 2.0 — across Sets B, C, and D. This is a training recency failure: syntactically valid code against a stale API assumption. The compiler is immune because node templates are environment-verified before registry inclusion. Reported as a distinct failure category in results.

**Single model and temperature** — all results use `gpt-4o-mini` at `temperature=0` for the planner and `gpt-4o` at `temperature=0` for the baseline. Generalization to other models or temperatures is untested.

**No fan-in or branching** — the execution model passes state strictly through single-predecessor function calls. CHECK 6 enforces this by rejecting any node with more than one inbound edge. Pipelines requiring data merges are not currently expressible.

---

## Reproducing Results

```bash
# Clean slate
rm benchmark/results/results_set_d.json
rm -f benchmark/fixtures/*.db benchmark/fixtures/output_*.csv

# Compiler run
python benchmark/harness.py \
    --tasks benchmark/tasks/tasks_set_d.json \
    --output benchmark/results/results_set_d.json \
    --skip-baseline

# Baseline run
python benchmark/run_baseline.py \
    --results benchmark/results/results_set_d.json \
    --tasks benchmark/tasks/tasks_set_d.json \
    --hard-timeout 120
```

Fixture row counts are fixed. `sales.csv`: 40 rows, 38 after deduplication, 27 with `revenue > 100`. These counts are embedded in task success criteria — regenerating fixtures without regenerating tasks will break `file_row_count` checks.

---

*Build Specification v5.0 · March 2026 · Pranav H.*