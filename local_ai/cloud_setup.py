"""Offline cloud preflight. Configuration never implies permission to send data."""

import ipaddress
import math
import os
import re
import stat
import tomllib
from pathlib import Path
from urllib.parse import urlsplit


def inspect_profile(path: Path) -> dict:
    result = {
        "configured": False,
        "inference_enabled": False,
        "network_checked": False,
        "private_context_export": False,
        "issues": [],
    }
    issues = result["issues"]
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, ValueError):
        issues.append("云端配置文件缺失或格式错误")
        return result
    if set(raw) - {
        "provider",
        "model",
        "base_url",
        "key_file",
        "allowed_users",
        "max_output_tokens",
        "daily_budget",
        "currency",
        "input_price_per_million",
        "output_price_per_million",
        "context_scope",
    }:
        issues.append("存在未知配置项；密钥必须存放在独立文件，不能直接写入配置")
    for field in ("provider", "model"):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
            issues.append(f"缺少或无效的 {field}")
    try:
        url = urlsplit(raw.get("base_url", ""))
        host = url.hostname or ""
        try:
            public = ipaddress.ip_address(host).is_global
        except ValueError:
            public = "." in host and not host.endswith((".local", ".localhost"))
        if not (
            url.scheme == "https"
            and public
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and url.port in (None, 443)
        ):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        issues.append("云端地址必须是固定的公网 HTTPS 地址，不含凭据、查询或非标准端口")
    users = raw.get("allowed_users")
    if (
        not isinstance(users, list)
        or not users
        or any(not isinstance(u, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", u) for u in users)
    ):
        issues.append("必须指定云端账号白名单")
    if raw.get("context_scope") != "current_question":
        issues.append("当前接入准备仅支持本次问题；历史和文档外发尚未实现")
    if type(raw.get("max_output_tokens")) is not int or not 1 <= raw["max_output_tokens"] <= 32768:
        issues.append("单次输出上限须为 1～32768 tokens")
    for field in ("daily_budget", "input_price_per_million", "output_price_per_million"):
        value = raw.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            issues.append(f"须填写正数 {field}，不能在价格或预算未知时启用")
    if raw.get("currency") not in {"CNY", "USD"}:
        issues.append("预算和价格须使用相同币种 CNY 或 USD")
    try:
        filename = raw.get("key_file")
        if not isinstance(filename, str) or not filename:
            raise ValueError()
        key_path = path.parent / filename
        fd = os.open(key_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise ValueError()
            key = handle.read(8193).strip()
            if not key or len(key) > 8192 or any(c < 33 or c > 126 for c in key):
                raise ValueError()
    except (OSError, ValueError, TypeError):
        issues.append("密钥文件缺失或不安全：须为当前用户拥有的 0600 普通文件，不能是符号链接")
    result["configured"] = not issues
    result["next_step"] = (
        "配置校验通过后仍须完成服务商适配、费用控制和真实调用验收，当前不会发送请求"
    )
    return result
