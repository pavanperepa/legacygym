# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Shared grading constants."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ScoreWeights:
    """Stable scoring weights for final normalized task scores."""

    correctness: float = 0.8
    maintainability: float = 0.1
    safety: float = 0.1

    def as_dict(self) -> dict[str, float]:
        """Expose score-weight config for metadata and logs."""

        return asdict(self)


DEFAULT_SCORE_WEIGHTS = ScoreWeights()
