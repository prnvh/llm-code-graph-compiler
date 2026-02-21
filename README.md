# LLM Graph Code Compiler

A constrained code generation system where an LLM acts as a planner over predefined executable nodes instead of generating entire systems from scratch.

---

## Overview

Most current AI code generation systems rely on large language models to synthesize entire programs from memory. This works, but it has structural weaknesses:

- No enforced architecture  
- No static validation of component compatibility  
- No guarantees of execution flow correctness  
- High variance in outputs  
- Opaque reasoning paths  

This project explores a different paradigm:

> The LLM does not write systems directly.  
> It composes them.

Instead of generating arbitrary code, the model selects from a registry of predefined, typed execution nodes. These nodes are compiled into a directed execution graph and stitched together with minimal glue logic.

The LLM functions as a conductor, not a generator.

---

## Core Idea

A system request (e.g., "Build an API endpoint that fetches data and returns an LLM response") is translated into:

1. A set of required capabilities  
2. A graph of compatible nodes  
3. A validated execution order  
4. Compiled output code  

Each node:

- Has defined input/output types  
- Exposes metadata describing its capability  
- Can be validated before execution  

This allows structured composition rather than free-form generation.

---

## Architecture

The system consists of five primary components:

### 1. Node Registry

A database of reusable, typed building blocks.

Each node defines:
- Name  
- Input types  
- Output types  
- Execution logic  
- Required configuration (e.g., API keys)

Nodes are versioned and validated before inclusion.


### 2. Planner (LLM Layer)

The LLM receives a high-level request and outputs:
- Required capabilities  
- A proposed node composition graph  

Importantly, the LLM is constrained to selecting nodes that exist in the registry. It does not invent new primitives.


### 3. Validator

Before compilation:

- Type compatibility is checked  
- Cycles are rejected  
- Missing nodes are flagged  
- Unresolved configuration fields are surfaced  

Invalid compositions never reach compilation.


### 4. Compiler

The compiler:

- Orders nodes topologically  
- Generates glue code  
- Injects configuration placeholders  
- Produces executable output  

The result is deterministic given a valid graph.


### 5. CLI Interface

A simple entry point where a user provides:
- A natural language task  
- Optional configuration  

The system returns:
- Structured execution graph  
- Generated output code  
- Warnings for missing parameters  

---

## Why This Exists

This project explores a broader question:

Can AI assisted software construction become more deterministic, inspectable, and verifiable?

**Rather than:** LLM creating raw code and hoping it runs
**This system attempts:** LLM to Typed Graph to Validation to Compilation to Execution


The difference is structural guarantees.

---

## How This Differs From Standard LLM Codegen

**Standard model:**
- Token prediction  
- Implicit architecture  
- High flexibility, low guarantees  

**This model:**
- Explicit node registry  
- Typed interfaces  
- Graph validation  
- Constrained planning  

**Tradeoff:**
- Less raw creativity  
- More structural correctness  

---

## Relation to SVMP

This project extends the architectural philosophy introduced in SVMP v4.1.

SVMP constrains runtime reasoning through:
- Identity Frames (hard multi-tenant isolation)
- Intent Logic Forks (deterministic execution paths)
- Similarity Governance Gates (confidence thresholds)
- Exactly-once state processing

Its core principle is simple:

> The LLM must operate within structural constraints.

This Graph Code Compiler applies the same principle to system construction.

Where SVMP constrains conversational reasoning at runtime,  
this system constrains code generation at build-time.

Both replace unconstrained token generation with:
- Explicit control flow
- Deterministic validation
- Zero-trust architectural assumptions

---

## Current Status

Prototype phase.

Current goals:

- Implement minimal node registry  
- Validate graph construction  
- Compile simple multi-node systems  
- Demonstrate deterministic generation within a constrained domain  

---

## Future Directions

- Capability scoring of nodes  
- Cost-aware graph planning  
- Runtime execution tracing  
- Formal graph verification  
- Registry learning from usage  


