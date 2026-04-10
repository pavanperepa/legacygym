import asyncio
import os

from openenv.core.client_types import StepResult

from inference import (
    CURATED_TASK_IDS,
    _resolve_async_result,
    _extract_server_metadata,
    create_model_agent,
    create_run_log_session_dir,
    format_end_line,
    format_start_line,
    format_step_line,
    load_dotenv,
    resolve_api_credentials,
    resolve_task_ids,
    run_tasks,
    run_episode,
    validate_server_task_ids,
)
from legacygym import LegacygymAction
from legacygym.server.environment import LegacygymEnvironment


class StaticAgent:
    def generate_initial_solution(self, observation):
        if observation.task.task_id == "array_length":
            return """def array_length(items: list[str]) -> int:\n    \"\"\"Return the number of items.\"\"\"\n    return len(items)\n"""
        if observation.task.task_id == "automatic_abbreviations":
            return """def automatic_abbreviations(text: str, expected_count: int) -> dict[str, object]:\n    \"\"\"Return the shortest unique abbreviations or a structured validation error.\"\"\"\n    words = text.split()\n    if len(words) != expected_count:\n        return {\"status\": \"error\", \"reason\": \"expected_count_mismatch\"}\n    if len(set(words)) != len(words):\n        return {\"status\": \"error\", \"reason\": \"identical_entries\"}\n    longest = max((len(word) for word in words), default=0)\n    for length in range(1, longest + 1):\n        abbreviations = [word[:length] for word in words]\n        if len(set(abbreviations)) == len(words):\n            return {\"status\": \"ok\", \"length\": length, \"abbreviations\": abbreviations}\n    return {\"status\": \"error\", \"reason\": \"identical_entries\"}\n"""
        if observation.task.task_id == "levenshtein_distance":
            return """def levenshtein_distance(left: str, right: str) -> int:\n    \"\"\"Return the Levenshtein edit distance between two strings.\"\"\"\n    if not left:\n        return len(right)\n    if not right:\n        return len(left)\n    previous = list(range(len(right) + 1))\n    for i, left_char in enumerate(left, start=1):\n        current = [i]\n        for j, right_char in enumerate(right, start=1):\n            current.append(min(\n                current[j - 1] + 1,\n                previous[j] + 1,\n                previous[j - 1] + (left_char != right_char),\n            ))\n        previous = current\n    return previous[-1]\n"""
        if observation.task.task_id == "word_frequency":
            return """from collections import Counter\nimport re\n\n_WORD_RE = re.compile(r\"[A-Za-z]+\")\n\n\ndef word_frequency(text: str, n: int) -> list[tuple[str, int]]:\n    \"\"\"Return the top-n lowercase word counts.\"\"\"\n    counts = Counter(_WORD_RE.findall(text.lower()))\n    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]\n"""
        return """from itertools import zip_longest\n\n\ndef _justify(value: str, width: int, alignment: str) -> str:\n    if alignment == \"left\":\n        return value.ljust(width)\n    if alignment == \"right\":\n        return value.rjust(width)\n    if alignment == \"center\":\n        return value.center(width)\n    raise ValueError(f\"Unsupported alignment: {alignment}\")\n\n\ndef align_columns(lines: list[str], alignment: str) -> list[str]:\n    \"\"\"Align dollar-delimited columns across all input rows.\"\"\"\n    rows = [line.rstrip(\"$\").split(\"$\") for line in lines]\n    widths = [max(len(cell) for cell in column) for column in zip_longest(*rows, fillvalue=\"\")]\n    return [\n        \" \".join(_justify(cell, widths[index], alignment) for index, cell in enumerate(row)).rstrip()\n        for row in rows\n    ]\n"""

    def repair_solution(self, observation):
        return observation.current_code


class AsyncEnvironmentAdapter:
    def __init__(self, env):
        self.env = env

    async def reset(self, **kwargs):
        observation = self.env.reset(**kwargs)
        return StepResult(observation=observation, reward=observation.reward, done=observation.done)

    async def step(self, action: LegacygymAction):
        observation = self.env.step(action)
        return StepResult(observation=observation, reward=observation.reward, done=observation.done)

    async def close(self):
        return None


class NestedAwaitableEnvironmentAdapter(AsyncEnvironmentAdapter):
    async def reset(self, **kwargs):
        async def inner():
            return await super(NestedAwaitableEnvironmentAdapter, self).reset(**kwargs)

        return inner()

    async def step(self, action: LegacygymAction):
        async def inner():
            return await super(NestedAwaitableEnvironmentAdapter, self).step(action)

        return inner()

    async def close(self):
        async def inner():
            return None

        return inner()


class FailingEnvironmentAdapter:
    async def reset(self, **kwargs):
        del kwargs
        raise RuntimeError("reset failed")

    async def step(self, action: LegacygymAction):
        del action
        raise RuntimeError("step should not be called")

    async def close(self):
        return None


def test_logging_helpers_are_single_line():
    assert format_start_line("array_length", "legacygym", "model").count("\n") == 0
    assert format_step_line(1, "submit", 0.5, False, "boom").count("\n") == 0
    assert format_end_line(True, 3, 0.75, [0.1, 0.2]).count("\n") == 0


def test_load_dotenv_populates_missing_values(tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "# comment\nAPI_BASE_URL=https://example.test/v1\nMODEL_NAME=\"demo-model\"\nHF_TOKEN=secret\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("API_BASE_URL", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    load_dotenv(dotenv_path)

    assert os.environ["API_BASE_URL"] == "https://example.test/v1"
    assert os.environ["MODEL_NAME"] == "demo-model"
    assert os.environ["HF_TOKEN"] == "secret"


def test_resolve_api_credentials_prefers_openai_key_for_openai_base_url(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("HF_TOKEN", "hf-token")
    monkeypatch.setenv("API_KEY", "openai-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    base_url, api_key = resolve_api_credentials()

    assert base_url == "https://api.openai.com/v1"
    assert api_key == "openai-key"


def test_resolve_api_credentials_prefers_api_key_for_configured_proxy(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://router.huggingface.co/v1")
    monkeypatch.setenv("HF_TOKEN", "hf-token")
    monkeypatch.setenv("API_KEY", "openai-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    base_url, api_key = resolve_api_credentials()

    assert base_url == "https://router.huggingface.co/v1"
    assert api_key == "openai-key"


def test_create_model_agent_prefers_exact_submission_env_pair(monkeypatch):
    captured: dict[str, str | None] = {}

    class FakeOpenAI:
        def __init__(self, *, base_url=None, api_key=None):
            captured["base_url"] = base_url
            captured["api_key"] = api_key

    monkeypatch.setenv("API_BASE_URL", "https://proxy.example/v1")
    monkeypatch.setenv("API_KEY", "proxy-key")
    monkeypatch.setenv("HF_TOKEN", "hf-token")
    monkeypatch.setattr("inference.OpenAI", FakeOpenAI)

    create_model_agent()

    assert captured["base_url"] == "https://proxy.example/v1"
    assert captured["api_key"] == "proxy-key"


def test_resolve_api_credentials_falls_back_to_hf_token_when_api_key_missing(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://router.huggingface.co/v1")
    monkeypatch.setenv("HF_TOKEN", "hf-token")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    base_url, api_key = resolve_api_credentials()

    assert base_url == "https://router.huggingface.co/v1"
    assert api_key == "hf-token"


def test_resolve_task_ids_defaults_to_all(monkeypatch):
    monkeypatch.delenv("TASK_NAME", raising=False)
    assert resolve_task_ids() == CURATED_TASK_IDS


def test_validate_server_task_ids_detects_missing_tasks():
    missing = validate_server_task_ids(
        expected_task_ids=["array_length", "align_columns"],
        available_task_ids=["array_length"],
    )

    assert missing == ["align_columns"]


def test_extract_server_metadata_prefers_transport_safe_field():
    env = LegacygymEnvironment()
    observation = env.reset(task_id="array_length")

    metadata = _extract_server_metadata(observation)

    assert metadata["environment_version"] == "baseline-v1"
    assert "array_length" in metadata["available_task_ids"]


def test_create_run_log_session_dir_uses_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_LOG_DIR", str(tmp_path))
    session_dir = create_run_log_session_dir()
    assert session_dir is not None
    assert session_dir.parent == tmp_path
    assert session_dir.exists()


def test_resolve_async_result_unwraps_nested_awaitables():
    async def inner():
        return 7

    async def outer():
        return inner()

    assert asyncio.run(_resolve_async_result(outer())) == 7


def test_run_episode_emits_required_log_lines(capsys):
    env = AsyncEnvironmentAdapter(LegacygymEnvironment())
    agent = StaticAgent()

    success, steps, score, rewards = asyncio.run(
        run_episode(
            env,
            agent,
            task_id="array_length",
            benchmark_name="legacygym",
            model_name="test-model",
        )
    )

    captured = capsys.readouterr().out.strip().splitlines()
    assert captured[0].startswith("[START]")
    assert any(line.startswith("[STEP]") for line in captured)
    assert captured[-1].startswith("[END]")
    assert success
    assert steps == len(rewards)
    assert score > 0.9


def test_run_episode_handles_nested_awaitables(capsys):
    env = NestedAwaitableEnvironmentAdapter(LegacygymEnvironment())
    agent = StaticAgent()

    success, steps, score, rewards = asyncio.run(
        run_episode(
            env,
            agent,
            task_id="array_length",
            benchmark_name="legacygym",
            model_name="test-model",
        )
    )

    captured = capsys.readouterr().out.strip().splitlines()
    assert captured[0].startswith("[START]")
    assert captured[-1].startswith("[END]")
    assert success
    assert steps == len(rewards)
    assert score > 0.9


def test_run_episode_returns_failure_instead_of_raising(capsys, tmp_path):
    env = FailingEnvironmentAdapter()
    agent = StaticAgent()

    success, steps, score, rewards = asyncio.run(
        run_episode(
            env,
            agent,
            task_id="array_length",
            benchmark_name="legacygym",
            model_name="test-model",
            run_log_dir=tmp_path,
        )
    )

    captured = capsys.readouterr().out.strip().splitlines()
    assert captured[0].startswith("[START]")
    assert captured[-1].startswith("[END]")
    assert not success
    assert steps == 0
    assert score == 0.0
    assert rewards == []
    assert (tmp_path / "array_length" / "summary.json").exists()


def test_run_tasks_writes_run_logs(tmp_path, capsys):
    env = AsyncEnvironmentAdapter(LegacygymEnvironment())
    agent = StaticAgent()

    results = asyncio.run(
        run_tasks(
            env,
            agent,
            task_ids=CURATED_TASK_IDS,
            benchmark_name="legacygym",
            model_name="test-model",
            run_log_dir=tmp_path,
        )
    )

    captured = capsys.readouterr().out.strip().splitlines()
    assert len([line for line in captured if line.startswith("[START]")]) == len(CURATED_TASK_IDS)
    assert len([line for line in captured if line.startswith("[END]")]) == len(CURATED_TASK_IDS)
    assert len(results) == len(CURATED_TASK_IDS)
    assert (tmp_path / "aggregate_summary.json").exists()
    assert (tmp_path / "server_preflight.json").exists()
    for task_id in CURATED_TASK_IDS:
        task_dir = tmp_path / task_id
        assert (task_dir / "summary.json").exists()
        assert (task_dir / "steps.json").exists()
        assert (task_dir / "final_candidate.py").exists()
        assert (task_dir / "server_metadata.json").exists()


class MissingTaskEnvironmentAdapter:
    async def reset(self, **kwargs):
        task_id = kwargs.get("task_id", "array_length")
        if task_id not in {"array_length", "automatic_abbreviations", "levenshtein_distance", "word_frequency", "align_columns"}:
            raise RuntimeError(f"unknown task: {task_id}")
        observation = LegacygymEnvironment().reset(task_id="array_length")
        observation.server_info = {
            "environment_name": "legacygym",
            "environment_version": "baseline-v1",
            "registry_signature": "test-signature",
            "available_task_ids": ["array_length"],
            "reward_weights": {},
            "score_weights": {},
            "runner_timeout_s": 2.0,
        }
        return StepResult(observation=observation, reward=observation.reward, done=observation.done)

    async def step(self, action: LegacygymAction):
        del action
        raise RuntimeError("step should not be called")

    async def close(self):
        return None


def test_run_tasks_emits_structured_lines_on_preflight_failure(tmp_path, capsys):
    env = MissingTaskEnvironmentAdapter()
    agent = StaticAgent()

    results = asyncio.run(
        run_tasks(
            env,
            agent,
            task_ids=CURATED_TASK_IDS,
            benchmark_name="legacygym",
            model_name="test-model",
            run_log_dir=tmp_path,
        )
    )

    captured = capsys.readouterr().out.strip().splitlines()
    assert len([line for line in captured if line.startswith("[START]")]) == len(CURATED_TASK_IDS)
    assert len([line for line in captured if line.startswith("[END]")]) == len(CURATED_TASK_IDS)
    assert len(results) == len(CURATED_TASK_IDS)


class PreflightErrorEnvironmentAdapter(AsyncEnvironmentAdapter):
    def __init__(self, env):
        super().__init__(env)
        self._reset_calls = 0

    async def reset(self, **kwargs):
        self._reset_calls += 1
        if self._reset_calls == 1 and "task_id" not in kwargs:
            raise RuntimeError("preflight unavailable")
        return await super().reset(**kwargs)


def test_run_tasks_continues_when_preflight_probe_fails(tmp_path, capsys):
    env = PreflightErrorEnvironmentAdapter(LegacygymEnvironment())
    agent = StaticAgent()

    results = asyncio.run(
        run_tasks(
            env,
            agent,
            task_ids=["array_length"],
            benchmark_name="legacygym",
            model_name="test-model",
            run_log_dir=tmp_path,
        )
    )

    captured = capsys.readouterr().out.strip().splitlines()
    assert captured[0].startswith("[START]")
    assert any(line.startswith("[STEP]") for line in captured)
    assert captured[-1].startswith("[END]")
    assert results[0]["task_id"] == "array_length"
