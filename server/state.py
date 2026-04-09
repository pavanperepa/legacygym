# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Internal mutable state for the modernization environment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

try:
    from ..models import (
        AttemptStatus,
        ExecutionResult,
        GradingResult,
        LegacygymState,
        RewardComponent,
    )
    from .tasks.base import TaskDefinition
except ImportError:
    from models import (
        AttemptStatus,
        ExecutionResult,
        GradingResult,
        LegacygymState,
        RewardComponent,
    )
    from server.tasks.base import TaskDefinition


@dataclass
class EnvironmentSessionState:
    """Mutable episode state kept by the environment instance."""

    episode_id: str
    task: TaskDefinition
    step_count: int = 0
    current_code: str = ""
    done: bool = False
    best_visible_score: float = 0.0
    last_action: Optional[str] = None
    last_error: Optional[str] = None
    last_execution: Optional[ExecutionResult] = None
    last_grading: Optional[GradingResult] = None
    reward_breakdown: list[RewardComponent] = field(default_factory=list)

    def attempt_status(self) -> AttemptStatus:
        """Return the current draft summary exposed in observations."""

        return AttemptStatus(
            has_solution=bool(self.current_code.strip()),
            solution_char_count=len(self.current_code),
            solution_line_count=len(self.current_code.splitlines()) if self.current_code else 0,
            last_action=self.last_action,
            last_error=self.last_error,
        )

    def public_state(self) -> LegacygymState:
        """Convert internal state to the OpenEnv state model."""

        return LegacygymState(
            episode_id=self.episode_id,
            step_count=self.step_count,
            task_id=self.task.spec.task_id,
            task_name=self.task.spec.task_name,
            difficulty=self.task.spec.difficulty,
            current_code=self.current_code,
            max_steps=self.task.spec.step_budget,
            done=self.done,
            last_action=self.last_action,
            last_error=self.last_error,
            best_visible_score=self.best_visible_score,
            last_execution=self.last_execution,
            last_grading=self.last_grading,
            reward_breakdown=self.reward_breakdown,
        )
