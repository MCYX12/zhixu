"""Start the installed local workspace without downloads or duplicate services."""

import argparse
import fcntl
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_ai.config import load_settings  # noqa: E402


@dataclass
class Service:
    name: str
    url: str
    command: list[str]
    log: Path
    kind: str


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def healthy(service):
    # Local health checks must not inherit VPN/shell proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(service.url, timeout=2) as response:
            data = response.read(65537)
            if len(data) > 65536:
                return False
            if service.kind == "search":
                return data.strip() == b"OK"
            payload = json.loads(data)
            return (
                isinstance(payload, dict)
                and payload.get("status") == "ok"
                and (service.kind != "gateway" or "external_access" in payload)
            )
    except (OSError, ValueError, urllib.error.URLError):
        return False


def occupied(service):
    url = urlsplit(service.url)
    try:
        with socket.create_connection((url.hostname, url.port or 80), timeout=1):
            return True
    except OSError:
        return False


def ensure(service, timeout=180):
    if healthy(service):
        print(f"✓ {service.name}已就绪，复用现有服务", flush=True)
        return
    if occupied(service):
        raise RuntimeError(
            f"{service.name}端口已占用但健康检查未通过；不会启动重复进程。请检查 {service.log}"
        )
    if not service.command:
        raise RuntimeError("未找到 llama-server，请设置 LLAMA_SERVER_BIN 或 --model-binary")
    service.log.parent.mkdir(parents=True, exist_ok=True)
    with service.log.open("ab") as log:
        process = subprocess.Popen(
            service.command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print(f"正在启动{service.name}，日志：{service.log}", flush=True)
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"{service.name}启动退出（{process.returncode}），请检查 {service.log}"
            )
        if healthy(service):
            print(f"✓ {service.name}已就绪", flush=True)
            return
        if time.monotonic() - last_report >= 10:
            print(f"仍在等待{service.name}就绪…", flush=True)
            last_report = time.monotonic()
        time.sleep(0.5)
    # Stop only the process created here; never stop another service on its port.
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    raise RuntimeError(f"{service.name}启动超时，已停止本次创建的进程。请检查 {service.log}")


def services(binary=None):
    settings = load_settings()
    if (settings.host, settings.port, settings.base_url, settings.searxng_url.rstrip("/")) != (
        "127.0.0.1",
        9000,
        "http://127.0.0.1:8080/v1",
        "http://127.0.0.1:8888",
    ):
        raise RuntimeError(
            "一键启动目前适用于默认回环端口 8080/8888/9000；自定义配置请按 README 分别启动"
        )
    python = ROOT / ".venv/bin/python"
    if not python.exists():
        raise RuntimeError("缺少本地 Python 环境，请先运行 uv sync --locked")
    config = ROOT / "config/launcher.local.json"
    saved = json.loads(config.read_text()) if config.exists() else {}
    binary = (
        binary
        or os.environ.get("LLAMA_SERVER_BIN")
        or saved.get("model_binary")
        or shutil.which("llama-server")
    )
    model_command = (
        [str(python), str(ROOT / "scripts/start_model.py"), "--binary", str(binary)]
        if binary
        else []
    )
    result = [
        Service(
            "本地模型",
            "http://127.0.0.1:8080/health",
            model_command,
            ROOT / "data/model.log",
            "model",
        )
    ]
    if settings.allow_web_search:
        result.append(
            Service(
                "搜索服务",
                "http://127.0.0.1:8888/healthz",
                [str(python), str(ROOT / "scripts/start_search.py")],
                ROOT / "data/search.log",
                "search",
            )
        )
    result.append(
        Service(
            "工作台",
            "http://127.0.0.1:9000/health",
            [str(python), "-m", "local_ai", "serve"],
            ROOT / "data/gateway.log",
            "gateway",
        )
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-binary")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--status", action="store_true", help="只检查服务，不启动进程")
    args = parser.parse_args()
    try:
        items = services(args.model_binary)
        if args.status:
            states = [healthy(item) for item in items]
            for item, ready in zip(items, states):
                print(f"{item.name}：{'就绪' if ready else '未就绪'}")
            return 0 if all(states) else 1
        (ROOT / "data").mkdir(exist_ok=True)
        with (ROOT / "data/workspace-start.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("另一个启动窗口正在工作，请等待它完成") from None
            for item in items:
                ensure(item)
        print("工作台已就绪：http://127.0.0.1:9000/", flush=True)
        print("关闭此窗口不会停止服务；搜索就绪仅表示本机服务可用，不代表外部引擎始终可用。")
        if not args.no_open:
            subprocess.run(["/usr/bin/open", "http://127.0.0.1:9000/"], check=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"启动未完成：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
