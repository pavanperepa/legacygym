# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Typed models for the Legacygym modernization environment."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import BaseModel, Field, model_validator


ActionType = Literal["replace_solution", "run_visible_tests", "submit"]
Difficulty = Literal["easy", "medium", "hard"]
ExecutionStatus = Literal[
    "not_run",
    "ok",
    "syntax_error",
    "runtime_error",
    "timeout",
    "unsafe_code",
    "missing_function",
]
GradingMode = Literal["visible", "full"]


class RewardComponent(BaseModel):
    """One reward term emitted by the reward adapter."""

    name: str = Field(..., description="Stable component name")
    value: float = Field(..., description="Signed reward contribution")
    detail: str = Field(default="", description="Short explanation of the component")


class TaskExample(BaseModel):
    """Visible example shown to the agent."""

    name: str = Field(..., description="Short label for the example")
    input_summary: str = Field(..., description="Human-readable input summary")
    expected_summary: str = Field(..., description="Human-readable expected output")


class TaskSpec(BaseModel):
    """Public task metadata exposed in observations."""

    task_id: str = Field(..., description="Stable task identifier")
    task_name: str = Field(..., description="Human-readable task name")
    difficulty: Difficulty = Field(..., description="Task difficulty tier")
    summary: str = Field(..., description="Normalized migration brief for the agent")
    cobol_source: str = Field(..., description="Legacy COBOL source provided to the agent")
    python_function_signature: str = Field(
        ..., description="Exact Python function signature expected by the grader"
    )
    function_name: str = Field(..., description="Function name expected in the solution")
    step_budget: int = Field(..., description="Maximum number of agent actions in the episode")
    visible_examples: List[TaskExample] = Field(
        default_factory=list,
        description="Representative visible test examples shown to the agent",
    )


class AttemptStatus(BaseModel):
    """Summary of the current draft."""

    has_solution: bool = Field(..., description="Whether the agent has provided code")
    solution_char_count: int = Field(..., description="Length of the current candidate in chars")
    solution_line_count: int = Field(..., description="Line count of the current candidate")
    last_action: Optional[ActionType] = Field(
        default=None,
        description="Most recent action processed by the environment",
    )
    last_error: Optional[str] = Field(default=None, description="Last actionable error message")


class TestCaseResult(BaseModel):
    """Outcome of a single grader test case."""

    name: str = Field(..., description="Stable test-case label")
    passed: bool = Field(..., description="Whether the candidate passed this test")
    hidden: bool = Field(..., description="Whether this case is hidden from the agent")
    message: str = Field(default="", description="Brief result message")


class ExecutionResult(BaseModel):
    """Structured result from the controlled execution runner."""

    status: ExecutionStatus = Field(..., description="Runner status code")
    function_name: Optional[str] = Field(
        default=None, description="Expected callable exercised by the runner"
    )
    error: Optional[str] = Field(default=None, description="High-level execution error text")
    stdout: str = Field(default="", description="Captured stdout from candidate execution")
    stderr: str = Field(default="", description="Captured stderr from candidate execution")
    duration_ms: int = Field(default=0, description="End-to-end execution duration in ms")


class GradingResult(BaseModel):
    """Deterministic grading summary."""

    mode: GradingMode = Field(..., description="Visible-only or full grading mode")
    correctness_score: float = Field(..., ge=0.0, le=1.0)
    maintainability_score: float = Field(..., ge=0.0, le=1.0)
    safety_score: float = Field(..., ge=0.0, le=1.0)
    final_score: float = Field(..., ge=0.0, le=1.0)
    visible_passed: int = Field(..., ge=0)
    visible_total: int = Field(..., ge=0)
    hidden_passed: int = Field(default=0, ge=0)
    hidden_total: int = Field(default=0, ge=0)
    feedback: List[str] = Field(default_factory=list)
    test_results: List[TestCaseResult] = Field(default_factory=list)


class LegacygymAction(Action):
    """Action for the modernization environment."""

    action_type: ActionType = Field(..., description="High-level action type")
    code: Optional[str] = Field(
        default=None,
        description="Full Python candidate source, required for replace_solution",
    )

    @model_validator(mode="after")
    def validate_payload(self) -> "LegacygymAction":
        if self.action_type == "replace_solution":
            if not self.code or not self.code.strip():
                raise ValueError("code is required for replace_solution")
        elif self.code is not None:
            raise ValueError("code is only allowed for replace_solution")
        return self


class LegacygymObservation(Observation):
    """Observation returned by the modernization environment."""

    task: TaskSpec = Field(..., description="Current task specification")
    attempt: AttemptStatus = Field(..., description="Current candidate status")
    current_code: str = Field(default="", description="Current candidate Python source")
    last_execution: Optional[ExecutionResult] = Field(
        default=None,
        description="Most recent execution result, if any",
    )
    last_grading: Optional[GradingResult] = Field(
        default=None,
        description="Most recent grading result, if any",
    )
    reward_breakdown: List[RewardComponent] = Field(
        default_factory=list,
        description="Reward terms for the latest transition",
    )


class LegacygymState(State):
    """Extended environment state for debugging and evaluation."""

    task_id: str = Field(..., description="Stable current task identifier")
    task_name: str = Field(..., description="Human-readable task name")
    difficulty: Difficulty = Field(..., description="Current task difficulty")
    current_code: str = Field(default="", description="Current candidate Python source")
    max_steps: int = Field(..., description="Per-episode step budget")
    done: bool = Field(default=False, description="Whether the episode is complete")
    last_action: Optional[ActionType] = Field(default=None, description="Last action processed")
    last_error: Optional[str] = Field(default=None, description="Last actionable error")
    best_visible_score: float = Field(default=0.0, ge=0.0, le=1.0)
    last_execution: Optional[ExecutionResult] = Field(default=None)
    last_grading: Optional[GradingResult] = Field(default=None)
    reward_breakdown: List[RewardComponent] = Field(default_factory=list)


class InferenceStepLog(BaseModel):
    """Utility model for testing `inference.py` logging behavior."""

    step: int
    action: str
    reward: float
    done: bool
    error: Optional[str] = None


class InferenceEpisodeLog(BaseModel):
    """Utility model for testing final inference summaries."""

    success: bool
    steps: int
    score: float
    rewards: List[float] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
