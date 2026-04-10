from legacygym import LegacygymAction
from legacygym.server.environment import LegacygymEnvironment


def test_environment_supports_replace_test_submit_flow():
    env = LegacygymEnvironment()
    reset = env.reset(task_id="array_length")
    assert reset.task.task_id == "array_length"
    assert not reset.done
    assert reset.server_info["task_id"] == "array_length"
    assert "array_length" in reset.server_info["available_task_ids"]
    assert "registry_signature" in reset.metadata
    assert "reward_weights" in reset.metadata
    assert "score_weights" in reset.metadata

    replace = env.step(
        LegacygymAction(
            action_type="replace_solution",
            code="""def array_length(items: list[str]) -> int:\n    \"\"\"Return the number of items.\"\"\"\n    return len(items)\n""",
        )
    )
    assert not replace.done
    assert replace.attempt.has_solution

    visible = env.step(LegacygymAction(action_type="run_visible_tests"))
    assert visible.last_grading is not None
    assert visible.last_grading.visible_passed == visible.last_grading.visible_total

    submitted = env.step(LegacygymAction(action_type="submit"))
    assert submitted.done
    assert submitted.last_grading is not None
    assert submitted.last_grading.final_score > 0.9
    assert env.state.done
