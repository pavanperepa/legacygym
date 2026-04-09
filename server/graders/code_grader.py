# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Deterministic task grader for candidate Python solutions."""

from __future__ import annotations

import ast
from typing import Literal

try:
    from ...models import ExecutionResult, GradingResult
    from ..execution.runner import PythonExecutionRunner
    from ..tasks.base import TaskDefinition
    from .base import DEFAULT_SCORE_WEIGHTS, ScoreWeights
except ImportError:
    from models import ExecutionResult, GradingResult
    from server.execution.runner import PythonExecutionRunner
    from server.tasks.base import TaskDefinition
    from server.graders.base import DEFAULT_SCORE_WEIGHTS, ScoreWeights


class DeterministicCodeGrader:
    """Grade candidate code against visible or full task cases."""

    def __init__(
        self,
        runner: PythonExecutionRunner,
        weights: ScoreWeights = DEFAULT_SCORE_WEIGHTS,
    ):
        self.runner = runner
        self.weights = weights

    def grade(
        self,
        task: TaskDefinition,
        source: str,
        mode: Literal["visible", "full"],
    ) -> tuple[ExecutionResult, GradingResult]:
        cases = task.visible_cases if mode == "visible" else task.all_cases
        runner_payload = self.runner.run(
            source=source,
            function_name=task.spec.function_name,
            cases=cases,
            allowed_imports=task.allowed_imports,
        )
        execution = runner_payload.execution
        visible_results = [result for result in runner_payload.test_results if not result.hidden]
        hidden_results = [result for result in runner_payload.test_results if result.hidden]

        visible_total = len(visible_results)
        hidden_total = len(hidden_results)
        visible_passed = sum(result.passed for result in visible_results)
        hidden_passed = sum(result.passed for result in hidden_results)
        correctness_denominator = visible_total + hidden_total
        correctness_score = (
            (visible_passed + hidden_passed) / correctness_denominator
            if correctness_denominator
            else 0.0
        )
        safety_score, safety_feedback = self._score_safety(execution)
        maintainability_score, maintainability_feedback = self._score_maintainability(
            source=source,
            function_name=task.spec.function_name,
        )
        final_score = self._combine_scores(
            correctness=correctness_score,
            maintainability=maintainability_score,
            safety=safety_score,
        )

        feedback = []
        feedback.extend(safety_feedback)
        feedback.extend(maintainability_feedback)
        failing_cases = [result for result in runner_payload.test_results if not result.passed]
        if failing_cases:
            feedback.append(
                f"{len(failing_cases)} test(s) failed: "
                + ", ".join(result.name for result in failing_cases[:3])
            )

        grading = GradingResult(
            mode=mode,
            correctness_score=round(correctness_score, 4),
            maintainability_score=round(maintainability_score, 4),
            safety_score=round(safety_score, 4),
            final_score=round(final_score, 4),
            visible_passed=visible_passed,
            visible_total=visible_total,
            hidden_passed=hidden_passed,
            hidden_total=hidden_total,
            feedback=feedback,
            test_results=runner_payload.test_results,
        )
        return execution, grading

    def _combine_scores(self, correctness: float, maintainability: float, safety: float) -> float:
        return max(
            0.0,
            min(
                1.0,
                correctness * self.weights.correctness
                + maintainability * self.weights.maintainability
                + safety * self.weights.safety,
            ),
        )

    def _score_safety(self, execution: ExecutionResult) -> tuple[float, list[str]]:
        if execution.status == "unsafe_code":
            return 0.0, [execution.error or "Unsafe code rejected by AST preflight"]
        if execution.status in {"syntax_error", "runtime_error", "timeout"}:
            return 0.4, [execution.error or "Execution failed"]
        if execution.status == "missing_function":
            return 0.5, [execution.error or "Expected function is missing"]
        return 1.0, []

    def _score_maintainability(
        self,
        source: str,
        function_name: str,
    ) -> tuple[float, list[str]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return 0.0, ["Source does not parse cleanly"]

        function_node = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                function_node = node
                break
        if function_node is None:
            return 0.0, [f"Expected function '{function_name}' is missing"]

        score = 1.0
        feedback: list[str] = []
        if ast.get_docstring(function_node) is None:
            score -= 0.1
            feedback.append("Add a short docstring to the target function")
        if function_node.returns is None or any(
            arg.annotation is None for arg in function_node.args.args
        ):
            score -= 0.2
            feedback.append("Add type hints to the function signature")
        if len(function_node.body) > 20:
            score -= 0.1
            feedback.append("Keep the implementation compact and focused")
        if any(isinstance(node, ast.Global) for node in ast.walk(function_node)):
            score -= 0.1
            feedback.append("Avoid global state in the solution")
        if len(source.splitlines()) > 80:
            score -= 0.1
            feedback.append("Keep the overall solution concise")
        return max(0.0, round(score, 4)), feedback
