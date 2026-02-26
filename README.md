# LLM Code Graph Compiler

A constraint-guided program synthesis system that uses large language models to plan execution graphs over a fixed library of typed template nodes, then deterministically compiles them into executable Python artifacts.

## Overview

Instead of generating free-form source code, this system:

- Converts a task description into a structured graph plan.
- Validates the plan for structural and type safety.
- Topologically schedules execution nodes.
- Assembles executable Python code by composing template primitives.

The design improves reliability in code generation by restricting synthesis inside a graph-constrained template execution space.

## Pipeline

The system follows this execution flow:

Task Description
↓
Planner (LLM or stub planner)
↓
Validator (graph structure, type compatibility, parameter completeness)
↓
Topological Scheduler
↓
Compiler (template assembly)
↓
Executable Python Artifact


## Node Registry

Computation is performed using a fixed library of template nodes.

Each node is defined with:
- Input type and output type semantics
- Required parameters
- Path to implementation template

Nodes are stored inside:
nodes/registry.py
nodes/types.py
nodes/templates/


## CLI Usage

Generate code using manual node composition:
python cli.py --nodes CSVParser QueryEngine

Generate code from plan JSON:
python cli.py --plan tests/test_plan.json

Generate code from task description using LLM planner:
python cli.py --task "Read CSV file, store into SQLite, and query data"


Artifacts are emitted to:

output/app.py
output/requirements.txt


## Planner
Two planning modes are supported:

- Deterministic stub planner for testing
- OpenAI-based planner that produces structured synthesis plans

Planner output must conform to:


{
"nodes": [],
"edges": [],
"parameters": {},
"flags": [],
"glue_code": ""
}


## Validation
The validator enforces:

- Node existence
- Directed acyclic graph structure
- Type compatibility between connected nodes
- Required parameter presence
- Orphan node detection

## Compiler
The compiler performs deterministic artifact synthesis by:

- Loading template code from registry paths
- Ordering nodes using topological sorting
- Emitting templates sequentially
- Adding execution stubs
- Allowing optional glue code injection

## Reliability Analysis Module

A standalone utility exists for estimating synthesis plan quality using structural connectivity and type coherence metrics.
File location:
core/reliability.py

This module is not integrated into the execution pipeline.

## Requirements
pydantic
pandas
openai

