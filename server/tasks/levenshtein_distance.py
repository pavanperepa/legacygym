# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Medium-hard Rosetta migration task: Levenshtein distance."""

from __future__ import annotations

_MAX_RECORD_LENGTH = 255

try:
    from ...models import TaskSpec
    from .base import RosettaTaskPair, TaskCase, TaskDefinition
except ImportError:
    from models import TaskSpec
    from server.tasks.base import RosettaTaskPair, TaskCase, TaskDefinition


def _reference_distance(left: str, right: str) -> int:
    left = left[:_MAX_RECORD_LENGTH]
    right = right[:_MAX_RECORD_LENGTH]
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            substitute_cost = previous[j - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, substitute_cost))
        previous = current
    return previous[-1]


def build_task(pair: RosettaTaskPair) -> TaskDefinition:
    """Create the Levenshtein-distance migration task."""

    visible_cases = [
        TaskCase("kitten_sitting", ("kitten", "sitting"), 3),
        TaskCase("gumbo_gambol", ("gumbo", "gambol"), 2),
    ]
    hidden_cases = [
        TaskCase("empty_left", ("", "abc"), 3, hidden=True),
        TaskCase("empty_right", ("abc", ""), 3, hidden=True),
        TaskCase("identical", ("legacy", "legacy"), 0, hidden=True),
        TaskCase("symmetric_case", ("Saturday", "Sunday"), _reference_distance("Saturday", "Sunday"), hidden=True),
        TaskCase("repeated_characters", ("bookkeeper", "booker"), _reference_distance("bookkeeper", "booker"), hidden=True),
        TaskCase("classic_example", ("intention", "execution"), _reference_distance("intention", "execution"), hidden=True),
        TaskCase("longer_strings", ("modernization", "modularization"), _reference_distance("modernization", "modularization"), hidden=True),
        TaskCase(
            "transposition_is_two_edits",
            ("ab", "ba"),
            _reference_distance("ab", "ba"),
            hidden=True,
        ),
        TaskCase(
            "long_common_prefix",
            ("x" * 32 + "tail", "x" * 32 + "trail"),
            _reference_distance("x" * 32 + "tail", "x" * 32 + "trail"),
            hidden=True,
        ),
        TaskCase(
            "long_repeated_strings",
            ("kitten" * 8, "sitten" * 8),
            _reference_distance("kitten" * 8, "sitten" * 8),
            hidden=True,
        ),
        TaskCase(
            "suffix_insertion_block",
            ("alignment", "misalignment"),
            _reference_distance("alignment", "misalignment"),
            hidden=True,
        ),
        TaskCase(
            "trailing_spaces_are_significant",
            ("abc  ", "abc"),
            _reference_distance("abc  ", "abc"),
            hidden=True,
        ),
        TaskCase(
            "leading_spaces_are_significant",
            ("  abc", "abc"),
            _reference_distance("  abc", "abc"),
            hidden=True,
        ),
        TaskCase(
            "truncate_to_255_characters_left",
            ("a" * 255 + "zzz", "a" * 255),
            _reference_distance("a" * 255 + "zzz", "a" * 255),
            hidden=True,
        ),
        TaskCase(
            "truncate_to_255_characters_right",
            ("b" * 254 + "c", "b" * 254 + "d" + "extra"),
            _reference_distance("b" * 254 + "c", "b" * 254 + "d" + "extra"),
            hidden=True,
        ),
    ]
    spec = TaskSpec(
        task_id="levenshtein_distance",
        task_name="Levenshtein distance",
        difficulty="medium",
        summary=(
            "Translate the COBOL behavior into a Python function named "
            "`levenshtein_distance`. Return the minimum number of single-character "
            "insertions, deletions, and substitutions needed to transform one string "
            "into the other. Do not treat swaps as a separate primitive. Preserve the "
            "legacy fixed-width input semantics from the COBOL source rather than "
            "silently normalizing the strings. Do not print anything, and do not use "
            "external libraries."
        ),
        cobol_source=pair.cobol_code,
        python_function_signature="def levenshtein_distance(left: str, right: str) -> int",
        function_name="levenshtein_distance",
        step_budget=9,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = """def levenshtein_distance(left: str, right: str) -> int:\n    \"\"\"Return the Levenshtein edit distance between two strings.\"\"\"\n    raise NotImplementedError(\"Implement the COBOL-to-Python migration\")\n"""
    return TaskDefinition(
        spec=spec,
        module_name="levenshtein_distance_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=[],
    )
