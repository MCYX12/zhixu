import ipaddress
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database: Path
    knowledge_root: Path
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "local-qwen"
    host: str = "127.0.0.1"
    port: int = 9000
    public_origin: str = ""
    trusted_proxy_ips: str = "127.0.0.1"
    max_concurrent: int = 2
    max_queue: int = 6
    queue_timeout: float = 30
    request_timeout: float = 180
    max_input_chars: int = 16000
    max_output_tokens: int = 2048
    token_budget_enabled: bool = False
    chunk_chars: int = 1800
    overlap_chars: int = 200
    max_file_bytes: int = 5 * 1024 * 1024
    top_k: int = 5
    max_context_chars: int = 7000
    allow_web_search: bool = False
    searxng_url: str = "http://127.0.0.1:8888"
    web_allowed_users: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.trusted_proxy_ips, str):
            raise ValueError("trusted_proxy_ips must be explicit IP addresses")
        for address in self.trusted_proxy_ips.split(","):
            if address.strip():
                ipaddress.ip_address(address.strip())
        if self.public_origin:
            public = urlsplit(self.public_origin)
            if (
                public.scheme != "https"
                or not public.hostname
                or public.username is not None
                or public.password is not None
                or public.path
                or public.query
                or public.fragment
                or public.port not in (None, 443)
            ):
                raise ValueError(
                    "public_origin must be an HTTPS origin without path or credentials"
                )
        if type(self.token_budget_enabled) is not bool:
            raise ValueError("token_budget_enabled must be a boolean")
        if type(self.allow_web_search) is not bool:
            raise ValueError("allow_web_search must be a boolean")
        if not isinstance(self.web_allowed_users, tuple) or any(
            not isinstance(user, str) or not user.strip() for user in self.web_allowed_users
        ):
            raise ValueError("web_allowed_users must contain explicit account IDs")
        url = urlsplit(self.base_url)
        try:
            local = ipaddress.ip_address(url.hostname or "").is_loopback
        except ValueError:
            local = False
        if not local or url.scheme != "http" or url.username or url.query or url.fragment:
            raise ValueError("Local backend must be an explicit loopback HTTP address")
        search_url = urlsplit(self.searxng_url)
        try:
            search_local = ipaddress.ip_address(search_url.hostname or "").is_loopback
        except ValueError:
            search_local = False
        if (
            not search_local
            or search_url.scheme != "http"
            or search_url.username
            or search_url.query
            or search_url.fragment
            or search_url.path not in {"", "/"}
        ):
            raise ValueError("SearXNG must use an explicit loopback HTTP origin")
        if self.allow_web_search and not self.web_allowed_users:
            raise ValueError("Web search requires an explicit user allowlist")
        for name in (
            "max_concurrent",
            "queue_timeout",
            "request_timeout",
            "max_input_chars",
            "max_output_tokens",
            "chunk_chars",
            "max_file_bytes",
            "top_k",
            "max_context_chars",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_queue < 0 or not 0 <= self.overlap_chars < self.chunk_chars:
            raise ValueError("Invalid queue or chunk overlap settings")


def load_settings(path: str | None = None) -> Settings:
    default = ROOT / "config/local.toml"
    if not default.exists():
        default = ROOT / "config/example.toml"
    config = Path(path or os.environ.get("LOCAL_AI_CONFIG", default))
    with config.open("rb") as f:
        raw = tomllib.load(f)
    policy = raw.get("policy", {})
    if any(type(value) is not bool for value in policy.values()):
        raise ValueError("Policy flags must be booleans")
    if not isinstance(raw.get("web", {}).get("allowed_users", []), list):
        raise ValueError("web.allowed_users must be a list")
    if any(v for k, v in policy.items() if k != "allow_web_search"):
        raise ValueError("Cloud inference and private context export are not implemented")
    server = raw.get("server", {})
    model = raw.get("model", {})
    knowledge = dict(raw.get("knowledge", {}))
    root = knowledge.pop("root", "examples/knowledge")
    database = server.get("database", "data/state.sqlite3")
    return Settings(
        **(
            server
            | {
                "database": (ROOT / database).resolve(),
                "knowledge_root": (ROOT / root).resolve(),
                "model": model.get("name", "local-qwen"),
                "base_url": model.get("base_url", "http://127.0.0.1:8080/v1"),
                "allow_web_search": policy.get("allow_web_search", False),
                "searxng_url": raw.get("web", {}).get("searxng_url", "http://127.0.0.1:8888"),
                "web_allowed_users": tuple(raw.get("web", {}).get("allowed_users", [])),
            }
            | knowledge
        )
    )
