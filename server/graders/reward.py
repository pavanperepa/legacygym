# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Minimal pluggable reward adapter for v1."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from ...models import ExecutionResult, GradingResult, RewardComponent
except ImportError:
    from models import ExecutionResult, GradingResult, RewardComponent


@dataclass(frozen=True)
class RewardWeights:
    """Centralized reward weights so RL tuning can change later."""

    invalid_code_penalty: float = -0.05
    unsafe_code_penalty: float = -0.1
    visible_progress_bonus: float = 0.15


DEFAULT_REWARD_WEIGHTS = RewardWeights()


class MinimalRewardAdapter:
    """Compute lightweight trajectory rewards from deterministic grading output."""

    def __init__(self, weights: RewardWeights = DEFAULT_REWARD_WEIGHTS):
        self.weights = weights

    def compute(
        self,
        *,
        action_type: str,
        previous_best_visible_score: float,
        current_best_visible_score: float,
        execution: ExecutionResult | None,
        grading: GradingResult | None,
        done: bool,
    ) -> tuple[float, list[RewardComponent]]:
        components: list[RewardComponent] = []

        if execution is not None and execution.status == "syntax_error":
            components.append(
                RewardComponent(
                    name="invalid_code_penalty",
                    value=self.weights.invalid_code_penalty,
                    detail="Candidate source did not parse",
                )
            )
        elif execution is not None and execution.status == "unsafe_code":
            components.append(
                RewardComponent(
                    name="unsafe_code_penalty",
                    value=self.weights.unsafe_code_penalty,
                    detail="Candidate used blocked operations or imports",
                )
            )

        if action_type == "run_visible_tests" and grading is not None:
            delta = max(0.0, current_best_visible_score - previous_best_visible_score)
            if delta > 0:
                components.append(
                    RewardComponent(
                        name="visible_progress_bonus",
                        value=round(delta * self.weights.visible_progress_bonus, 4),
                        detail="Visible-test pass ratio improved",
                    )
                )

        if done and grading is not None:
            components.append(
                RewardComponent(
                    name="final_task_score",
                    value=grading.final_score,
                    detail="Final normalized task score",
                )
            )

        reward = round(sum(component.value for component in components), 4)
        return reward, components
