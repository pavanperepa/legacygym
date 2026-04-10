# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Hard Rosetta migration task: automatic abbreviations."""

from __future__ import annotations

from typing import Any

try:
    from ...models import TaskSpec
    from .base import RosettaTaskPair, TaskCase, TaskDefinition
except ImportError:
    from models import TaskSpec
    from server.tasks.base import RosettaTaskPair, TaskCase, TaskDefinition


def _reference_automatic_abbreviations(text: str, expected_count: int) -> dict[str, Any]:
    words = text.split()
    if len(words) != expected_count:
        return {"status": "error", "reason": "expected_count_mismatch"}

    if len(set(words)) != len(words):
        return {"status": "error", "reason": "identical_entries"}

    longest = max((len(word) for word in words), default=0)
    for length in range(1, longest + 1):
        abbreviations = [word[:length] for word in words]
        if len(set(abbreviations)) == len(words):
            return {
                "status": "ok",
                "length": length,
                "abbreviations": abbreviations,
            }

    return {"status": "error", "reason": "identical_entries"}


def build_task(pair: RosettaTaskPair) -> TaskDefinition:
    """Create the automatic-abbreviations migration task."""

    visible_cases = [
        TaskCase(
            "weekdays",
            ("Monday Tuesday Wednesday Thursday Friday Saturday Sunday", 7),
            _reference_automatic_abbreviations(
                "Monday Tuesday Wednesday Thursday Friday Saturday Sunday",
                7,
            ),
        ),
        TaskCase(
            "june_july_january",
            ("june july january", 3),
            _reference_automatic_abbreviations("june july january", 3),
        ),
    ]
    hidden_cases = [
        TaskCase(
            "not_enough_entries",
            ("Monday Tuesday Wednesday", 7),
            _reference_automatic_abbreviations("Monday Tuesday Wednesday", 7),
            hidden=True,
        ),
        TaskCase(
            "identical_entries",
            ("same same same", 3),
            _reference_automatic_abbreviations("same same same", 3),
            hidden=True,
        ),
        TaskCase(
            "requires_full_word_for_one_entry",
            ("dog door dorm dolphin", 4),
            _reference_automatic_abbreviations("dog door dorm dolphin", 4),
            hidden=True,
        ),
        TaskCase(
            "mixed_whitespace",
            ("alpha   algebra\talmanac alpine", 4),
            _reference_automatic_abbreviations("alpha   algebra\talmanac alpine", 4),
            hidden=True,
        ),
        TaskCase(
            "already_unique_first_letters",
            ("red blue green yellow", 4),
            _reference_automatic_abbreviations("red blue green yellow", 4),
            hidden=True,
        ),
        TaskCase(
            "late_disambiguation",
            ("transport transpose transatlantic transaction", 4),
            _reference_automatic_abbreviations(
                "transport transpose transatlantic transaction",
                4,
            ),
            hidden=True,
        ),
    ]
    spec = TaskSpec(
        task_id="automatic_abbreviations",
        task_name="Automatic abbreviations",
        difficulty="hard",
        summary=(
            "Translate the COBOL behavior into a Python function named "
            "`automatic_abbreviations`. The input text contains space-delimited "
            "entries that must be abbreviated using the shortest shared prefix length "
            "that makes every abbreviation unique. Respect the validation behavior "
            "implied by the legacy workflow: the line must contain exactly the "
            "expected number of entries, and duplicate full entries are an error. "
            "Return a structured result and do not print anything."
        ),
        cobol_source=pair.cobol_code,
        python_function_signature=(
            "def automatic_abbreviations(text: str, expected_count: int) -> dict[str, object]"
        ),
        function_name="automatic_abbreviations",
        step_budget=10,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = """def automatic_abbreviations(text: str, expected_count: int) -> dict[str, object]:\n    \"\"\"Return the shortest unique abbreviations or a structured validation error.\"\"\"\n    raise NotImplementedError(\"Implement the COBOL-to-Python migration\")\n"""
    return TaskDefinition(
        spec=spec,
        module_name="automatic_abbreviations_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=[],
    )
