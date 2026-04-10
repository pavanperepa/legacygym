# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Main OpenEnv environment implementation."""

from __future__ import annotations

import os
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment

try:
    from ..models import LegacygymAction, LegacygymObservation
    from .execution import PythonExecutionRunner
    from .graders import DeterministicCodeGrader, MinimalRewardAdapter
    from .state import EnvironmentSessionState
    from .task_registry import TaskRegistry
except ImportError:
    from models import LegacygymAction, LegacygymObservation
    from server.execution import PythonExecutionRunner
    from server.graders import DeterministicCodeGrader, MinimalRewardAdapter
    from server.state import EnvironmentSessionState
    from server.task_registry import TaskRegistry


class LegacygymEnvironment(Environment):
    """Environment for deterministic COBOL-to-Python modernization tasks."""

    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    ENVIRONMENT_VERSION: str = "baseline-v1"

    def __init__(self):
        super().__init__()
        self.registry = TaskRegistry()
        self.runner = PythonExecutionRunner()
        self.grader = DeterministicCodeGrader(self.runner)
        self.reward_adapter = MinimalRewardAdapter()
        self._session = self._new_session(self.registry.default_task_id())

    def _new_session(self, task_id: str, episode_id: str | None = None) -> EnvironmentSessionState:
        task = self.registry.get(task_id)
        return EnvironmentSessionState(
            episode_id=episode_id or str(uuid4()),
            task=task,
            current_code=task.initial_stub,
        )

    def reset(
        self,
        seed: int | None = None,
        episode_id: str | None = None,
        **kwargs,
    ) -> LegacygymObservation:
        del seed
        requested_task_id = (
            kwargs.get("task_id") or os.getenv("TASK_NAME") or os.getenv("LEGACYGYM_TASK")
        )
        task_id = requested_task_id or self.registry.default_task_id()
        self._session = self._new_session(task_id, episode_id=episode_id)
        return self._build_observation(reward=0.0)

    def step(
        self,
        action: LegacygymAction,
        timeout_s: float | None = None,
        **kwargs,
    ) -> LegacygymObservation:
        del kwargs
        if self._session.done:
            return self._build_observation(reward=0.0)

        if timeout_s is not None:
            self.runner.timeout_s = timeout_s

        self._session.step_count += 1
        self._session.last_action = action.action_type
        self._session.reward_breakdown = []
        previous_best_visible = self._session.best_visible_score
        current_visible_score = previous_best_visible

        if action.action_type == "replace_solution":
            self._session.current_code = action.code or ""
            self._session.last_execution = self.runner.run(
                source=self._session.current_code,
                function_name=self._session.task.spec.function_name,
                cases=[],
                allowed_imports=self._session.task.allowed_imports,
            ).execution
            self._session.last_grading = None
            self._session.last_error = self._session.last_execution.error
        elif action.action_type == "run_visible_tests":
            execution, grading = self.grader.grade(
                task=self._session.task,
                source=self._session.current_code,
                mode="visible",
            )
            self._session.last_execution = execution
            self._session.last_grading = grading
            visible_score = grading.visible_passed / grading.visible_total if grading.visible_total else 0.0
            current_visible_score = visible_score
            self._session.best_visible_score = max(self._session.best_visible_score, visible_score)
            self._session.last_error = execution.error or (grading.feedback[0] if grading.feedback else None)
        elif action.action_type == "submit":
            self._finalize_with_full_grading()
            current_visible_score = self._session.best_visible_score

        if not self._session.done and self._session.step_count >= self._session.task.spec.step_budget:
            self._finalize_with_full_grading()
            current_visible_score = self._session.best_visible_score

        reward, components = self.reward_adapter.compute(
            action_type=action.action_type,
            previous_best_visible_score=previous_best_visible,
            current_best_visible_score=self._session.best_visible_score,
            current_visible_score=current_visible_score,
            execution=self._session.last_execution,
            grading=self._session.last_grading,
            done=self._session.done,
            step_count=self._session.step_count,
            max_steps=self._session.task.spec.step_budget,
        )
        self._session.reward_breakdown = components
        return self._build_observation(reward=reward)

    def _finalize_with_full_grading(self) -> None:
        execution, grading = self.grader.grade(
            task=self._session.task,
            source=self._session.current_code,
            mode="full",
        )
        self._session.last_execution = execution
        self._session.last_grading = grading
        visible_score = grading.visible_passed / grading.visible_total if grading.visible_total else 0.0
        self._session.best_visible_score = max(self._session.best_visible_score, visible_score)
        self._session.last_error = execution.error or (grading.feedback[0] if grading.feedback else None)
        self._session.done = True

    def _build_observation(self, reward: float) -> LegacygymObservation:
        remaining_steps = max(0, self._session.task.spec.step_budget - self._session.step_count)
        server_info = {
            "task_id": self._session.task.spec.task_id,
            "remaining_steps": remaining_steps,
            "available_task_ids": self.registry.task_ids(),
            "registry_signature": self.registry.signature(),
            "environment_name": "legacygym",
            "environment_version": self.ENVIRONMENT_VERSION,
            "runner_timeout_s": self.runner.timeout_s,
            "reward_weights": self.reward_adapter.weights_as_dict(),
            "score_weights": self.grader.weights.as_dict(),
        }
        return LegacygymObservation(
            task=self._session.task.spec,
            attempt=self._session.attempt_status(),
            current_code=self._session.current_code,
            server_info=server_info,
            last_execution=self._session.last_execution,
            last_grading=self._session.last_grading,
            reward_breakdown=self._session.reward_breakdown,
            done=self._session.done,
            reward=reward,
            metadata=server_info,
        )

    @property
    def state(self):
        return self._session.public_state()
