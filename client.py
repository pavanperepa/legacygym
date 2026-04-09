# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Client for the Legacygym modernization environment."""

from __future__ import annotations

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

from .models import LegacygymAction, LegacygymObservation, LegacygymState


class LegacygymEnv(EnvClient[LegacygymAction, LegacygymObservation, LegacygymState]):
    """Persistent WebSocket client for the modernization environment."""

    def _step_payload(self, action: LegacygymAction) -> Dict[str, Any]:
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[LegacygymObservation]:
        obs_data = payload.get("observation", {})
        obs_data.setdefault("done", payload.get("done", obs_data.get("done", False)))
        obs_data.setdefault("reward", payload.get("reward", obs_data.get("reward")))
        observation = LegacygymObservation(**obs_data)
        return StepResult(
            observation=observation,
            reward=payload.get("reward", observation.reward),
            done=payload.get("done", observation.done),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> LegacygymState:
        return LegacygymState(**payload)
