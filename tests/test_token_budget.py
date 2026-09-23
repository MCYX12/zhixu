import json
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from local_ai.api import create_app
from local_ai.config import Settings
from local_ai.token_budget import BudgetUnavailable, TokenBudget, check_budget


@pytest.mark.parametrize("prompt,output,fits", [(7000, 1160, True), (7001, 1160, False)])
def test_budget_includes_output_and_reserve(prompt, output, fits):
    assert TokenBudget(prompt, output, 8192).fits is fits


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("count,expected", [(100, 200), (8000, 413), (None, 503)])
def test_budget_gates_generation_and_releases_lease(tmp_path, stream, count, expected):
    calls = []
    settings = Settings(tmp_path / "db", tmp_path, token_budget_enabled=True)

    def backend(request):
        calls.append(request)
        if request.url.path == "/props":
            return httpx.Response(200, json={"default_generation_settings": {"n_ctx": 8192}})
        if request.url.path == "/v1/chat/completions/input_tokens":
            if count is None:
                return httpx.Response(404)
            return httpx.Response(200, json={"input_tokens": count})
        assert request.url.path == "/v1/chat/completions"
        if stream:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content='data: {"choices":[{"delta":{"content":"你好"}}]}\n\ndata: [DONE]\n\n',
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "你好"}}]}
        )

    app = create_app(settings, httpx.MockTransport(backend))
    key = app.state.store.create_user("test", [])
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer " + key},
            json={
                "model": "local",
                "messages": [{"role": "user", "content": "你好"}],
                "max_tokens": 512,
                "stream": stream,
            },
        )
        assert r.status_code == expected
        completions = [c for c in calls if c.url.path == "/v1/chat/completions"]
        assert len(completions) == (1 if expected == 200 else 0)
        assert app.state.queue.active == 0 and app.state.queue.waiting == 0
        if expected == 200:
            assert r.headers["x-local-ai-prompt-tokens"] == "100"
            assert json.loads(calls[1].content) == json.loads(completions[0].content)


@pytest.mark.parametrize("context,prompt", [(True, 20), (8192, -1), (8192, "20"), (None, 20)])
async def test_invalid_backend_budget_never_uses_estimate(context, prompt):
    def backend(request):
        return httpx.Response(
            200,
            json={"default_generation_settings": {"n_ctx": context}}
            if request.url.path == "/props"
            else {"input_tokens": prompt},
        )

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8080/v1/", transport=httpx.MockTransport(backend)
    ) as client:
        with pytest.raises(BudgetUnavailable):
            await check_budget(client, {"messages": [], "max_tokens": 512})


def test_budget_config_must_be_boolean(tmp_path):
    with pytest.raises(ValueError):
        replace(Settings(tmp_path / "db", tmp_path), token_budget_enabled="false")
