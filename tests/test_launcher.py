import sys

import pytest

from scripts import start_workspace as launcher


@pytest.fixture
def service(tmp_path):
    return launcher.Service(
        "测试服务", "http://127.0.0.1:1/health", [], tmp_path / "service.log", "model"
    )


def test_reuses_ready_service_without_spawning(monkeypatch, service):
    monkeypatch.setattr(launcher, "healthy", lambda _: True)
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda *a, **kw: pytest.fail("duplicate process")
    )
    launcher.ensure(service)


def test_occupied_unhealthy_port_never_spawns(monkeypatch, service):
    monkeypatch.setattr(launcher, "healthy", lambda _: False)
    monkeypatch.setattr(launcher, "occupied", lambda _: True)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **kw: pytest.fail("occupied port"))
    with pytest.raises(RuntimeError, match="端口已占用"):
        launcher.ensure(service)


def test_startup_exit_reported_and_output_goes_to_log(monkeypatch, service):
    monkeypatch.setattr(launcher, "healthy", lambda _: False)
    monkeypatch.setattr(launcher, "occupied", lambda _: False)
    service.command = [sys.executable, "-c", "print('startup failed');raise SystemExit(3)"]
    with pytest.raises(RuntimeError, match="启动退出（3）"):
        launcher.ensure(service, timeout=5)
    assert "startup failed" in service.log.read_text()


def test_timeout_stops_only_created_process(monkeypatch, service):
    monkeypatch.setattr(launcher, "healthy", lambda _: False)
    monkeypatch.setattr(launcher, "occupied", lambda _: False)
    created = []
    popen = launcher.subprocess.Popen

    def spawn(*args, **kwargs):
        process = popen(*args, **kwargs)
        created.append(process)
        return process

    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    service.command = [sys.executable, "-c", "import time;time.sleep(30)"]
    with pytest.raises(RuntimeError, match="启动超时"):
        launcher.ensure(service, timeout=0.05)
    assert len(created) == 1 and created[0].poll() is not None
