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
    assert '- "release/**"' in workflow
    assert "python -m pytest" in workflow
    assert "needs: validate-uat" in workflow
    assert "vars.UAT_DEPLOY_ENABLED == 'true'" in workflow
    assert "startsWith(github.base_ref, 'release/')" in workflow
    assert "github.event.pull_request.draft == false" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "github.event.pull_request.head.sha || github.sha" in workflow
    assert 'ref: ${{ env.UAT_DEPLOY_SHA }}' in workflow
    assert 'persist-credentials: false' in workflow
    assert 'run: bash "$GITHUB_WORKSPACE/uat-deployment-source/deploy/linux/deploy-uat.sh" "$UAT_DEPLOY_SHA"' in workflow
    assert "cancel-in-progress: false" in workflow
    assert "gh release" not in workflow


def test_uat_service_is_isolated_from_production() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    service = (repository_root / "deploy" / "linux" / "ratsboombot-uat.service").read_text(encoding="utf-8")
    environment = (repository_root / ".env.uat.example").read_text(encoding="utf-8")
    bot = (repository_root / "bot" / "bot.py").read_text(encoding="utf-8")

    assert "WorkingDirectory=/opt/ratsboombot-uat" in service
    assert "EnvironmentFile=/opt/ratsboombot-uat/.env" in service
    assert "ADMIN_PORT=4346" in environment
    assert "TWITCH_ADAPTER_PORT=4344" in environment
    assert "DATABASE_PATH=.data/tokens.db" in environment
    assert "ENVIRONMENT=uat" in environment
    assert "SESSION_COOKIE_DOMAIN=" in environment
    assert "https://uat.ratsboombot.com" in environment
    assert "adapter=web.AiohttpAdapter(host=settings.ADMIN_HOST, port=settings.TWITCH_ADAPTER_PORT)" in bot


def test_uat_deploy_script_only_targets_uat_instance() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    script = (repository_root / "deploy" / "linux" / "deploy-uat.sh").read_text(encoding="utf-8")

    assert 'APP_DIR="/opt/ratsboombot-uat"' in script
    assert 'SERVICE_NAME="ratsboombot-uat"' in script
    assert 'DEPLOY_REF="${1:-uat}"' in script
    assert '[[ ! "$DEPLOY_REF" =~ ^[0-9a-f]{40}$ ]]' in script
    assert 'git fetch --no-tags origin "$DEPLOY_REF"' in script
    assert 'git checkout --detach "$NEW_COMMIT"' in script
    assert 'HEALTH_URL="http://127.0.0.1:4346/health"' in script
    assert 'systemctl restart "$SERVICE_NAME"' in script


def test_validation_commands_cover_feature_packages() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    for relative_path in (
        ".github/workflows/uat.yml",
        "deploy/linux/deploy.sh",
        "deploy/linux/deploy-uat.sh",
    ):
        source = (repository_root / relative_path).read_text(encoding="utf-8")
        commands = [line.split("-m compileall", 1)[1].split() for line in source.splitlines() if "-m compileall" in line]
        assert commands, relative_path
        for command in commands:
            assert {"loyalty", "viewer_queue", "pets", "rpg_minigame"} <= set(command), relative_path
