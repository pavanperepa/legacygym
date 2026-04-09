# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Controlled Python execution harness for candidate solutions."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass
from typing import Iterable

try:
    from ...models import ExecutionResult, TestCaseResult
    from ..tasks.base import TaskCase
except ImportError:
    from models import ExecutionResult, TestCaseResult
    from server.tasks.base import TaskCase


_DEFAULT_ALLOWED_IMPORTS = {"collections", "itertools", "math", "re", "string", "typing"}
_BANNED_IMPORTS = {
    "asyncio",
    "builtins",
    "ctypes",
    "glob",
    "importlib",
    "io",
    "os",
    "pathlib",
    "pickle",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
}
_BANNED_CALLS = {"breakpoint", "compile", "eval", "exec", "input", "open", "__import__"}
_BANNED_ATTRS = {"fork", "popen", "spawn", "system"}


@dataclass
class RunnerPayload:
    """Execution details returned from the runner prior to grading."""

    execution: ExecutionResult
    test_results: list[TestCaseResult]


class UnsafeCodeError(ValueError):
    """Raised when AST preflight rejects the candidate."""


class PythonExecutionRunner:
    """Run candidate code in a small subprocess-based harness."""

    def __init__(self, timeout_s: float = 2.0):
        self.timeout_s = timeout_s

    def _validate_ast(self, source: str, allowed_imports: Iterable[str]) -> ast.Module:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise exc

        effective_allowlist = set(allowed_imports) | _DEFAULT_ALLOWED_IMPORTS
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in _BANNED_IMPORTS or root not in effective_allowlist:
                        raise UnsafeCodeError(f"Import '{alias.name}' is not allowed")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in _BANNED_IMPORTS or root not in effective_allowlist:
                    raise UnsafeCodeError(f"Import from '{node.module}' is not allowed")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in _BANNED_CALLS:
                    raise UnsafeCodeError(f"Call to '{node.func.id}' is not allowed")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _BANNED_ATTRS:
                    raise UnsafeCodeError(f"Attribute call '{node.func.attr}' is not allowed")
        return tree

    def run(
        self,
        source: str,
        function_name: str,
        cases: list[TaskCase],
        allowed_imports: Iterable[str] | None = None,
    ) -> RunnerPayload:
        """Run the candidate against the provided deterministic cases."""

        start = time.perf_counter()
        try:
            self._validate_ast(source, allowed_imports or [])
        except SyntaxError as exc:
            return RunnerPayload(
                execution=ExecutionResult(
                    status="syntax_error",
                    function_name=function_name,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - start) * 1000),
                ),
                test_results=[],
            )
        except UnsafeCodeError as exc:
            return RunnerPayload(
                execution=ExecutionResult(
                    status="unsafe_code",
                    function_name=function_name,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - start) * 1000),
                ),
                test_results=[],
            )

        with tempfile.TemporaryDirectory(prefix="legacygym_runner_") as temp_dir:
            temp_path = Path(temp_dir)
            candidate_path = temp_path / "candidate_module.py"
            cases_path = temp_path / "cases.json"
            harness_path = temp_path / "harness.py"
            candidate_path.write_text(source, encoding="utf-8")
            serialized_cases = [
                {
                    "name": case.name,
                    "args": list(case.args),
                    "kwargs": case.kwargs or {},
                    "expected": case.expected,
                    "hidden": case.hidden,
                }
                for case in cases
            ]
            cases_path.write_text(json.dumps(serialized_cases), encoding="utf-8")
            harness_path.write_text(_HARNESS_CODE, encoding="utf-8")

            try:
                completed = subprocess.run(
                    [sys.executable, "-I", str(harness_path), str(candidate_path), function_name, str(cases_path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout_s,
                    env={
                        "PYTHONIOENCODING": "utf-8",
                        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                    },
                )
            except subprocess.TimeoutExpired:
                return RunnerPayload(
                    execution=ExecutionResult(
                        status="timeout",
                        function_name=function_name,
                        error=f"Execution timed out after {self.timeout_s:.2f}s",
                        duration_ms=int((time.perf_counter() - start) * 1000),
                    ),
                    test_results=[],
                )

        duration_ms = int((time.perf_counter() - start) * 1000)
        if completed.returncode != 0:
            return RunnerPayload(
                execution=ExecutionResult(
                    status="runtime_error",
                    function_name=function_name,
                    error=(completed.stderr or completed.stdout or "Harness execution failed").strip(),
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    duration_ms=duration_ms,
                ),
                test_results=[],
            )

        payload = json.loads(completed.stdout or "{}")
        execution = ExecutionResult(
            status=payload.get("status", "runtime_error"),
            function_name=function_name,
            error=payload.get("error"),
            stdout=payload.get("stdout", ""),
            stderr=payload.get("stderr", ""),
            duration_ms=duration_ms,
        )
        test_results = [
            TestCaseResult(
                name=result["name"],
                passed=result["passed"],
                hidden=result["hidden"],
                message=result.get("message", ""),
            )
            for result in payload.get("results", [])
        ]
        return RunnerPayload(execution=execution, test_results=test_results)


_HARNESS_CODE = textwrap.dedent(
    """
    import contextlib
    import importlib.util
    import io
    import json
    import sys
    from pathlib import Path


    def main() -> int:
        candidate_path = Path(sys.argv[1])
        function_name = sys.argv[2]
        cases_path = Path(sys.argv[3])
        results = []
        import_stdout = io.StringIO()
        import_stderr = io.StringIO()

        try:
            spec = importlib.util.spec_from_file_location("candidate_module", candidate_path)
            if spec is None or spec.loader is None:
                raise RuntimeError("Unable to load candidate module")
            module = importlib.util.module_from_spec(spec)
            with contextlib.redirect_stdout(import_stdout), contextlib.redirect_stderr(import_stderr):
                spec.loader.exec_module(module)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "runtime_error",
                        "error": f"Module import failed: {exc}",
                        "stdout": import_stdout.getvalue(),
                        "stderr": import_stderr.getvalue(),
                        "results": [],
                    }
                )
            )
            return 0

        if not hasattr(module, function_name):
            print(
                json.dumps(
                    {
                        "status": "missing_function",
                        "error": f"Expected function '{function_name}' was not defined",
                        "stdout": import_stdout.getvalue(),
                        "stderr": import_stderr.getvalue(),
                        "results": [],
                    }
                )
            )
            return 0

        target = getattr(module, function_name)
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        try:
            cases = json.loads(cases_path.read_text(encoding="utf-8"))
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                for case in cases:
                    try:
                        actual = target(*case["args"], **case["kwargs"])
                        passed = actual == case["expected"]
                        message = "passed" if passed else f"expected {case['expected']!r}, got {actual!r}"
                    except Exception as exc:
                        passed = False
                        message = f"raised {type(exc).__name__}: {exc}"
                    results.append(
                        {
                            "name": case["name"],
                            "passed": passed,
                            "hidden": case["hidden"],
                            "message": message,
                        }
                    )
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "runtime_error",
                        "error": f"Case execution failed: {exc}",
                        "stdout": import_stdout.getvalue() + stdout_buffer.getvalue(),
                        "stderr": import_stderr.getvalue() + stderr_buffer.getvalue(),
                        "results": results,
                    }
                )
            )
            return 0

        print(
            json.dumps(
                {
                    "status": "ok",
                    "error": None,
                    "stdout": import_stdout.getvalue() + stdout_buffer.getvalue(),
                    "stderr": import_stderr.getvalue() + stderr_buffer.getvalue(),
                    "results": results,
                }
            )
        )
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """
)
