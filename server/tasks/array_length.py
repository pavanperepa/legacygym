# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Easy Rosetta migration task: array length."""

from __future__ import annotations

try:
    from ...models import TaskSpec
    from .base import RosettaTaskPair, TaskCase, TaskDefinition
except ImportError:
    from models import TaskSpec
    from server.tasks.base import RosettaTaskPair, TaskCase, TaskDefinition


def build_task(pair: RosettaTaskPair) -> TaskDefinition:
    """Create the easy array-length migration task."""

    visible_cases = [
        TaskCase("two_items", (["apple", "orange"],), 2),
        TaskCase("empty_list", ([],), 0),
    ]
    hidden_cases = [
        TaskCase("single_item", (["x"],), 1, hidden=True),
        TaskCase("five_items", (["a", "b", "c", "d", "e"],), 5, hidden=True),
        TaskCase("repeated_values", (["same", "same", "same"],), 3, hidden=True),
    ]
    spec = TaskSpec(
        task_id="array_length",
        task_name="Array length",
        difficulty="easy",
        summary=(
            "Translate the legacy COBOL behavior into a Python function named "
            "`array_length`. Return the number of elements in `items`. Do not print "
            "anything, and do not mutate the input list."
        ),
        cobol_source=pair.cobol_code,
        python_function_signature="def array_length(items: list[str]) -> int",
        function_name="array_length",
        step_budget=6,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = """def array_length(items: list[str]) -> int:\n    \"\"\"Return the number of elements in the input list.\"\"\"\n    raise NotImplementedError(\"Implement the COBOL-to-Python migration\")\n"""
    return TaskDefinition(
        spec=spec,
        module_name="array_length_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=[],
    )
