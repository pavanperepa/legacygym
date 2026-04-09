# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""UTF-8 loader for Rosetta task comparisons."""

from __future__ import annotations

import json
from pathlib import Path

from .base import RosettaTaskPair


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
