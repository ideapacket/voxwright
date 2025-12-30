from __future__ import annotations

import voxwright


def test_public_api_exports_real_application_mechanics() -> None:
    required = {
        "EventEnvelope",
        "SpokenAdapter",
        "ToolRegistry",
        "TaskFrame",
        "WorkflowDefinition",
        "ToolSandbox",
        "RepairConfig",
        "ContextManager",
        "LatencyBudget",
        "EvaluationRun",
        "application_scenario",
        "parse_call",
        "run_repair",
        "score_runs",
    }
    assert required <= set(voxwright.__all__)
    assert all(hasattr(voxwright, name) for name in voxwright.__all__)
    assert len(voxwright.__all__) == len(set(voxwright.__all__))
