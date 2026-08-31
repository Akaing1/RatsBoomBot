from pathlib import Path


def test_master_release_workflow_deploys_with_raspberry_pi_runner() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    workflow = (repository_root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "deploy-production:" in workflow
    assert "needs: publish-release" in workflow
    assert "- self-hosted" in workflow
    assert "- ratsboombot" in workflow
    assert "run: /opt/ratsboombot/deploy/linux/deploy.sh" in workflow
