from pathlib import Path


def test_master_release_workflow_deploys_with_raspberry_pi_runner() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    workflow = (repository_root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "deploy-production:" in workflow
    assert "needs: publish-release" in workflow
    assert "- self-hosted" in workflow
    assert "- ratsboombot" in workflow
    assert "run: /opt/ratsboombot/deploy/linux/deploy.sh" in workflow



def test_uat_workflow_validates_before_guarded_deployment() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    workflow = (repository_root / ".github" / "workflows" / "uat.yml").read_text(encoding="utf-8")

    assert "- uat" in workflow
    assert "python -m pytest" in workflow
    assert "needs: validate-uat" in workflow
    assert "vars.UAT_DEPLOY_ENABLED == 'true'" in workflow
    assert "run: /opt/ratsboombot-uat/deploy/linux/deploy-uat.sh" in workflow
    assert "gh release" not in workflow


def test_uat_service_is_isolated_from_production() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    service = (repository_root / "deploy" / "linux" / "ratsboombot-uat.service").read_text(encoding="utf-8")
    environment = (repository_root / ".env.uat.example").read_text(encoding="utf-8")

    assert "WorkingDirectory=/opt/ratsboombot-uat" in service
    assert "EnvironmentFile=/opt/ratsboombot-uat/.env" in service
    assert "ADMIN_PORT=4346" in environment
    assert "DATABASE_PATH=.data/tokens.db" in environment
    assert "ENVIRONMENT=uat" in environment
    assert "SESSION_COOKIE_DOMAIN=" in environment
    assert "https://uat.ratsboombot.com" in environment


def test_uat_deploy_script_only_targets_uat_instance() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    script = (repository_root / "deploy" / "linux" / "deploy-uat.sh").read_text(encoding="utf-8")

    assert 'APP_DIR="/opt/ratsboombot-uat"' in script
    assert 'SERVICE_NAME="ratsboombot-uat"' in script
    assert 'DEPLOY_BRANCH="uat"' in script
    assert 'HEALTH_URL="http://127.0.0.1:4346/health"' in script
    assert 'systemctl restart "$SERVICE_NAME"' in script
