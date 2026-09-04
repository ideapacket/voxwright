from __future__ import annotations

import subprocess
import sys

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
        "encode_workflow",
        "decode_workflow",
        "workflow_digest",
        "WorkflowCheckpoint",
        "verify_checkpoint",
        "resume_suffix",
        "AuditSummary",
        "audit_entries",
        "summarize_audit",
        "ContextUpdate",
        "context_digest",
        "context_update",
        "RuntimeTurn",
        "runtime_digest",
        "CampaignArtifact",
        "encode_campaign",
        "decode_campaign",
        "PermissionPrompt",
        "permission_prompt_event",
        "metric_bundle_from_dict",
        "encode_registry",
        "decode_registry",
    }
    assert required <= set(voxwright.__all__)
    assert all(hasattr(voxwright, name) for name in voxwright.__all__)
    assert len(voxwright.__all__) == len(set(voxwright.__all__))


def test_public_api_contract_is_sorted_and_exact() -> None:
    assert voxwright.__all__ == sorted(voxwright.__all__)
    assert len(voxwright.__all__) == 89
    assert voxwright.__all__[0] == "AdapterCapabilities"
    assert voxwright.__all__[-1] == "write_workflow"


def test_base_import_does_not_load_the_optional_framework() -> None:
    command = "import sys, voxwright; print('torch' in sys.modules); print(voxwright.__version__)"
    result = subprocess.run(
        [sys.executable, "-c", command], check=True, capture_output=True, text=True
    )
    assert result.stdout.splitlines() == ["False", voxwright.__version__]
