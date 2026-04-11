# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""UTF-8 loaders for task datasets used by the environment."""

from __future__ import annotations

import json
from pathlib import Path

from .base import CobolReviewSample, RosettaTaskPair


def _normalize_text(value: str) -> str:
    """Collapse the dataset's non-breaking spaces into regular spaces."""

    return value.replace("\u00a0", " ").strip()


def load_rosetta_pairs(path: Path) -> dict[str, RosettaTaskPair]:
    """Load paired COBOL/Python records keyed by task name."""

    rows = json.loads(path.read_text(encoding="utf-8"))
    paired: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        task_name = _normalize_text(row["task_name"])
        language_name = _normalize_text(row["language_name"])
        paired.setdefault(task_name, {})[language_name] = {
            "description": _normalize_text(row["task_description"]),
            "code": _normalize_text(row["code"]),
        }

    result: dict[str, RosettaTaskPair] = {}
    for task_name, languages in paired.items():
        if "COBOL" not in languages or "Python" not in languages:
            continue
        cobol_entry = languages["COBOL"]
        python_entry = languages["Python"]
        result[task_name] = RosettaTaskPair(
            task_name=task_name,
            task_description=cobol_entry["description"] or python_entry["description"],
            cobol_code=cobol_entry["code"],
            python_code=python_entry["code"],
        )
    return result


def cobol_review_dataset_path() -> Path:
    """Return the expected COBOL review dataset path from the repository root."""

    return Path(__file__).resolve().parents[2] / "cobol-code-sample-review.json"


def load_cobol_review_samples(path: Path) -> dict[str, CobolReviewSample]:
    """Load the top-level COBOL review dataset keyed by program name."""

    rows = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, CobolReviewSample] = {}
    for row in rows:
        program_name = _normalize_text(row["program_name"])
        result[program_name] = CobolReviewSample(
            program_name=program_name,
            input_file_names=[
                item.strip()
                for item in _normalize_text(row["input_file_names"]).split(",")
                if item.strip()
            ],
            output_file_names=[
                item.strip()
                for item in _normalize_text(row["output_file_names"]).split(",")
                if item.strip()
            ],
            inputs=json.loads(row["inputs"]),
            outputs=json.loads(row["outputs"]),
            complete_prompt=_normalize_text(row["complete_prompt"]),
            instruct_prompt=_normalize_text(row["instruct_prompt"]),
            canonical_solution=_normalize_text(row["canonical_solution"]),
        )
    return result
