# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Hard Rosetta migration task: align columns."""

from __future__ import annotations

from itertools import zip_longest

try:
    from ...models import TaskSpec
    from .base import RosettaTaskPair, TaskCase, TaskDefinition
except ImportError:
    from models import TaskSpec
    from server.tasks.base import RosettaTaskPair, TaskCase, TaskDefinition


def _justify(value: str, width: int, alignment: str) -> str:
    if alignment == "left":
        return value.ljust(width)
    if alignment == "right":
        return value.rjust(width)
    if alignment == "center":
        return value.center(width)
    raise ValueError(f"Unsupported alignment: {alignment}")


def _reference_align_columns(lines: list[str], alignment: str) -> list[str]:
    rows = [line.rstrip("$").split("$") for line in lines]
    widths = [
        max(len(cell) for cell in column)
        for column in zip_longest(*rows, fillvalue="")
    ]
    return [
        " ".join(
            _justify(cell, widths[index], alignment)
            for index, cell in enumerate(row)
        ).rstrip()
        for row in rows
    ]


def build_task(pair: RosettaTaskPair) -> TaskDefinition:
    """Create the align-columns migration task."""

    lines_sample = [
        "Given$a$text$file",
        "to$align$nicely",
        "with$ragged$columns",
    ]
    visible_cases = [
        TaskCase(
            "left_alignment",
            (lines_sample, "left"),
            _reference_align_columns(lines_sample, "left"),
        ),
        TaskCase(
            "right_alignment",
            (["a$bb", "ccc$d"], "right"),
            _reference_align_columns(["a$bb", "ccc$d"], "right"),
        ),
        TaskCase(
            "center_single_column_visible",
            (["solo", "wider"], "center"),
            _reference_align_columns(["solo", "wider"], "center"),
        ),
    ]
    hidden_cases = [
        TaskCase(
            "center_alignment",
            (["one$two$three", "twelve$x$z"], "center"),
            _reference_align_columns(["one$two$three", "twelve$x$z"], "center"),
            hidden=True,
        ),
        TaskCase(
            "trailing_delimiter",
            (["a$b$", "cc$ddd$"], "left"),
            _reference_align_columns(["a$b$", "cc$ddd$"], "left"),
            hidden=True,
        ),
        TaskCase(
            "varying_column_counts",
            (["short$wide", "loooooong$x$tail"], "left"),
            _reference_align_columns(["short$wide", "loooooong$x$tail"], "left"),
            hidden=True,
        ),
        TaskCase(
            "empty_middle_cells",
            (["a$$c", "long$value$"], "right"),
            _reference_align_columns(["a$$c", "long$value$"], "right"),
            hidden=True,
        ),
        TaskCase(
            "single_column_rows",
            (["solo", "wider"], "center"),
            _reference_align_columns(["solo", "wider"], "center"),
            hidden=True,
        ),
        TaskCase(
            "empty_input_line",
            (["", "alpha$beta"], "left"),
            _reference_align_columns(["", "alpha$beta"], "left"),
            hidden=True,
        ),
        TaskCase(
            "center_single_column_padding",
            (["a", "wide"], "center"),
            _reference_align_columns(["a", "wide"], "center"),
            hidden=True,
        ),
        TaskCase(
            "multiple_empty_rows",
            (["", "", "alpha$beta"], "right"),
            _reference_align_columns(["", "", "alpha$beta"], "right"),
            hidden=True,
        ),
        TaskCase(
            "ragged_center_alignment",
            (["aa$bbb$c", "d$eeeee$ff", "gggg"], "center"),
            _reference_align_columns(["aa$bbb$c", "d$eeeee$ff", "gggg"], "center"),
            hidden=True,
        ),
        TaskCase(
            "leading_empty_column_center",
            (["$alpha", "bb$cc"], "center"),
            _reference_align_columns(["$alpha", "bb$cc"], "center"),
            hidden=True,
        ),
        TaskCase(
            "multiple_trailing_delimiters",
            (["a$b$$", "cc$ddd$$"], "left"),
            _reference_align_columns(["a$b$$", "cc$ddd$$"], "left"),
            hidden=True,
        ),
    ]
    spec = TaskSpec(
        task_id="align_columns",
        task_name="Align columns",
        difficulty="hard",
        summary=(
            "Translate the COBOL behavior into a Python function named "
            "`align_columns`. Treat each line as a row of `$`-delimited fields and "
            "return aligned text rows with one space between columns. Preserve row "
            "order, preserve empty leading and trailing fields, size each column "
            "from the widest observed cell, and respect `left`, `right`, or "
            "`center` alignment."
        ),
        cobol_source=pair.cobol_code,
        python_function_signature=(
            "def align_columns(lines: list[str], alignment: str) -> list[str]"
        ),
        function_name="align_columns",
        step_budget=11,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = """def align_columns(lines: list[str], alignment: str) -> list[str]:\n    \"\"\"Align dollar-delimited columns across the provided lines.\"\"\"\n    raise NotImplementedError(\"Implement the COBOL-to-Python migration\")\n"""
    return TaskDefinition(
        spec=spec,
        module_name="align_columns_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=["itertools"],
    )
