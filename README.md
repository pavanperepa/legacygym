---
title: Legacygym Modernization Environment
emoji: 🧰
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - modernization
  - cobol
---

# Legacygym Modernization Environment

Legacygym is an OpenEnv-compatible benchmark for iterative COBOL-to-Python modernization. Each episode gives an agent legacy COBOL source, a normalized Python function contract, visible examples, and a small action space for drafting, testing, and submitting code.

The environment is intentionally lightweight and deterministic. It does not execute COBOL. It executes only agent-generated Python inside a controlled runner and scores correctness, maintainability, and safe behavior.

## Tasks

V1 ships three fixed Rosetta-backed tasks with increasing difficulty:

- `array_length` (`easy`): return the number of elements in a list.
- `tokenize_with_escaping` (`medium`): split on unescaped separators while preserving escaped characters.
- `word_frequency` (`hard`): normalize text, count words, and return the top `n` items with deterministic tie-breaking.

The dataset source is [rosetta-code-task-comparisons.json](/c:/Users/pavan/openenv-rl-gym/legacygym/rosetta-code-task-comparisons.json). The paired Python snippets are used only as reference material while authoring tasks and tests; the runtime baseline does not use them as direct answers.

## Action Space

`LegacygymAction` supports exactly three actions:

- `replace_solution`: provide the full candidate Python module in `code`.
- `run_visible_tests`: execute only visible tests for the stored candidate.
- `submit`: run full grading and end the episode.

## Observation Space

`LegacygymObservation` includes:

- `task`: task id, difficulty, migration summary, COBOL source, function signature, and visible examples.
- `attempt`: whether code exists, code size, last action, and last error.
- `current_code`: the currently stored Python module.
- `last_execution`: latest runner result, including status and error.
- `last_grading`: latest grading summary, including visible/hidden counts and normalized scores.
- `reward_breakdown`: minimal pluggable reward terms for the most recent transition.

`state()` returns the same episode context plus internal progress fields such as `step_count`, `best_visible_score`, and `done`.

## Reward And Scoring

Deterministic grading is the primary contract:

- correctness comes from visible and hidden tests,
- maintainability comes from static checks on the target function,
- safety comes from AST preflight and controlled execution outcomes.

The final task score is normalized to `[0, 1]`.

RL reward shaping is intentionally minimal in v1 and isolated behind a reward adapter:

- small negative reward for invalid or unsafe code,
- small positive reward when visible test pass rate improves,
- final reward on termination from the normalized task score.

## Inference Compatibility

The root-level [inference.py](/c:/Users/pavan/openenv-rl-gym/legacygym/inference.py) follows the required evaluator control flow:

1. create an OpenAI client from `API_BASE_URL` and `HF_TOKEN` or `API_KEY`,
2. create the environment from `IMAGE_NAME`, `ENV_BASE_URL`, or a local default URL,
3. call `await env.reset(...)`,
4. call `await env.step(...)` in a loop,
5. call `await env.close()` in `finally`.

Supported environment variables:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`
- `API_KEY`
- `OPENAI_API_KEY`
- `IMAGE_NAME`
- `ENV_BASE_URL`
- `TASK_NAME`
- `BENCHMARK_NAME`
- `RUN_LOG_DIR`

`inference.py` automatically loads a root-level `.env` file before reading these variables.

Auth selection follows the submission requirements without breaking direct OpenAI usage:

- if `API_BASE_URL` points at an OpenAI endpoint, `OPENAI_API_KEY` or `API_KEY` is used
- otherwise, `HF_TOKEN` is preferred and `API_KEY` is the fallback

That keeps evaluator compatibility for Hugging Face-style submission flows while avoiding accidental use of an `hf_...` token against `https://api.openai.com/v1`.

The script emits strict evaluator-compatible stdout:

```text
[START] task=<task_name> env=<benchmark> model=<model_name>
[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
```

By default, `inference.py` runs all three curated tasks in sequence. To narrow the run, set `TASK_NAME` to one task id or a comma-separated list such as `array_length,word_frequency`.

Detailed local artifacts are written under `run_logs/` by default, with one subdirectory per task plus an `aggregate_summary.json` file. Set `RUN_LOG_DIR` to change the output location, or set it to an empty string to disable file artifacts.

## Running Locally

Install dependencies:

```bash
uv sync
```

Run the server:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

Interact from Python:

```python
import asyncio

from legacygym import LegacygymAction, LegacygymEnv


async def main() -> None:
    env = LegacygymEnv(base_url="http://127.0.0.1:8000")
    try:
        reset = await env.reset(task_id="array_length")
        print(reset.observation.task.task_name)

        result = await env.step(
            LegacygymAction(
                action_type="replace_solution",
                code=\"\"\"def array_length(items: list[str]) -> int:
    \"\"\"Return the number of items.\"\"\"
    return len(items)
\"\"\",
            )
        )
        print(result.observation.attempt.last_error)

        result = await env.step(LegacygymAction(action_type="run_visible_tests"))
        print(result.observation.last_grading.visible_passed)

        result = await env.step(LegacygymAction(action_type="submit"))
        print(result.reward, result.observation.last_grading.final_score)
    finally:
        await env.close()


asyncio.run(main())
```

Run the baseline inference loop:

```bash
@"
API_BASE_URL=https://api.openai.com/v1
MODEL_NAME=your-model
API_KEY=sk-...
TASK_NAME=all
RUN_LOG_DIR=run_logs
# Optional:
# ENV_BASE_URL=http://127.0.0.1:8000
# IMAGE_NAME=legacygym-env:latest
"@ | Set-Content .env

python inference.py
```

For submission-style or HF-compatible routers, use:

```dotenv
API_BASE_URL=https://your-router/v1
MODEL_NAME=your-model
HF_TOKEN=hf_...
TASK_NAME=all
```

## Docker

Build the root-level Docker image:

```bash
docker build -t legacygym-env:latest .
```

Run it:

```bash
docker run --rm -p 8000:8000 legacygym-env:latest
```

## Testing

Run the test suite:

```bash
.venv\Scripts\python.exe -m pytest
```

The tests cover dataset loading, the execution runner, task graders, reward adaptation, environment flow, and inference log formatting.
