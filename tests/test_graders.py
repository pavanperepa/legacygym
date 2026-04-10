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

    assert 0.0 <= bad.final_score <= 1.0
    assert 0.0 <= good.final_score <= 1.0
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
