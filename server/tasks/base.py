# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Base task types and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

try:
    from ...models import TaskExample, TaskSpec
except ImportError:
    from models import TaskExample, TaskSpec


@dataclass(frozen=True)
class RosettaTaskPair:
    """Paired COBOL/Python entry from the Rosetta dataset."""

    task_name: str
    task_description: str
    cobol_code: str
    python_code: str


@dataclass(frozen=True)
class TaskCase:
    """Deterministic test case for a migration task."""

    name: str
    args: Sequence[Any]
    expected: Any
    kwargs: Dict[str, Any] | None = None
    hidden: bool = False

    def as_example(self) -> TaskExample:
        """Convert a visible case into an observation preview."""

        return TaskExample(
            name=self.name,
            input_summary=repr({"args": list(self.args), "kwargs": self.kwargs or {}}),
            expected_summary=repr(self.expected),
        )


def canonicalize_result(value: Any) -> Any:
    """Normalize nested outputs for deterministic task-aware comparisons."""

    if isinstance(value, tuple):
        return [canonicalize_result(item) for item in value]
    if isinstance(value, list):
        return [canonicalize_result(item) for item in value]
    if isinstance(value, dict):
        return {key: canonicalize_result(item) for key, item in value.items()}
    return value


def default_result_comparator(actual: Any, expected: Any) -> bool:
    """Default comparator for task outputs."""

    return canonicalize_result(actual) == canonicalize_result(expected)


def format_result_summary(value: Any) -> str:
    """Render a normalized output summary for logs and grader feedback."""

    return repr(canonicalize_result(value))


@dataclass(frozen=True)
class TaskDefinition:
    """Complete internal definition for one environment task."""

    spec: TaskSpec
    module_name: str
    initial_stub: str
    visible_cases: List[TaskCase]
    hidden_cases: List[TaskCase]
    allowed_imports: List[str]
    comparator: Callable[[Any, Any], bool] = field(default=default_result_comparator)

    @property
    def all_cases(self) -> List[TaskCase]:
        """All test cases in execution order."""

        return [*self.visible_cases, *self.hidden_cases]


def dataset_path() -> Path:
    """Return the expected dataset path from the repository root."""

    return Path(__file__).resolve().parents[2] / "rosetta-code-task-comparisons.json"
