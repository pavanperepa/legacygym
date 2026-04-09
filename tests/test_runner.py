from legacygym.server.execution import PythonExecutionRunner
from legacygym.server.tasks.base import TaskCase


def test_runner_reports_syntax_errors():
    runner = PythonExecutionRunner()

    result = runner.run(
        source="def array_length(items):\nreturn len(items)\n",
        function_name="array_length",
        cases=[TaskCase("basic", (["a"],), 1)],
        allowed_imports=[],
    )

    assert result.execution.status == "syntax_error"


def test_runner_rejects_unsafe_imports():
    runner = PythonExecutionRunner()

    result = runner.run(
        source="import os\n\ndef array_length(items):\n    return len(items)\n",
        function_name="array_length",
        cases=[TaskCase("basic", (["a"],), 1)],
        allowed_imports=[],
    )

    assert result.execution.status == "unsafe_code"
