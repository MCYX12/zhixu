import json

import httpx
import pytest

from local_ai.config import Settings
from local_ai.search_planner import alternate_query


@pytest.mark.parametrize(
    "content,expected",
    [
        ('{"query":"robotics github"}', "robotics github"),
        ("not json", None),
        ('{"query":[]}', None),
    ],
)
async def test_local_planner_boundaries(monkeypatch, tmp_path, content, expected):
    original = httpx.AsyncClient
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    def client(**kwargs):
        assert kwargs["trust_env"] is False
        return original(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr("local_ai.search_planner.httpx.AsyncClient", client)
    result = await alternate_query(Settings(tmp_path / "db", tmp_path), "公开问题")
    assert result == expected
    assert len(calls) == 1 and calls[0].url.host == "127.0.0.1"
    payload = json.loads(calls[0].content)
    assert len(payload["messages"]) == 2 and payload["messages"][1]["content"] == "公开问题"
    assert payload["max_tokens"] == 96
