"""Baseline inference loop for the Legacygym modernization environment."""

from __future__ import annotations

import asyncio
from datetime import datetime
import inspect
import json
import os
from pathlib import Path
import re
from typing import Protocol

from openai import OpenAI

from legacygym import LegacygymAction, LegacygymEnv, LegacygymObservation

CURATED_TASK_IDS = [
    "array_length",
    "automatic_abbreviations",
    "levenshtein_distance",
    "word_frequency",
    "align_columns",
]


class ModelAgent(Protocol):
    """Small interface for the baseline code generator."""

    def generate_initial_solution(self, observation: LegacygymObservation) -> str:
        ...

    def repair_solution(self, observation: LegacygymObservation) -> str:
        ...


def _is_openai_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    normalized = base_url.strip().lower()
    return "api.openai.com" in normalized or normalized.endswith("/openai/v1")


def load_dotenv(path: str | os.PathLike[str] = ".env", *, override: bool = False) -> None:
    """Load simple KEY=VALUE pairs from a local .env file."""

    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if override or key not in os.environ:
            os.environ[key] = value


def _sanitize_log_value(value: str | None) -> str:
    if not value:
        return "null"
    return value.replace("\r", "\\r").replace("\n", "\\n")


def format_start_line(task_name: str, benchmark: str, model_name: str) -> str:
    return f"[START] task={task_name} env={benchmark} model={model_name}"


def format_step_line(step: int, action: str, reward: float, done: bool, error: str | None) -> str:
    return (
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={str(done).lower()} error={_sanitize_log_value(error)}"
    )


def format_end_line(success: bool, steps: int, score: float, rewards: list[float]) -> str:
    reward_blob = ",".join(f"{reward:.2f}" for reward in rewards)
    return (
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.4f} rewards={reward_blob}"
    )


def emit_structured_line(line: str) -> None:
    """Print a structured validator-facing line and flush immediately."""

    print(line, flush=True)


def _strip_code_fences(text: str) -> str:
    fenced = re.findall(r"```(?:python)?\n(.*?)```", text, flags=re.DOTALL)
    if fenced:
        return fenced[0].strip()
    return text.strip()


def resolve_api_credentials() -> tuple[str | None, str]:
    """Pick the correct auth token for the configured provider."""

    base_url = os.getenv("API_BASE_URL")
    hf_token = os.getenv("HF_TOKEN")
    api_key = os.getenv("API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if base_url and api_key:
        return base_url, api_key

    if _is_openai_base_url(base_url):
        selected = openai_api_key or api_key
        if selected:
            return base_url, selected
        if hf_token:
            raise RuntimeError(
                "API_BASE_URL points to OpenAI, but only HF_TOKEN is set. "
                "Set API_KEY or OPENAI_API_KEY for direct OpenAI usage."
            )
        raise RuntimeError(
            "API_KEY or OPENAI_API_KEY is required when API_BASE_URL points to OpenAI."
        )

    selected = hf_token or openai_api_key or api_key
    if selected:
        return base_url, selected
    raise RuntimeError(
        "Missing model auth. Set HF_TOKEN for submission-style/HF-compatible endpoints, "
        "or API_KEY/OPENAI_API_KEY for direct OpenAI usage."
    )


def _render_task_prompt(observation: LegacygymObservation) -> str:
    examples = "\n".join(
        f"- {example.name}: input={example.input_summary} expected={example.expected_summary}"
        for example in observation.task.visible_examples
    )
    return (
        f"Task: {observation.task.task_name}\n"
        f"Difficulty: {observation.task.difficulty}\n"
        f"Summary: {observation.task.summary}\n"
        f"Function signature: {observation.task.python_function_signature}\n"
        f"Visible examples:\n{examples}\n\n"
        f"COBOL source:\n{observation.task.cobol_source}\n"
    )


def _render_feedback(observation: LegacygymObservation) -> str:
    feedback = []
    if observation.last_execution and observation.last_execution.error:
        feedback.append(f"Execution error: {observation.last_execution.error}")
    if observation.last_grading and observation.last_grading.feedback:
        feedback.extend(f"Grader feedback: {item}" for item in observation.last_grading.feedback)
    if observation.last_grading:
        feedback.append(
            "Visible progress: "
            f"{observation.last_grading.visible_passed}/{observation.last_grading.visible_total}"
        )
    return "\n".join(feedback) or "No feedback yet."


class OpenAIModelAgent:
    """Deterministic prompting wrapper over the OpenAI client."""

    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name
        self.interactions: list[dict[str, str]] = []

    def _complete(self, prompt: str, *, kind: str, task_id: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are migrating legacy COBOL logic into a single Python function. "
                        "Return only valid Python source code with no markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        completion = _strip_code_fences(response.choices[0].message.content or "")
        self.interactions.append(
            {
                "kind": kind,
                "task_id": task_id,
                "prompt": prompt,
                "response": completion,
            }
        )
        return completion

    def generate_initial_solution(self, observation: LegacygymObservation) -> str:
        prompt = (
            _render_task_prompt(observation)
            + "\nWrite the full Python module now. Define exactly the requested function."
        )
        return self._complete(prompt, kind="initial", task_id=observation.task.task_id)

    def repair_solution(self, observation: LegacygymObservation) -> str:
        prompt = (
            _render_task_prompt(observation)
            + "\nCurrent candidate:\n"
            + observation.current_code
            + "\n\nRepair the module based on this feedback:\n"
            + _render_feedback(observation)
            + "\nReturn the full corrected Python module."
        )
        return self._complete(prompt, kind="repair", task_id=observation.task.task_id)


def create_model_agent() -> OpenAIModelAgent:
    base_url, api_key = resolve_api_credentials()
    client = OpenAI(base_url=base_url, api_key=api_key)
    return OpenAIModelAgent(client=client, model_name=os.getenv("MODEL_NAME", "unknown-model"))


def create_environment() -> LegacygymEnv:
    env_base_url = os.getenv("ENV_BASE_URL")
    if env_base_url:
        return LegacygymEnv(base_url=env_base_url)
    image_name = os.getenv("IMAGE_NAME")
    if image_name:
        return LegacygymEnv.from_docker_image(image_name)
    return LegacygymEnv(base_url="http://127.0.0.1:8000")


def resolve_task_ids() -> list[str]:
    """Resolve which curated tasks to run for the current invocation."""

    raw_value = os.getenv("TASK_NAME", "all").strip()
    if not raw_value or raw_value.lower() in {"all", "*"}:
        return list(CURATED_TASK_IDS)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def create_run_log_session_dir() -> Path | None:
    """Create a timestamped local run-log directory unless disabled."""

    raw_dir = os.getenv("RUN_LOG_DIR", "run_logs").strip()
    if not raw_dir:
        return None
    session_dir = Path(raw_dir) / datetime.now().strftime("run_%Y%m%d_%H%M%S")
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


async def _resolve_async_result(value: object, *, max_depth: int = 5) -> object:
    """Unwrap awaitables returned by runtime/client layers."""

    depth = 0
    result = value
    while inspect.isawaitable(result):
        result = await result
        depth += 1
        if depth > max_depth:
            raise RuntimeError("Exceeded maximum awaitable resolution depth")
    return result


def _collect_agent_interactions(agent: ModelAgent, task_id: str) -> list[dict[str, str]]:
    interactions = getattr(agent, "interactions", [])
    return [item for item in interactions if item.get("task_id") == task_id]


def _extract_server_metadata(observation: LegacygymObservation) -> dict[str, object]:
    """Return stable server metadata from an observation."""

    metadata = dict(observation.server_info or observation.metadata)
    return {
        "environment_name": metadata.get("environment_name", "legacygym"),
        "environment_version": metadata.get("environment_version"),
        "registry_signature": metadata.get("registry_signature"),
        "available_task_ids": metadata.get("available_task_ids", []),
        "reward_weights": metadata.get("reward_weights", {}),
        "score_weights": metadata.get("score_weights", {}),
        "runner_timeout_s": metadata.get("runner_timeout_s"),
    }


async def probe_server_metadata(env: LegacygymEnv) -> dict[str, object]:
    """Fetch server metadata before starting task episodes."""

    reset_result = await _resolve_async_result(env.reset())
    return _extract_server_metadata(reset_result.observation)


def validate_server_task_ids(
    *,
    expected_task_ids: list[str],
    available_task_ids: list[str],
) -> list[str]:
    """Return the curated tasks that the connected server does not expose."""

    available = set(available_task_ids)
    return [task_id for task_id in expected_task_ids if task_id not in available]


def write_task_run_logs(
    session_dir: Path | None,
    *,
    task_id: str,
    benchmark_name: str,
    model_name: str,
    success: bool,
    steps: int,
    score: float,
    rewards: list[float],
    initial_observation: LegacygymObservation,
    final_observation: LegacygymObservation,
    step_records: list[dict[str, object]],
    agent: ModelAgent,
    server_metadata: dict[str, object] | None = None,
) -> None:
    """Persist detailed per-task artifacts for local inspection."""

    if session_dir is None:
        return

    task_dir = session_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        task_dir / "summary.json",
        {
            "task_id": task_id,
            "benchmark_name": benchmark_name,
            "model_name": model_name,
            "success": success,
            "steps": steps,
            "score": score,
            "rewards": rewards,
            "server_metadata": server_metadata or {},
        },
    )
    _write_json(task_dir / "server_metadata.json", server_metadata or {})
    _write_json(task_dir / "initial_observation.json", initial_observation.model_dump(mode="json"))
    _write_json(task_dir / "final_observation.json", final_observation.model_dump(mode="json"))
    _write_json(task_dir / "steps.json", step_records)
    _write_json(task_dir / "agent_interactions.json", _collect_agent_interactions(agent, task_id))
    (task_dir / "final_candidate.py").write_text(final_observation.current_code, encoding="utf-8")


async def run_episode(
    env: LegacygymEnv,
    agent: ModelAgent,
    *,
    task_id: str,
    benchmark_name: str,
    model_name: str,
    run_log_dir: Path | None = None,
) -> tuple[bool, int, float, list[float]]:
    emit_structured_line(format_start_line(task_id, benchmark_name, model_name))
    rewards: list[float] = []
    step_index = 0
    success = False
    score = 0.0
    step_records: list[dict[str, object]] = []
    initial_observation: LegacygymObservation | None = None
    observation: LegacygymObservation | None = None
    server_metadata: dict[str, object] | None = None

    try:
        reset_result = await _resolve_async_result(env.reset(task_id=task_id))
        observation = reset_result.observation
        initial_observation = observation.model_copy(deep=True)
        server_metadata = _extract_server_metadata(observation)

        actions: list[LegacygymAction] = [
            LegacygymAction(
                action_type="replace_solution",
                code=agent.generate_initial_solution(observation),
            )
        ]

        while actions:
            action = actions.pop(0)
            result = await _resolve_async_result(env.step(action))
            step_index += 1
            observation = result.observation
            reward = float(result.reward or 0.0)
            rewards.append(reward)
            error = observation.attempt.last_error
            step_records.append(
                {
                    "step": step_index,
                    "action_type": action.action_type,
                    "reward": reward,
                    "done": result.done,
                    "error": error,
                    "code": action.code,
                    "observation": observation.model_dump(mode="json"),
                }
            )
            emit_structured_line(
                format_step_line(step_index, action.action_type, reward, result.done, error)
            )

            if result.done:
                score = observation.last_grading.final_score if observation.last_grading else 0.0
                success = bool(score >= 0.99)
                break

            if action.action_type == "replace_solution":
                actions.append(LegacygymAction(action_type="run_visible_tests"))
                continue

            if action.action_type == "run_visible_tests":
                last_grading = observation.last_grading
                runtime_info = observation.server_info or observation.metadata
                remaining_steps = int(runtime_info.get("remaining_steps", 0))
                if last_grading and last_grading.visible_passed == last_grading.visible_total:
                    actions.append(LegacygymAction(action_type="submit"))
                elif remaining_steps > 1:
                    actions.append(
                        LegacygymAction(
                            action_type="replace_solution",
                            code=agent.repair_solution(observation),
                        )
                    )
                else:
                    actions.append(LegacygymAction(action_type="submit"))
    except Exception as exc:
        success = False
        score = 0.0
        step_records.append(
            {
                "step": step_index,
                "action_type": "exception",
                "reward": 0.0,
                "done": True,
                "error": str(exc),
                "code": None,
                "observation": observation.model_dump(mode="json") if observation is not None else None,
            }
        )
    finally:
        emit_structured_line(format_end_line(success, step_index, score, rewards))
        if initial_observation is not None and observation is not None:
            write_task_run_logs(
                run_log_dir,
                task_id=task_id,
                benchmark_name=benchmark_name,
                model_name=model_name,
                success=success,
                steps=step_index,
                score=score,
                rewards=rewards,
                initial_observation=initial_observation,
                final_observation=observation,
                step_records=step_records,
                agent=agent,
                server_metadata=server_metadata,
            )
        elif run_log_dir is not None:
            task_dir = run_log_dir / task_id
            task_dir.mkdir(parents=True, exist_ok=True)
            _write_json(
                task_dir / "summary.json",
                {
                    "task_id": task_id,
                    "benchmark_name": benchmark_name,
                    "model_name": model_name,
                    "success": success,
                    "steps": step_index,
                    "score": score,
                    "rewards": rewards,
                    "error": step_records[-1]["error"] if step_records else "unknown error",
                    "server_metadata": server_metadata or {},
                },
            )
            _write_json(task_dir / "server_metadata.json", server_metadata or {})
            _write_json(task_dir / "steps.json", step_records)
    return success, step_index, score, rewards


async def run_tasks(
    env: LegacygymEnv,
    agent: ModelAgent,
    *,
    task_ids: list[str],
    benchmark_name: str,
    model_name: str,
    run_log_dir: Path | None = None,
) -> list[dict[str, object]]:
    """Run a sequence of tasks and return aggregate results."""

    server_metadata = await probe_server_metadata(env)
    missing_task_ids = validate_server_task_ids(
        expected_task_ids=task_ids,
        available_task_ids=list(server_metadata.get("available_task_ids", [])),
    )

    if run_log_dir is not None:
        _write_json(
            run_log_dir / "server_preflight.json",
            {
                "requested_task_ids": task_ids,
                "server_metadata": server_metadata,
                "missing_task_ids": missing_task_ids,
            },
        )

    results: list[dict[str, object]] = []
    if missing_task_ids:
        error = (
            "Connected server does not expose all requested tasks: "
            + ", ".join(missing_task_ids)
        )
        for task_id in task_ids:
            emit_structured_line(format_start_line(task_id, benchmark_name, model_name))
            emit_structured_line(format_end_line(False, 0, 0.0, []))
        results = [
            {
                "task_id": task_id,
                "success": False,
                "steps": 0,
                "score": 0.0,
                "rewards": [],
                "error": error,
            }
            for task_id in task_ids
        ]
        if run_log_dir is not None:
            _write_json(run_log_dir / "aggregate_summary.json", results)
        return results

    for task_id in task_ids:
        success, steps, score, rewards = await run_episode(
            env,
            agent,
            task_id=task_id,
            benchmark_name=benchmark_name,
            model_name=model_name,
            run_log_dir=run_log_dir,
        )
        results.append(
            {
                "task_id": task_id,
                "success": success,
                "steps": steps,
                "score": score,
                "rewards": rewards,
                "server_metadata": server_metadata,
            }
        )

    if run_log_dir is not None:
        _write_json(run_log_dir / "aggregate_summary.json", results)

    return results


async def main() -> None:
    load_dotenv()
    env = create_environment()
    agent = create_model_agent()
    task_ids = resolve_task_ids()
    benchmark_name = os.getenv("BENCHMARK_NAME", "legacygym")
    model_name = os.getenv("MODEL_NAME", "unknown-model")
    run_log_dir = create_run_log_session_dir()
    try:
        try:
            await run_tasks(
                env,
                agent,
                task_ids=task_ids,
                benchmark_name=benchmark_name,
                model_name=model_name,
                run_log_dir=run_log_dir,
            )
        except Exception as exc:
            for task_id in task_ids:
                emit_structured_line(format_start_line(task_id, benchmark_name, model_name))
                emit_structured_line(format_end_line(False, 0, 0.0, []))
            if run_log_dir is not None:
                _write_json(
                    run_log_dir / "run_error.json",
                    {
                        "benchmark_name": benchmark_name,
                        "model_name": model_name,
                        "task_ids": task_ids,
                        "error": str(exc),
                    },
                )
    finally:
        await _resolve_async_result(env.close())


if __name__ == "__main__":
    asyncio.run(main())
