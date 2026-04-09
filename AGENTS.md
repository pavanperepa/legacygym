# AGENTS.md

## Purpose

This repository implements a real-world OpenEnv environment for legacy code modernization.

The environment focuses on COBOL-to-Python migration as an agent task:
- the agent receives legacy COBOL source and task context,
- the agent generates or edits Python code,
- only the generated Python is executed,
- the environment scores correctness, maintainability, and safe behavior.

This repo is not a production migration platform. It is an evaluation/training environment for agents.

---

## Read Order

Before making changes, read files in this order:

1. `AGENTS.md`
2. `HACKATHON_REQUIREMENTS.md`
3. `SUBMISSION_GUARDRAILS.md`

Do not make architectural decisions without following these files.

---

## Fixed Assumptions

These decisions are already made and must not be re-decided unless absolutely necessary:

1. COBOL is provided as input text only.
2. COBOL is not executed at runtime.
3. The environment executes only agent-generated Python.
4. Scoring is based on:
   - functional correctness,
   - visible and hidden tests,
   - maintainability / coding quality,
   - safe behavior and penalties for undesirable actions.
5. The environment must remain deterministic and lightweight.
6. Do not build a full enterprise-grade sandbox.
7. Prefer a controlled Python runner with timeout and restricted execution behavior.
8. Build the shared skeleton first, then implement tasks on top of it.
9. The repo must be compatible with the required inference flow and stdout format used by the hackathon sample script. :contentReference[oaicite:1]{index=1}

---

## Project Goal

Build an OpenEnv-compatible environment where an agent iteratively migrates legacy COBOL logic into Python and is rewarded for preserving business behavior while improving code quality.

The environment should feel like a real modernization workflow:
- inspect legacy code,
- generate Python,
- run tests,
- inspect failures,
- refine the solution,
- submit a final answer.

---

## What This Repo Must Implement

The final repo must support:

- typed models for observation, action, and reward,
- environment state management,
- `reset()`,
- `step(action)`,
- `state()`,
- at least 3 tasks with increasing difficulty,
- deterministic graders that score from `0.0` to `1.0`,
- meaningful partial-progress reward,
- a root-level `inference.py`,
- reproducible baseline behavior,
- container-ready structure for later deployment.

The inference integration must work with the sample pattern:
- OpenAI client for LLM calls,
- environment created from Docker image when needed,
- task/env/model logging in the required stdout format. :contentReference[oaicite:2]{index=2}

---

## Current Repo Expectations

Build on top of the existing repository structure unless a small refactor clearly improves clarity.

Important existing root-level files may include:
- `models.py`
- `client.py`
- `openenv.yaml`
- `README.md`
- `pyproject.toml`
- `server/`

Prefer extending the current structure rather than scattering logic across many new top-level files.

---

## Target Architecture

The preferred structure is:

- `models.py`
  - typed request/response/state models
- `server/environment.py`
  - main environment loop
- `server/state.py`
  - internal state representation
- `server/task_registry.py`
  - task loading and selection
- `server/tasks/`
  - one module per task
- `server/graders/`
  - grader interfaces and scoring logic
- `server/execution/runner.py`
  - controlled Python execution harness
- `inference.py`
  - baseline model loop

Keep execution separate from grading.

### Execution Layer
Responsible for:
- running generated Python,
- capturing stdout/stderr,
- handling timeout,
- returning structured execution results.

### Grading Layer
Responsible for:
- correctness scoring,
- hidden/visible test aggregation,
- maintainability scoring,
- penalties,
- normalized final score.

---

## Inference Compatibility Rules

The repo must be designed so `inference.py` can follow the sample execution pattern:

- create an OpenAI client using `API_BASE_URL` and `HF_TOKEN`/`API_KEY`,
- create the environment from a Docker image when appropriate,
- call `await env.reset()`,
- call `await env.step(...)` in a loop,
- call `await env.close()` in a `finally` block,
- emit one `[START]` line, one `[STEP]` line per step, and one `[END]` line even on exception. :contentReference[oaicite:3]{index=3}

Do not invent a different inference control flow unless strictly necessary.

---

## Preferred Action Flow

The environment should support an iterative workflow such as:

- inspect source/task context,
- write or patch Python,
- run visible tests,
- inspect results,
- submit final answer.

Do not force all evaluation into one single binary action if a multi-step flow is clearer.

---

## Implementation Order

Implement in this order:

1. stabilize typed models and contracts,
2. implement environment skeleton with `reset()`, `step()`, `state()`,
3. implement Python runner contract,
4. make one easy task work end-to-end,
5. generalize task and grader interfaces,
6. add medium and hard tasks,
7. refine reward shaping,
8. implement `inference.py`,
9. finalize packaging, validator readiness, and documentation.

Do not optimize polish before the shared skeleton works.

---