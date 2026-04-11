# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Task registry backed by the Rosetta dataset."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .tasks import (
    TaskDefinition,
    build_align_columns_task,
    build_automatic_abbreviations_task,
    build_array_length_task,
    build_compare_csv_files_task,
    build_extension_to_csv_task,
    build_file_pattern_move_task,
    build_levenshtein_distance_task,
    build_word_frequency_task,
    cobol_review_dataset_path,
    dataset_path,
    load_cobol_review_samples,
    load_rosetta_pairs,
)


class TaskRegistry:
    """Load and expose the curated set of v1 tasks."""

    def __init__(self, path: Path | None = None):
        self._pairs = load_rosetta_pairs(path or dataset_path())
        self._review_samples = load_cobol_review_samples(cobol_review_dataset_path())
        self._tasks = self._build_tasks()
        self._ordered_ids = list(self._tasks)

    def _build_tasks(self) -> dict[str, TaskDefinition]:
        return {
            "array_length": build_array_length_task(self._pairs["Array length"]),
            "automatic_abbreviations": build_automatic_abbreviations_task(
                self._pairs["Abbreviations, automatic"]
            ),
            "levenshtein_distance": build_levenshtein_distance_task(
                self._pairs["Levenshtein distance"]
            ),
            "word_frequency": build_word_frequency_task(self._pairs["Word frequency"]),
            "align_columns": build_align_columns_task(self._pairs["Align columns"]),
            "review_file_pattern_move": build_file_pattern_move_task(
                self._review_samples["task_func_02"]
            ),
            "review_extension_to_csv": build_extension_to_csv_task(
                self._review_samples["task_func_08"]
            ),
            "review_compare_csv_files": build_compare_csv_files_task(
                self._review_samples["task_func_24"]
            ),
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

    def signature(self) -> str:
        """Return a stable signature for the currently registered tasks."""

        payload = [
            {
                "task_id": task.spec.task_id,
                "task_name": task.spec.task_name,
                "difficulty": task.spec.difficulty,
                "step_budget": task.spec.step_budget,
                "visible_cases": len(task.visible_cases),
                "hidden_cases": len(task.hidden_cases),
            }
            for task in self._tasks.values()
        ]
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:12]
