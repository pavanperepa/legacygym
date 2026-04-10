# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Trajectory-oriented reward adapter for the modernization benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass

try:
    from ...models import ExecutionResult, GradingResult, RewardComponent
except ImportError:
    from models import ExecutionResult, GradingResult, RewardComponent


@dataclass(frozen=True)
class RewardWeights:
    """Centralized reward weights for trajectory shaping."""

    invalid_code_penalty: float = -0.08
    unsafe_code_penalty: float = -0.16
    runtime_failure_penalty: float = -0.04
    parse_success_bonus: float = 0.02
    visible_progress_scale: float = 0.45
    visible_regression_scale: float = -0.08
    stagnation_penalty: float = -0.01
    maintainability_scale: float = 0.04
    safety_scale: float = 0.03
    completion_efficiency_scale: float = 0.1


DEFAULT_REWARD_WEIGHTS = RewardWeights()


class MinimalRewardAdapter:
    """Compute richer RL-friendly reward from deterministic grading output."""

    def __init__(self, weights: RewardWeights = DEFAULT_REWARD_WEIGHTS):
        self.weights = weights

    def weights_as_dict(self) -> dict[str, float]:
        """Expose the active shaping config for environment metadata and logs."""

        return asdict(self.weights)

    def compute(
        self,
        *,
        action_type: str,
        previous_best_visible_score: float,
        current_best_visible_score: float,
        current_visible_score: float,
        execution: ExecutionResult | None,
        grading: GradingResult | None,
        done: bool,
        step_count: int,
        max_steps: int,
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
        elif execution is not None and execution.status in {"runtime_error", "timeout", "missing_function"}:
            components.append(
                RewardComponent(
                    name="runtime_failure_penalty",
                    value=self.weights.runtime_failure_penalty,
                    detail=execution.error or "Candidate failed during execution",
                )
            )
        elif action_type == "replace_solution" and execution is not None and execution.status == "ok":
            components.append(
                RewardComponent(
                    name="parse_success_bonus",
                    value=self.weights.parse_success_bonus,
                    detail="Candidate parsed and loaded successfully",
                )
            )

        if action_type == "run_visible_tests" and grading is not None:
            improvement = max(0.0, current_best_visible_score - previous_best_visible_score)
            regression = max(0.0, previous_best_visible_score - current_visible_score)
            if improvement > 0:
                components.append(
                    RewardComponent(
                        name="visible_progress_bonus",
                        value=round(improvement * self.weights.visible_progress_scale, 4),
                        detail="Visible-test pass ratio improved",
                    )
                )
            elif current_visible_score < previous_best_visible_score:
                components.append(
                    RewardComponent(
                        name="visible_regression_penalty",
                        value=round(regression * self.weights.visible_regression_scale, 4),
                        detail="Visible-test performance regressed from the best-so-far score",
                    )
                )
            else:
                components.append(
                    RewardComponent(
                        name="stagnation_penalty",
                        value=self.weights.stagnation_penalty,
                        detail="Visible tests produced no new progress",
                    )
                )
            components.append(
                RewardComponent(
                    name="maintainability_signal",
                    value=round((grading.maintainability_score - 0.5) * self.weights.maintainability_scale, 4),
                    detail="Small shaping signal from maintainability quality",
                )
            )
            components.append(
                RewardComponent(
                    name="safety_signal",
                    value=round((grading.safety_score - 0.5) * self.weights.safety_scale, 4),
                    detail="Small shaping signal from safe execution quality",
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
            if grading.final_score > 0:
                remaining_ratio = max(0.0, (max_steps - step_count) / max_steps) if max_steps else 0.0
                components.append(
                    RewardComponent(
                        name="completion_efficiency_bonus",
                        value=round(
                            grading.final_score * remaining_ratio * self.weights.completion_efficiency_scale,
                            4,
                        ),
                        detail="Small bonus for finishing strong with steps remaining",
                    )
                )

        reward = round(sum(component.value for component in components), 4)
        return reward, components
