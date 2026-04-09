# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Hard Rosetta migration task: word frequency."""

from __future__ import annotations

from collections import Counter
import re

try:
    from ...models import TaskSpec
    from .base import RosettaTaskPair, TaskCase, TaskDefinition
except ImportError:
    from models import TaskSpec
    from server.tasks.base import RosettaTaskPair, TaskCase, TaskDefinition


_WORD_RE = re.compile(r"[A-Za-z]+")


def _reference_word_frequency(text: str, n: int) -> list[tuple[str, int]]:
    words = _WORD_RE.findall(text.lower())
    counts = Counter(words)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:n]


def build_task(pair: RosettaTaskPair) -> TaskDefinition:
    """Create the word-frequency migration task."""

    visible_cases = [
        TaskCase(
            "simple_counts",
            ("red blue red green blue red", 2),
            _reference_word_frequency("red blue red green blue red", 2),
        ),
        TaskCase(
            "case_and_punctuation",
            ("Hello, hello! HELLO? world.", 2),
            _reference_word_frequency("Hello, hello! HELLO? world.", 2),
        ),
    ]
    hidden_cases = [
        TaskCase(
            "alphabetical_tie_break",
            ("gamma beta alpha gamma beta alpha", 3),
            _reference_word_frequency("gamma beta alpha gamma beta alpha", 3),
            hidden=True,
        ),
        TaskCase(
            "ignore_numbers",
            ("one 1 one 2 two 2 TWO", 2),
            _reference_word_frequency("one 1 one 2 two 2 TWO", 2),
            hidden=True,
        ),
        TaskCase(
            "truncate_n",
            ("apple banana apple cherry banana banana", 1),
            _reference_word_frequency("apple banana apple cherry banana banana", 1),
            hidden=True,
        ),
    ]
    spec = TaskSpec(
        task_id="word_frequency",
        task_name="Word frequency",
        difficulty="hard",
        summary=(
            "Translate the COBOL behavior into a Python function named "
            "`word_frequency`. Extract words using the regex `[A-Za-z]+`, lowercase "
            "them, count frequencies, sort by descending frequency and then "
            "alphabetically for tie-breaking, and return the top `n` items as a list "
            "of `(word, count)` tuples. Do not read files or print output."
        ),
        cobol_source=pair.cobol_code,
        python_function_signature="def word_frequency(text: str, n: int) -> list[tuple[str, int]]",
        function_name="word_frequency",
        step_budget=10,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = """from collections import Counter\nimport re\n\n_WORD_RE = re.compile(r\"[A-Za-z]+\")\n\n\ndef word_frequency(text: str, n: int) -> list[tuple[str, int]]:\n    \"\"\"Return the top-n lowercase word counts from the input text.\"\"\"\n    raise NotImplementedError(\"Implement the COBOL-to-Python migration\")\n"""
    return TaskDefinition(
        spec=spec,
        module_name="word_frequency_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=["collections", "re"],
    )
