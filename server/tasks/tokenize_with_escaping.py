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
        TaskCase("leading_separator", ("|a\\||b", "|", "\\"), ["", "a|", "b"], hidden=True),
        TaskCase("double_escape_before_separator", ("a\\\\|b|c", "|", "\\"), ["a\\", "b", "c"], hidden=True),
        TaskCase("no_separator_present", ("value\\|tail", ",", "\\"), ["value|tail"], hidden=True),
        TaskCase(
            "consecutive_escaped_separator_runs",
            ("a\\,b\\,c,d", ",", "\\"),
            ["a,b,c", "d"],
            hidden=True,
        ),
        TaskCase(
            "separator_at_end",
            ("keep|tail|", "|", "\\"),
            ["keep", "tail", ""],
            hidden=True,
        ),
        TaskCase(
            "escaped_escape_then_literal_separator",
            ("root\\\\|child\\|leaf|end", "|", "\\"),
            ["root\\", "child|leaf", "end"],
            hidden=True,
        ),
    ]
    spec = TaskSpec(
        task_id="tokenize_with_escaping",
        task_name="Tokenize a string with escaping",
        difficulty="medium",
        summary=(
            "Translate the COBOL behavior into a Python function named "
            "`tokenize_with_escaping`. Partition the input into tokens using the "
            "separator, but treat escaped characters as literal content. A trailing "
            "escape character remains in the final token. Empty tokens still matter. "
            "Return the tokens in order and do not print anything."
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
