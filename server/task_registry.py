# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Task registry backed by the Rosetta dataset."""

from __future__ import annotations

from pathlib import Path

from .tasks import (
    TaskDefinition,
    build_array_length_task,
    build_tokenize_with_escaping_task,
    build_word_frequency_task,
    dataset_path,
    load_rosetta_pairs,
)


class TaskRegistry:
    """Load and expose the curated set of v1 tasks."""

    def __init__(self, path: Path | None = None):
        self._pairs = load_rosetta_pairs(path or dataset_path())
        self._tasks = self._build_tasks()
        self._ordered_ids = list(self._tasks)

    def _build_tasks(self) -> dict[str, TaskDefinition]:
        return {
            "array_length": build_array_length_task(self._pairs["Array length"]),
            "tokenize_with_escaping": build_tokenize_with_escaping_task(
                self._pairs["Tokenize a string with escaping"]
            ),
            "word_frequency": build_word_frequency_task(self._pairs["Word frequency"]),
        }

    def get(self, task_id: str) -> TaskDefinition:
        """Return one task definition by id."""

        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"Unknown task_id '{task_id}'") from exc

    def default_task_id(self) -> str:
        """Return the deterministic default task id."""

        return self._ordered_ids[0]

    def task_ids(self) -> list[str]:
        """Return the curated task ids in stable order."""

        return list(self._ordered_ids)
