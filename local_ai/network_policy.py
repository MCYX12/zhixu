"""Read macOS browser/system proxy settings without inheriting shell proxy variables."""

import fnmatch
import ipaddress
import re
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit


class NetworkPolicyError(ValueError):
    pass


def read_system_proxy():
    if sys.platform != "darwin":
        return {}
    try:
        result = subprocess.run(
            ["/usr/sbin/scutil", "--proxy"], capture_output=True, text=True, timeout=2, check=True
        )
    except (OSError, subprocess.SubprocessError):
        raise NetworkPolicyError("无法读取系统代理设置，已停止外部请求") from None
    if "<dictionary>" not in result.stdout:
        raise NetworkPolicyError("系统代理设置格式无法识别")
    settings = {}
    for key, value in re.findall(r"^  (\w+) : ([^\n]+)$", result.stdout, re.MULTILINE):
        if not value.startswith("<"):
            settings[key] = value.strip()
    exceptions = re.search(r"ExceptionsList : <array> \{(.*?)\}", result.stdout, re.DOTALL)
    settings["exceptions"] = re.findall(r"\d+ : ([^\n]+)", exceptions[1]) if exceptions else []
    return settings


def bypass(host, settings):
    host = host.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if host == "localhost" or (address and address.is_loopback):
        return True
    if str(settings.get("ExcludeSimpleHostnames")) == "1" and "." not in host:
        return True
    for pattern in settings.get("exceptions", []):
        pattern = pattern.strip().lower()
        if pattern == "<local>" and "." not in host:
            return True
        if "/" in pattern and address:
            try:
                if address in ipaddress.ip_network(pattern, strict=False):
                    return True
            except ValueError:
                continue
        if fnmatch.fnmatchcase(host, pattern):
            return True
    return False


class SystemProxy:
    def __init__(self, reader=read_system_proxy):
        self.reader = reader
        self.lock = threading.Lock()
        self.updated = 0
        self.settings = {}

    def snapshot(self):
        with self.lock:
            if time.monotonic() - self.updated > 1:
                settings = self.reader()  # On failure do not reuse stale or direct settings.
                self.settings = settings
                self.updated = time.monotonic()
            return self.settings

    def for_url(self, url):
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        # These internal endpoints never depend on system proxy/PAC availability.
        if bypass(host, {}):
            return None
        settings = self.snapshot()
        if any(
            str(settings.get(k)) == "1"
            for k in ["ProxyAutoConfigEnable", "ProxyAutoDiscoveryEnable"]
        ):
            raise NetworkPolicyError(
                "当前使用 PAC/自动代理发现，尚未适配；请使用系统 HTTP/HTTPS 代理"
            )
        if bypass(host, settings):
            return None
        name = "HTTPS" if parsed.scheme == "https" else "HTTP"
        if str(settings.get(name + "Enable")) != "1":
            name = "SOCKS"
            if str(settings.get("SOCKSEnable")) != "1":
                return None
        proxy_host = str(settings.get(name + "Proxy", ""))
        try:
            port = int(settings.get(name + "Port", 0))
            if not proxy_host or not 0 < port < 65536 or re.search(r"[\s/@?#]", proxy_host):
                raise ValueError()
            if ":" in proxy_host:
                ipaddress.IPv6Address(proxy_host)
                proxy_host = "[" + proxy_host + "]"
        except ValueError:
            raise NetworkPolicyError("系统代理地址或端口无效，已停止外部请求") from None
        scheme = "socks5h" if name == "SOCKS" else "http"
        return f"{scheme}://{proxy_host}:{port}"

    def describe(self):
        try:
            proxy = self.for_url("https://example.com/")
            return {
                "mode": "system",
                "route": "proxy" if proxy else "direct",
                "label": "跟随系统代理" if proxy else "跟随系统网络（直连）",
            }
        except NetworkPolicyError as error:
            return {"mode": "system", "route": "unavailable", "label": str(error)}


SYSTEM_PROXY = SystemProxy()
