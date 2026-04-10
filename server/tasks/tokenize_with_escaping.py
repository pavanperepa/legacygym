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


_MAX_TOKENS = 32
_MAX_TOKEN_LENGTH = 16


def _reference_tokenize_with_escaping(
    text: str,
    separator: str,
    escape: str,
) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    escaped = False

    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == escape:
            escaped = True
        elif char == separator:
            tokens.append("".join(current)[:_MAX_TOKEN_LENGTH])
            current = []
            if len(tokens) >= _MAX_TOKENS:
                return tokens[:_MAX_TOKENS]
        else:
            current.append(char)

    if escaped:
        current.append(escape)
    if len(tokens) < _MAX_TOKENS:
        tokens.append("".join(current)[:_MAX_TOKEN_LENGTH])
    return tokens[:_MAX_TOKENS]


def build_task(pair: RosettaTaskPair) -> TaskDefinition:
    """Create the tokenize-with-escaping migration task."""

    visible_cases = [
        TaskCase(
            "escaped_separator",
            ("Hello\\,World,Again", ",", "\\"),
            _reference_tokenize_with_escaping("Hello\\,World,Again", ",", "\\"),
        ),
        TaskCase(
            "empty_token",
            ("a|b||c", "|", "\\"),
            _reference_tokenize_with_escaping("a|b||c", "|", "\\"),
        ),
    ]
    hidden_cases = [
        TaskCase(
            "escaped_escape",
            ("one\\\\,two", ",", "\\"),
            _reference_tokenize_with_escaping("one\\\\,two", ",", "\\"),
            hidden=True,
        ),
        TaskCase(
            "trailing_escape",
            ("abc\\", ",", "\\"),
            _reference_tokenize_with_escaping("abc\\", ",", "\\"),
            hidden=True,
        ),
        TaskCase(
            "mixed_symbols",
            ("x\\|y|z\\||", "|", "\\"),
            _reference_tokenize_with_escaping("x\\|y|z\\||", "|", "\\"),
            hidden=True,
        ),
        TaskCase(
            "leading_separator",
            ("|a\\||b", "|", "\\"),
            _reference_tokenize_with_escaping("|a\\||b", "|", "\\"),
            hidden=True,
        ),
        TaskCase(
            "double_escape_before_separator",
            ("a\\\\|b|c", "|", "\\"),
            _reference_tokenize_with_escaping("a\\\\|b|c", "|", "\\"),
            hidden=True,
        ),
        TaskCase(
            "no_separator_present",
            ("value\\|tail", ",", "\\"),
            _reference_tokenize_with_escaping("value\\|tail", ",", "\\"),
            hidden=True,
        ),
        TaskCase(
            "consecutive_escaped_separator_runs",
            ("a\\,b\\,c,d", ",", "\\"),
            _reference_tokenize_with_escaping("a\\,b\\,c,d", ",", "\\"),
            hidden=True,
        ),
        TaskCase(
            "separator_at_end",
            ("keep|tail|", "|", "\\"),
            _reference_tokenize_with_escaping("keep|tail|", "|", "\\"),
            hidden=True,
        ),
        TaskCase(
            "escaped_escape_then_literal_separator",
            ("root\\\\|child\\|leaf|end", "|", "\\"),
            _reference_tokenize_with_escaping("root\\\\|child\\|leaf|end", "|", "\\"),
            hidden=True,
        ),
        TaskCase(
            "token_truncation_to_16_chars",
            ("abcdefghijklmnopq|tiny", "|", "\\"),
            _reference_tokenize_with_escaping("abcdefghijklmnopq|tiny", "|", "\\"),
            hidden=True,
        ),
        TaskCase(
            "escaped_long_token_truncates_after_unescape",
            ("abcd\\|efghijklmnopq|done", "|", "\\"),
            _reference_tokenize_with_escaping("abcd\\|efghijklmnopq|done", "|", "\\"),
            hidden=True,
        ),
        TaskCase(
            "token_limit_of_32",
            ("|".join(f"t{i}" for i in range(35)), "|", "\\"),
            _reference_tokenize_with_escaping("|".join(f"t{i}" for i in range(35)), "|", "\\"),
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
            "Respect the legacy storage limits implied by the COBOL working-storage "
            "layout. Return the tokens in order and do not print anything."
        ),
        cobol_source=pair.cobol_code,
        python_function_signature=(
            "def tokenize_with_escaping(text: str, separator: str, escape: str) -> list[str]"
        ),
        function_name="tokenize_with_escaping",
        step_budget=8,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = """def tokenize_with_escaping(text: str, separator: str, escape: str) -> list[str]:\n    \"\"\"Tokenize escaped separators while preserving the legacy storage limits.\"\"\"\n    raise NotImplementedError(\"Implement the COBOL-to-Python migration\")\n"""
    return TaskDefinition(
        spec=spec,
        module_name="tokenize_with_escaping_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=[],
    )
