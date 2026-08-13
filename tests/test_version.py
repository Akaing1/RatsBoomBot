from config import version


def test_deployment_stamp_reads_deployed_value(tmp_path, monkeypatch) -> None:
    deployment_stamp_path = tmp_path / "deployment.txt"
    deployment_stamp_path.write_text("08.12.2026-v5.4.2\n", encoding="utf-8")
    monkeypatch.setattr(version, "DEPLOYMENT_STAMP_PATH", deployment_stamp_path)

    assert version.get_deployment_stamp() == "08.12.2026-v5.4.2"


def test_deployment_stamp_falls_back_to_app_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(version, "DEPLOYMENT_STAMP_PATH", tmp_path / "missing.txt")

    assert version.get_deployment_stamp() == f"v{version.APP_VERSION}"