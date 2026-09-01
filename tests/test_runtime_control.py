import os
import signal
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from fastapi.responses import RedirectResponse
from starlette.requests import Request

import app.runtime_control as runtime_control
import web.admin.routers.runtime_control as runtime_control_router


def create_request() -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/admin/runtime/restart",
        "headers": [],
        "session": {"csrf_token": "expected"}
    })


@pytest.mark.asyncio
async def test_restart_runtime_terminates_current_process_after_delay(monkeypatch) -> None:
    sleep_delays = []
    kill_requests = []

    async def record_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    monkeypatch.setattr(runtime_control.asyncio, "sleep", record_sleep)
    monkeypatch.setattr(runtime_control.os, "kill", lambda process_id, requested_signal: kill_requests.append((process_id, requested_signal)))

    await runtime_control.restart_runtime()

    assert sleep_delays == [runtime_control.RESTART_DELAY_SECONDS]
    assert kill_requests == [(os.getpid(), signal.SIGTERM)]


def test_systemd_restarts_after_clean_dashboard_shutdown() -> None:
    repository_root = Path(runtime_control.__file__).resolve().parents[1]
    service_definition = repository_root / "deploy" / "linux" / "ratsboombot.service"

    service_text = service_definition.read_text(encoding="utf-8")

    assert "Restart=always" in service_text


def test_restart_delay_allows_proxy_response_to_finish() -> None:
    assert runtime_control.RESTART_DELAY_SECONDS >= 5.0


def test_dashboard_restarts_without_navigating_to_interrupted_request() -> None:
    repository_root = Path(runtime_control.__file__).resolve().parents[1]
    dashboard_template = (repository_root / "web" / "templates" / "admin" / "dashboard.html").read_text(encoding="utf-8")

    assert 'event.preventDefault();' in dashboard_template
    assert 'await fetch(restartForm.action' in dashboard_template
    assert 'window.location.href = "/admin";' in dashboard_template


@pytest.mark.asyncio
async def test_restart_route_requires_owner_before_scheduling_restart(monkeypatch) -> None:
    async def reject_non_owner(request: Request):
        return RedirectResponse(url="/admin", status_code=303)

    monkeypatch.setattr(runtime_control_router, "require_owner", reject_non_owner)
    background_tasks = BackgroundTasks()

    response = await runtime_control_router.restart_bot(create_request(), background_tasks, "expected")

    assert response.status_code == 303
    assert background_tasks.tasks == []


@pytest.mark.asyncio
async def test_restart_route_validates_csrf_and_schedules_restart(monkeypatch) -> None:
    validated_tokens = []

    async def allow_owner(request: Request):
        request.state.administrator = None
        return None

    monkeypatch.setattr(runtime_control_router, "require_owner", allow_owner)
    monkeypatch.setattr(runtime_control_router, "validate_csrf_token", lambda request, token: validated_tokens.append(token))
    monkeypatch.setattr(runtime_control_router.templates, "TemplateResponse", lambda **values: values)
    background_tasks = BackgroundTasks()

    response = await runtime_control_router.restart_bot(create_request(), background_tasks, "expected")

    assert validated_tokens == ["expected"]
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is runtime_control_router.restart_runtime
    assert response["name"] == "admin/restarting.html"
