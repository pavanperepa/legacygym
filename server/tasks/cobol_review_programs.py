# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Program-level COBOL review tasks backed by file fixtures."""

from __future__ import annotations

import re

try:
    from ...models import TaskSpec
    from .base import CobolReviewSample, TaskCase, TaskDefinition
except ImportError:
    from models import TaskSpec
    from server.tasks.base import CobolReviewSample, TaskCase, TaskDefinition


def _join_lines(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _file_pattern_move_reference(inputs: dict[str, str]) -> dict[str, str]:
    source = inputs.get("input.txt", "")
    kept: list[str] = []
    for raw_line in source.splitlines():
        line = raw_line.rstrip("\r")
        if "." not in line:
            continue
        extension = line.rsplit(".", 1)[1]
        if extension in {"txt", "doc", "docx"}:
            kept.append(line)
    return {"output.txt": _join_lines(kept)}


def _convert_extensions_to_csv_reference(inputs: dict[str, str]) -> dict[str, str]:
    source = inputs.get("input.txt", "")
    converted: list[str] = []
    for raw_line in source.splitlines():
        line = raw_line.rstrip("\r")
        trimmed = line.strip()
        if len(trimmed) <= 4:
            continue
        extension = trimmed[-5:]
        if extension[1:5] == ".txt":
            base = trimmed[:-5]
            converted.append(f"{base}.csv")
        elif extension in {".docx", ".xlsx"}:
            base = trimmed[:-5]
            converted.append(f"{base}.csv")
    return {"output.txt": _join_lines(converted)}


_ALPHA_ONLY_NAME = re.compile(r"^[A-Za-z]+$")


def _sort_valid_customer_names_reference(inputs: dict[str, str]) -> dict[str, str]:
    source = inputs.get("input.txt", "")
    valid_names = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and _ALPHA_ONLY_NAME.fullmatch(line.strip())
    ]
    return {"output.txt": _join_lines(sorted(valid_names))}


def _compare_csv_files_reference(inputs: dict[str, str]) -> dict[str, str]:
    left_lines = inputs.get("task_func24_inp1", "").splitlines()
    right_lines = inputs.get("task_func24_inp2", "").splitlines()
    output_lines = ["Line Number,Status,Content"]
    max_len = max(len(left_lines), len(right_lines))
    for index in range(max_len):
        line_number = f"{index + 1:06d}"
        left = left_lines[index] if index < len(left_lines) else None
        right = right_lines[index] if index < len(right_lines) else None
        if left is not None and right is not None:
            if left == "" and right == "":
                continue
            if left == right:
                output_lines.append(f"{line_number}, ,{left}")
            else:
                if left != "":
                    output_lines.append(f"{line_number},-,{left}")
                if right != "":
                    output_lines.append(f"{line_number},+,{right}")
        elif left is not None and left != "":
            output_lines.append(f"{line_number},-,{left}")
        elif right is not None and right != "":
            output_lines.append(f"{line_number},+,{right}")
    return {"task_func24_out": _join_lines(output_lines)}


def _build_summary(sample: CobolReviewSample, contract: str) -> str:
    prompt = sample.instruct_prompt.split("Code:", 1)[0].strip()
    return (
        f"Translate the COBOL program into a Python function named `{contract}`. "
        "The function receives a mapping of input file names to file contents and "
        "must return a mapping of output file names to file contents. "
        "Preserve the legacy file-processing behavior from the COBOL source and do "
        f"not print anything.\n\nLegacy task brief:\n{prompt}"
    )


def build_file_pattern_move_task(sample: CobolReviewSample) -> TaskDefinition:
    visible_case = TaskCase(
        "dataset_sample",
        (sample.inputs,),
        sample.outputs,
    )
    hidden_cases = [
        TaskCase(
            "mixed_extensions",
            (
                {
                    "input.txt": (
                        "notes.doc\narchive.tar.gz\nmemo.txt\nbook.docx\nimage.jpeg\n"
                    )
                },
            ),
            {"output.txt": "notes.doc\nmemo.txt\nbook.docx\n"},
            hidden=True,
        ),
        TaskCase(
            "case_sensitive_extensions",
            (
                {
                    "input.txt": (
                        "REPORT.DOCX\nsummary.doc\nlower.txt\nplain\n"
                    )
                },
            ),
            {"output.txt": "summary.doc\nlower.txt\n"},
            hidden=True,
        ),
    ]
    spec = TaskSpec(
        task_id="review_file_pattern_move",
        task_name="Review dataset: file pattern move",
        difficulty="medium",
        summary=_build_summary(sample, "file_pattern_move"),
        cobol_source=sample.canonical_solution,
        python_function_signature=(
            "def file_pattern_move(inputs: dict[str, str]) -> dict[str, str]"
        ),
        function_name="file_pattern_move",
        step_budget=11,
        visible_examples=[visible_case.as_example()],
    )
    initial_stub = (
        "def file_pattern_move(inputs: dict[str, str]) -> dict[str, str]:\n"
        '    """Transform the input files into the expected output files."""\n'
        '    raise NotImplementedError("Implement the COBOL-to-Python migration")\n'
    )
    return TaskDefinition(
        spec=spec,
        module_name="review_file_pattern_move_candidate",
        initial_stub=initial_stub,
        visible_cases=[visible_case],
        hidden_cases=hidden_cases,
        allowed_imports=[],
    )


def build_extension_to_csv_task(sample: CobolReviewSample) -> TaskDefinition:
    visible_cases = [
        TaskCase(
            "dataset_sample",
            (sample.inputs,),
            sample.outputs,
        ),
        TaskCase(
            "uppercase_and_short_txt_visible",
            (
                {
                    "input.txt": (
                        "ab.txt\nDATA.TXT\nmemo.docx\n"
                    )
                },
            ),
            {"output.txt": "a.csv\nmemo.csv\n"},
        ),
    ]
    hidden_cases = [
        TaskCase(
            "mixed_supported_extensions",
            (
                {
                    "input.txt": (
                        "notes.txt\nreport.docx\nsheet.xlsx\nimage.png\n"
                    )
                },
            ),
            {"output.txt": "note.csv\nreport.csv\nsheet.csv\n"},
            hidden=True,
        ),
        TaskCase(
            "embedded_spaces_and_case_sensitivity",
            (
                {
                    "input.txt": (
                        " report.docx \nnotes.txt\nmemo.XLSX\n"
                    )
                },
            ),
            {"output.txt": "report.csv\nnote.csv\n"},
            hidden=True,
        ),
        TaskCase(
            "five_character_slice_for_txt",
            (
                {
                    "input.txt": (
                        "test2file.txt\nxy.txt\n"
                    )
                },
            ),
            {"output.txt": "test2fil.csv\nx.csv\n"},
            hidden=True,
        ),
    ]
    spec = TaskSpec(
        task_id="review_extension_to_csv",
        task_name="Review dataset: extension to csv",
        difficulty="hard",
        summary=(
            _build_summary(sample, "convert_extensions_to_csv")
            + "\n\nPreserve the legacy five-character extension slicing behavior from "
            "the COBOL program, including its fixed-width truncation quirk for `.txt` files. "
            "Extension matching is case-sensitive."
        ),
        cobol_source=sample.canonical_solution,
        python_function_signature=(
            "def convert_extensions_to_csv(inputs: dict[str, str]) -> dict[str, str]"
        ),
        function_name="convert_extensions_to_csv",
        step_budget=12,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = (
        "def convert_extensions_to_csv(inputs: dict[str, str]) -> dict[str, str]:\n"
        '    """Convert supported input filenames into legacy CSV output names."""\n'
        '    raise NotImplementedError("Implement the COBOL-to-Python migration")\n'
    )
    return TaskDefinition(
        spec=spec,
        module_name="review_extension_to_csv_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=[],
    )


def build_compare_csv_files_task(sample: CobolReviewSample) -> TaskDefinition:
    visible_cases = [
        TaskCase(
            "dataset_sample",
            (sample.inputs,),
            sample.outputs,
        ),
        TaskCase(
            "identical_and_extra_rows_visible",
            (
                {
                    "task_func24_inp1": (
                        "A\nB\nC\nD\n"
                    ),
                    "task_func24_inp2": (
                        "A\nX\nC\n"
                    )
                },
            ),
            {
                "task_func24_out": (
                    "Line Number,Status,Content\n"
                    "000001, ,A\n"
                    "000002,-,B\n"
                    "000002,+,X\n"
                    "000003, ,C\n"
                    "000004,-,D\n"
                )
            },
        ),
        TaskCase(
            "blank_rows_are_skipped_visible",
            (
                {
                    "task_func24_inp1": "hdr\n\nsame\nTail,1\n",
                    "task_func24_inp2": "hdr\n\nsame\nTail,2\n",
                },
            ),
            {
                "task_func24_out": (
                    "Line Number,Status,Content\n"
                    "000001, ,hdr\n"
                    "000003, ,same\n"
                    "000004,-,Tail,1\n"
                    "000004,+,Tail,2\n"
                )
            },
        ),
    ]
    hidden_cases = [
        TaskCase(
            "blank_right_line_is_ignored",
            (
                {
                    "task_func24_inp1": "Name,Age\nAlice,30\nBob,25\nTail,1\n",
                    "task_func24_inp2": "Name,Age\nAlice,31\nBob,25\n\n",
                },
            ),
            {
                "task_func24_out": (
                    "Line Number,Status,Content\n"
                    "000001, ,Name,Age\n"
                    "000002,-,Alice,30\n"
                    "000002,+,Alice,31\n"
                    "000003, ,Bob,25\n"
                    "000004,-,Tail,1\n"
                )
            },
            hidden=True,
        ),
        TaskCase(
            "extra_lines_from_second_file",
            (
                {
                    "task_func24_inp1": "hdr\nsame\n",
                    "task_func24_inp2": "hdr\nsame\nnew1\nnew2\n",
                },
            ),
            {
                "task_func24_out": (
                    "Line Number,Status,Content\n"
                    "000001, ,hdr\n"
                    "000002, ,same\n"
                    "000003,+,new1\n"
                    "000004,+,new2\n"
                )
            },
            hidden=True,
        ),
        TaskCase(
            "matching_blank_rows_preserve_line_numbers",
            (
                {
                    "task_func24_inp1": "A\n\nB\n",
                    "task_func24_inp2": "A\n\nX\n",
                },
            ),
            {
                "task_func24_out": (
                    "Line Number,Status,Content\n"
                    "000001, ,A\n"
                    "000003,-,B\n"
                    "000003,+,X\n"
                )
            },
            hidden=True,
        ),
    ]
    spec = TaskSpec(
        task_id="review_compare_csv_files",
        task_name="Review dataset: compare csv files",
        difficulty="hard",
        summary=_build_summary(sample, "compare_csv_files")
        + "\n\nCompare both input files line by line. When both lines exist and match, "
        "emit one blank-status row. When they differ, emit `-` for the first file and "
        "`+` for the second file. Ignore empty lines when only one side has content. "
        "If both files are blank at the same line number, emit no report row for that "
        "position but keep later line numbers aligned to the original record positions.",
        cobol_source=sample.canonical_solution,
        python_function_signature=(
            "def compare_csv_files(inputs: dict[str, str]) -> dict[str, str]"
        ),
        function_name="compare_csv_files",
        step_budget=12,
        visible_examples=[case.as_example() for case in visible_cases],
    )
    initial_stub = (
        "def compare_csv_files(inputs: dict[str, str]) -> dict[str, str]:\n"
        '    """Return a CSV diff report for the provided legacy input files."""\n'
        '    raise NotImplementedError("Implement the COBOL-to-Python migration")\n'
    )
    return TaskDefinition(
        spec=spec,
        module_name="review_compare_csv_files_candidate",
        initial_stub=initial_stub,
        visible_cases=visible_cases,
        hidden_cases=hidden_cases,
        allowed_imports=[],
    )
