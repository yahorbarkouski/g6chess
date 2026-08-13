"""Repository-level safety checks for release workflows."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[4]


def test_modal_deployment_is_manual_and_does_not_overwrite_runtime_secrets() -> None:
    workflow = (REPOSITORY_ROOT / ".github/workflows/deploy-modal.yml").read_text(encoding="utf-8")

    trigger_block, _separator, jobs_block = workflow.partition("\npermissions:")

    assert "workflow_dispatch:" in trigger_block
    assert "push:" not in trigger_block
    assert "modal secret create" not in jobs_block
    assert "--force" not in jobs_block
