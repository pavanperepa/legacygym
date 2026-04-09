import asyncio
import os

from openenv.core.client_types import StepResult

from inference import (
    CURATED_TASK_IDS,
    create_run_log_session_dir,
    format_end_line,
    format_start_line,
    format_step_line,
    load_dotenv,
    resolve_api_credentials,
    resolve_task_ids,
    run_tasks,
    run_episode,
)
from legacygym import LegacygymAction
from legacygym.server.environment import LegacygymEnvironment


class StaticAgent:
    def generate_initial_solution(self, observation):
        if observation.task.task_id == "array_length":
            return """def array_length(items: list[str]) -> int:\n    \"\"\"Return the number of items.\"\"\"\n    return len(items)\n"""
        if observation.task.task_id == "tokenize_with_escaping":
            return """def tokenize_with_escaping(text: str, separator: str, escape: str) -> list[str]:\n    \"\"\"Split on non-escaped separators.\"\"\"\n    tokens: list[str] = []\n    current: list[str] = []\n    i = 0\n    while i < len(text):\n        char = text[i]\n        if char == escape:\n            if i + 1 < len(text):\n                current.append(text[i + 1])\n                i += 2\n                continue\n            current.append(char)\n            i += 1\n            continue\n        if char == separator:\n            tokens.append(\"\".join(current))\n            current = []\n            i += 1\n            continue\n        current.append(char)\n        i += 1\n    tokens.append(\"\".join(current))\n    return tokens\n"""
        return """from collections import Counter\nimport re\n\n_WORD_RE = re.compile(r\"[A-Za-z]+\")\n\n\ndef word_frequency(text: str, n: int) -> list[tuple[str, int]]:\n    \"\"\"Return the top-n lowercase word counts.\"\"\"\n    counts = Counter(_WORD_RE.findall(text.lower()))\n    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]\n"""

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


def test_resolve_api_credentials_prefers_hf_token_for_non_openai_base_url(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://router.huggingface.co/v1")
    monkeypatch.setenv("HF_TOKEN", "hf-token")
    monkeypatch.setenv("API_KEY", "openai-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    base_url, api_key = resolve_api_credentials()

    assert base_url == "https://router.huggingface.co/v1"
    assert api_key == "hf-token"


def test_resolve_task_ids_defaults_to_all(monkeypatch):
    monkeypatch.delenv("TASK_NAME", raising=False)
    assert resolve_task_ids() == CURATED_TASK_IDS


def test_create_run_log_session_dir_uses_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_LOG_DIR", str(tmp_path))
    session_dir = create_run_log_session_dir()
    assert session_dir is not None
    assert session_dir.parent == tmp_path
    assert session_dir.exists()


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
    assert len([line for line in captured if line.startswith("[START]")]) == 3
    assert len([line for line in captured if line.startswith("[END]")]) == 3
    assert len(results) == 3
    assert (tmp_path / "aggregate_summary.json").exists()
    for task_id in CURATED_TASK_IDS:
        task_dir = tmp_path / task_id
        assert (task_dir / "summary.json").exists()
        assert (task_dir / "steps.json").exists()
        assert (task_dir / "final_candidate.py").exists()
