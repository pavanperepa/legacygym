from legacygym.models import ExecutionResult, GradingResult
from legacygym.server.graders import MinimalRewardAdapter


def test_reward_adapter_is_small_and_pluggable():
    adapter = MinimalRewardAdapter()
    execution = ExecutionResult(status="ok", function_name="array_length")
    grading = GradingResult(
        mode="visible",
        correctness_score=1.0,
        maintainability_score=1.0,
        safety_score=1.0,
        final_score=1.0,
        visible_passed=2,
        visible_total=2,
        hidden_passed=0,
        hidden_total=0,
        feedback=[],
        test_results=[],
    )

    reward, components = adapter.compute(
        action_type="run_visible_tests",
        previous_best_visible_score=0.0,
        current_best_visible_score=1.0,
        current_visible_score=1.0,
        execution=execution,
        grading=grading,
        done=False,
        step_count=1,
        max_steps=6,
    )

    assert reward > 0
    assert any(component.name == "visible_progress_bonus" for component in components)
