# HACKATHON_REQUIREMENTS.md

## Mandatory Goal

Build a complete real-world OpenEnv environment that an AI agent can learn from through the standard:
- `step()`
- `reset()`
- `state()`

API.

This environment must simulate a real-world task, not a toy problem or game.

## Current Status

- The environment now implements:
  - `reset()`
  - `step()`
  - `state()`
- The current task set includes 3 graded tasks:
- The current task set includes 5 graded tasks:
  - `array_length`
  - `automatic_abbreviations`
  - `levenshtein_distance`
  - `word_frequency`
  - `align_columns`
- Deterministic grading, controlled execution, and a minimal reward adapter are implemented.
- A root-level `inference.py` exists and currently runs all curated tasks in sequence by default.
- A root-level `Dockerfile` exists for deployment.
- Local execution artifacts are written under `run_logs/`.

---

## Required Functional Features

### 1. Real-World Task Simulation
The environment must model a task humans actually do.

For this repo, the chosen domain is:
- legacy COBOL-to-Python modernization / migration.

### 2. OpenEnv Spec Compliance
The environment must implement:
- typed Observation model,
- typed Action model,
- typed Reward model,
- `step(action)` returning observation, reward, done, info,
- `reset()` returning an initial observation,
- `state()` returning current state,
- `openenv.yaml` metadata.

### 3. Minimum 3 Tasks
The environment must include at least 3 tasks:
- easy,
- medium,
- hard.

Each task must have a programmatic grader.

### 4. Deterministic Graders
Graders must:
- produce reproducible scores,
- return values in the range `0.0` to `1.0`,
- have clear success/failure criteria,
- not always return the same result.

### 5. Meaningful Reward Function
The reward function must:
- provide signal across the trajectory,
- reward partial progress,
- penalize clearly undesirable behavior,
- avoid purely sparse end-of-episode scoring.

### 6. Baseline Inference Script
A root-level file named exactly:
- `inference.py`

must exist.

It must:
- use the OpenAI client for LLM calls,
- read settings from environment variables,
- produce reproducible baseline scores across all tasks,

---

## Required Environment Variables

The sample script expects these variables:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

The sample code also supports:
- `API_KEY` as a fallback auth variable,
- `IMAGE_NAME` for Docker-image-based environment startup,
- task/benchmark-specific variables such as task name and benchmark name

Note:
- in evaluator/submission runs, prefer the injected `API_BASE_URL` and `API_KEY` exactly as provided so requests are observed on the expected proxy path.

Important note:
- the prose header mentions `LOCAL_IMAGE_NAME`,
- the actual sample code reads `IMAGE_NAME`.

For implementation, prefer supporting the variable actually used by code. If desired, support both names for compatibility, but do not document only `LOCAL_IMAGE_NAME` and ignore `IMAGE_NAME`. 

Do not hardcode secrets.

---

## Required Inference Control Flow

The sample script establishes a concrete pattern the repo should support:

1. build an `OpenAI` client with `base_url=API_BASE_URL` and `api_key=HF_TOKEN/API_KEY`,
2. create the environment instance,
3. call `await env.reset()`,
4. repeatedly call `await env.step(...)`,
5. collect rewards,
6. call `await env.close()` in `finally`,
7. always emit `[END]` output even if exceptions occur. 

Your environment and inference script should align with this pattern.

---

## STDOUT Logging Requirements

The inference script must emit exactly these line types to stdout:

- `[START] task=<task_name> env=<benchmark> model=<model_name>`
- `[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>`
- `[END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>`

Rules from the sample:
- one `[START]` line at episode begin,
- one `[STEP]` line immediately after each `env.step()` return,
- one `[END]` line after `env.close()`, always emitted,
- reward values formatted to 2 decimal places,
- `done` and `success` as lowercase booleans,
- `error` must be raw last-action error text or `null`,
- all fields on a single line,
- each task score must be in `[0, 1]`. 

Do not change this format.

---

## Runtime / Infra Constraints

The submitted environment and inference flow must remain lightweight and reproducible.

The broader hackathon constraints still apply, including limited runtime and modest machine resources. Keep the environment simple enough to run comfortably under those limits. 

---

## Deployment Requirements

The submission must include:

- a working Dockerfile,
- containerized execution,
- deployability to Hugging Face Spaces,
- environment responds correctly after deployment.

The repo should be structured so:
- `docker build` works,
- `docker run` works,
- the service starts cleanly,
- OpenEnv validation can pass. 

If the environment is started from a Docker image in inference, make sure the image variable naming is consistent with the actual implementation.

---

## Documentation Requirements

The README must include:

- environment description,
- motivation / real-world utility,
- action space definition,
- observation space definition,
- task descriptions,
- difficulty progression,
- setup instructions,
- usage instructions,

The README should also mention the required inference variables and the strict stdout logging format so users do not accidentally break evaluator parsing.

---

## Validator / Submission Expectations

Before submission, the repo should pass these checks:

1. HF Space deploys
2. service responds successfully
3. OpenEnv metadata and API are valid
4. Dockerfile builds
5. `inference.py` runs without error
6. all required tasks exist
7. graders produce normalized scores
8. baseline is reproducible.

The inference script must also be evaluator-compatible in env vars, control flow, and stdout formatting. 

---

## Disqualification Risks

Avoid the following failure cases:

- environment does not deploy,
- environment does not respond,
- missing or broken Dockerfile,
- missing root-level `inference.py`,
- no baseline inference behavior,
- fewer than 3 tasks,
- grader always returns the same score,
- trivial or plagiarized environment,
- incompatible logging/output format,
- missing spec compliance. 

---

## Scoring Priorities

The repo should optimize for:

1. real-world utility,
2. task and grader quality,
3. clean environment design,
4. code quality and spec compliance,
5. creativity and novelty
6. 
That means:
- correctness and evaluation quality matter more than flashy extras,
- exact compatibility with evaluator expectations matters more than custom logging or custom inference flow,
- real-world usefulness matters more than overengineering,
- determinism matters more than clever but fragile ideas. 
