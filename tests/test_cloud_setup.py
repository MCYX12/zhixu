import json

import pytest

from local_ai.cloud_setup import inspect_profile


@pytest.fixture
def profile(tmp_path):
    key = tmp_path / "provider.key"
    key.write_text("test-secret-never-report")
    key.chmod(0o600)
    path = tmp_path / "cloud.toml"
    path.write_text("""provider = "test"
model = "test-model"
base_url = "https://api.example.com/v1"
key_file = "provider.key"
allowed_users = ["owner"]
context_scope = "current_question"
max_output_tokens = 2048
currency = "CNY"
daily_budget = 5
input_price_per_million = 1
output_price_per_million = 2
""")
    return path


def test_valid_profile_does_not_enable_network_or_expose_key(profile):
    result = inspect_profile(profile)
    assert result["configured"]
    assert not result["inference_enabled"]
    assert not result["network_checked"]
    assert "test-secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "address",
    [
        "http://api.example.com",
        "https://127.0.0.1",
        "https://10.0.0.1",
        "https://user:secret@api.example.com",
        "https://api.example.com?key=secret",
        "https://api.example.com:8443",
        "https://[::1]",
    ],
)
def test_invalid_endpoint(profile, address):
    profile.write_text(profile.read_text().replace("https://api.example.com/v1", address))
    result = inspect_profile(profile)
    assert not result["configured"]
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize("replacement", ["0", "-1", "nan", "inf", "true"])
def test_budget_fail_closed(profile, replacement):
    profile.write_text(
        profile.read_text().replace("daily_budget = 5", "daily_budget = " + replacement)
    )
    assert not inspect_profile(profile)["configured"]


def test_key_permissions_and_symlink(profile):
    key = profile.parent / "provider.key"
    key.chmod(0o644)
    assert not inspect_profile(profile)["configured"]
    key.chmod(0o600)
    moved = key.with_name("real.key")
    key.rename(moved)
    key.symlink_to(moved)
    assert not inspect_profile(profile)["configured"]


@pytest.mark.parametrize(
    "old,new",
    [
        ('allowed_users = ["owner"]', "allowed_users = []"),
        ("current_question", "history"),
        ('provider = "test"', 'api_key = "test-secret"'),
    ],
)
def test_missing_authorization_and_inline_secret(profile, old, new):
    profile.write_text(profile.read_text().replace(old, new))
    result = inspect_profile(profile)
    assert not result["configured"]
    assert "test-secret" not in json.dumps(result)


def test_missing_file(tmp_path):
    assert not inspect_profile(tmp_path / "missing.toml")["configured"]
