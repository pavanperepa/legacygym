from legacygym.server.execution import PythonExecutionRunner
from legacygym.server.graders import DeterministicCodeGrader
from legacygym.server.task_registry import TaskRegistry


def test_grader_scores_good_code_higher_than_bad_code():
    registry = TaskRegistry()
    task = registry.get("array_length")
    grader = DeterministicCodeGrader(PythonExecutionRunner())

    good_source = """def array_length(items: list[str]) -> int:\n    \"\"\"Return the number of items.\"\"\"\n    return len(items)\n"""
    bad_source = """def array_length(items: list[str]) -> int:\n    \"\"\"Return the number of items.\"\"\"\n    return 0\n"""

    _, good = grader.grade(task, good_source, mode="full")
    _, bad = grader.grade(task, bad_source, mode="full")

    assert 0.0 < bad.final_score < 1.0
    assert 0.0 < good.final_score < 1.0
    assert good.hidden_total > 0
    assert good.final_score > bad.final_score


def test_grader_normalizes_structured_outputs_before_comparison():
    registry = TaskRegistry()
    task = registry.get("word_frequency")
    grader = DeterministicCodeGrader(PythonExecutionRunner())

    source = """from collections import Counter\nimport re\n\n_WORD_RE = re.compile(r\"[A-Za-z]+\")\n\n\ndef word_frequency(text: str, n: int) -> list[tuple[str, int]]:\n    \"\"\"Return the top-n lowercase word counts.\"\"\"\n    counts = Counter(_WORD_RE.findall(text.lower()))\n    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]\n"""

    _, grading = grader.grade(task, source, mode="visible")

    assert grading.visible_total == 2
    assert grading.visible_passed == 2
    assert grading.correctness_score == 1.0


def test_review_file_pattern_move_task_grades_reference_behavior():
    registry = TaskRegistry()
    task = registry.get("review_file_pattern_move")
    grader = DeterministicCodeGrader(PythonExecutionRunner())

    source = """def file_pattern_move(inputs: dict[str, str]) -> dict[str, str]:
    \"\"\"Return only filenames with supported extensions.\"\"\"
    kept = []
    for line in inputs.get("input.txt", "").splitlines():
        if "." not in line:
            continue
        extension = line.rsplit(".", 1)[1]
        if extension in {"txt", "doc", "docx"}:
            kept.append(line)
    output = ""
    if kept:
        output = "\\n".join(kept) + "\\n"
    return {"output.txt": output}
"""

    _, grading = grader.grade(task, source, mode="full")

    assert grading.visible_passed == grading.visible_total
    assert grading.hidden_passed == grading.hidden_total
    assert 0.0 < grading.final_score < 1.0


def test_review_compare_csv_files_task_grades_reference_behavior():
    registry = TaskRegistry()
    task = registry.get("review_compare_csv_files")
    grader = DeterministicCodeGrader(PythonExecutionRunner())

    source = """def compare_csv_files(inputs: dict[str, str]) -> dict[str, str]:
    \"\"\"Return a CSV diff report for the two legacy input files.\"\"\"
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
    return {"task_func24_out": "\\n".join(output_lines) + "\\n"}
"""

    _, grading = grader.grade(task, source, mode="full")

    assert grading.visible_passed == grading.visible_total
    assert grading.hidden_passed == grading.hidden_total
    assert 0.0 < grading.final_score < 1.0


def test_review_compare_csv_files_penalizes_reporting_double_blank_rows():
    registry = TaskRegistry()
    task = registry.get("review_compare_csv_files")
    grader = DeterministicCodeGrader(PythonExecutionRunner())

    source = """def compare_csv_files(inputs: dict[str, str]) -> dict[str, str]:
    \"\"\"Return a CSV diff report for the two legacy input files.\"\"\"
    left_lines = inputs.get("task_func24_inp1", "").splitlines()
    right_lines = inputs.get("task_func24_inp2", "").splitlines()
    output_lines = ["Line Number,Status,Content"]
    max_len = max(len(left_lines), len(right_lines))
    for index in range(max_len):
        line_number = f"{index + 1:06d}"
        left = left_lines[index] if index < len(left_lines) else None
        right = right_lines[index] if index < len(right_lines) else None
        if left is not None and right is not None:
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
    return {"task_func24_out": "\\n".join(output_lines) + "\\n"}
"""

    _, grading = grader.grade(task, source, mode="full")

    assert grading.final_score < 0.99
    assert grading.hidden_passed < grading.hidden_total
