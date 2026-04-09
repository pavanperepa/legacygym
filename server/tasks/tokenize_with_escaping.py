# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Medium Rosetta migration task: tokenize with escaping."""

from __future__ import annotations

try:
    from ...models import TaskSpec
    from .base import RosettaTaskPair, TaskCase, TaskDefinition
except ImportError:
    from models import TaskSpec
    from server.tasks.base import RosettaTaskPair, TaskCase, TaskDefinition


def build_task(pair: RosettaTaskPair) -> TaskDefinition:
    """Create the tokenize-with-escaping migration task."""

    visible_cases = [
        TaskCase("escaped_separator", ("Hello\\,World,Again", ",", "\\"), ["Hello,World", "Again"]),
        TaskCase("empty_token", ("a|b||c", "|", "\\"), ["a", "b", "", "c"]),
    ]
    hidden_cases = [
        TaskCase("escaped_escape", ("one\\\\,two", ",", "\\"), ["one\\", "two"], hidden=True),
        TaskCase("trailing_escape", ("abc\\", ",", "\\"), ["abc\\"], hidden=True),
        TaskCase("mixed_symbols", ("x\\|y|z\\||", "|", "\\"), ["x|y", "z|", ""], hidden=True),
    ]
    spec = TaskSpec(
        task_id="tokenize_with_escaping",
        task_name="Tokenize a string with escaping",
        difficulty="medium",
        summary=(
            "Translate the COBOL behavior into a Python function named "
            "`tokenize_with_escaping`. Split `text` on unescaped occurrences of "
            "`separator`. The escape character removes itself and preserves the next "
            "character literally. If the escape character appears at the very end of "
            "the string, keep it in the final token. Return a list of tokens and do "
            "not print anything."
        ),
        cobol_source=pair.cobol_code,
        python_function_signature=(
            "def tokenize_with_escaping(text: str, separator: str, escape: str) -> list[str]"
        ),
        function_name="tokenize_with_escaping",
        step_budget=8,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = """def tokenize_with_escaping(text: str, separator: str, escape: str) -> list[str]:\n    \"\"\"Split on non-escaped separators while preserving escaped characters.\"\"\"\n    raise NotImplementedError(\"Implement the COBOL-to-Python migration\")\n"""
    return TaskDefinition(
        spec=spec,
        module_name="tokenize_with_escaping_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=[],
    )
