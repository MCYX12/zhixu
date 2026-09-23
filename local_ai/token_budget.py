"""Preflight budgets using the running llama.cpp chat parser and tokenizer."""

import asyncio
from dataclasses import dataclass

import httpx


class BudgetUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class TokenBudget:
    prompt: int
    output: int
    context: int
    reserve: int = 32

    @property
    def fits(self):
        return self.prompt + self.output + self.reserve <= self.context


async def check_budget(client, payload):
    try:
        # Uses exactly the same messages and template kwargs as the completion.
        # Both requests share the existing loopback-only, no-proxy HTTP client.
        async with asyncio.timeout(8):
            props = await client.get(client.base_url.copy_with(path="/props"), timeout=4)
            props.raise_for_status()
            context = props.json()["default_generation_settings"]["n_ctx"]
            counted = await client.post("chat/completions/input_tokens", json=payload, timeout=4)
            counted.raise_for_status()
            prompt = counted.json()["input_tokens"]
        if type(context) is not int or context <= 0 or type(prompt) is not int or prompt < 1:
            raise ValueError("invalid tokenizer response")
        return TokenBudget(prompt, payload["max_tokens"], context)
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError) as error:
        raise BudgetUnavailable(
            "无法校验本地模型上下文预算，请检查模型服务；本次未启动生成"
        ) from error
