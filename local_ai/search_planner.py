"""Local-only public query rewriting; never accepts document or conversation context."""

import asyncio
import json

import httpx


async def alternate_query(settings, query):
    try:
        async with asyncio.timeout(15):
            async with httpx.AsyncClient(
                base_url=settings.base_url.rstrip("/") + "/", trust_env=False, timeout=14
            ) as client:
                response = await client.post(
                    "chat/completions",
                    json={
                        "model": settings.model,
                        "stream": False,
                        "max_tokens": 96,
                        "temperature": 0,
                        "chat_template_kwargs": {"enable_thinking": False},
                        "messages": [
                            {
                                "role": "system",
                                "content": '你是搜索词编辑器。将用户当前公开问题改写成一条简短搜索查询，保留核心实体和时间要求，去掉礼貌用语与回答格式要求。中文实体不得改名；GitHub或编程主题必须使用英文关键词（例如机器人译为robotics），其他中文专名保持原文。不得回答问题或编造事实。只输出JSON对象，格式：{"query":"关键词"}。',
                            },
                            {"role": "user", "content": query[:300]},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                value = json.loads(content)["query"]
                if (
                    isinstance(value, str)
                    and 2 <= len(value.strip()) <= 180
                    and not any(ord(c) < 32 for c in value)
                ):
                    return value.strip()
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, IndexError):
        pass
    return None
