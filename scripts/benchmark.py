"""Real gateway smoke benchmark; no fabricated token throughput or stable p95 claims."""

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx


async def measure(base_url, key, mode, question):
    start = time.perf_counter()
    first = None
    text = ""
    done = False
    error = None
    async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
        async with client.stream(
            "POST",
            base_url + "/v1/chat/completions",
            headers={"Authorization": "Bearer " + key},
            json={
                "model": mode,
                "messages": [{"role": "user", "content": question}],
                "stream": True,
                "max_tokens": 128,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                chunk = json.loads(data)
                if chunk.get("error"):
                    error = chunk["error"]
                content = (chunk.get("choices") or [{}])[0].get("delta", {}).get(
                    "content", ""
                ) or ""
                if content and first is None:
                    first = time.perf_counter() - start
                text += content
    return {
        "mode": mode,
        "first_content_seconds": first,
        "total_seconds": time.perf_counter() - start,
        "output_characters": len(text),
        "completed": done and not error,
        "error": error,
        "answer": text,
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:9000")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    key = args.key_file.read_text().strip()
    rows = []
    for mode, question in [
        ("local", "用一句话解释 PID 控制。"),
        ("knowledge", "根据资料，实验记录编号是什么？"),
    ]:
        rows.append(await measure(args.base_url, key, mode, question))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"kind": "two-request-smoke-not-p95", "results": rows}, ensure_ascii=False, indent=2
        )
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
