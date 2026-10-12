"""Client for Jan's local OpenAI-compatible API (llama.cpp backend).

Configure with environment variables:
    JAN_URL      base URL including /v1 (default http://127.0.0.1:1337/v1)
    JAN_API_KEY  only if an API key is set in Jan → Settings → Local API Server
"""
from __future__ import annotations

import os

import numpy as np
import requests

JAN_URL = os.getenv("JAN_URL", "http://127.0.0.1:1337/v1").rstrip("/")

# Method key -> Jan model id (the id Jan lists under /v1/models).
JAN_MODEL_MAP = {
    "llama": os.getenv("JAN_LLAMA_MODEL", "bartowski/Llama-3.2-3B-Instruct-Q4_K_M"),
    "qwen": os.getenv("JAN_QWEN_EMBED_MODEL", "Qwen/Qwen3-Embedding-8B-Q4_K_M"),
    "embeddinggemma": os.getenv("JAN_GEMMA_EMBED_MODEL", "unsloth/embeddinggemma-300M-BF16"),
}


class JanError(RuntimeError):
    pass


def _headers() -> dict:
    key = os.getenv("JAN_API_KEY")
    return {"Authorization": f"Bearer {key}"} if key else {}


def _post(path: str, payload: dict, timeout: float) -> dict:
    try:
        resp = requests.post(f"{JAN_URL}{path}", json=payload, headers=_headers(), timeout=timeout)
    except requests.RequestException as e:
        raise JanError(f"{path}: {e}") from e
    if resp.status_code != 200:
        raise JanError(f"{path}: HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def list_models() -> list[str]:
    try:
        resp = requests.get(f"{JAN_URL}/models", headers=_headers(), timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise JanError(f"/models: {e}") from e
    return [m["id"] for m in resp.json().get("data", [])]


def chat(model: str, prompt: str, max_tokens: int, seed: int = 0, top_logprobs: int = 0,
         timeout: float = 600) -> dict:
    """Greedy (temperature 0) single-turn completion.

    Returns {'text', 'prompt_tokens', 'top_logprobs'}; 'top_logprobs' is the list of
    {token, logprob} alternatives for the first generated token, or None if the
    server did not return them.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "seed": seed,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if top_logprobs:
        payload.update(logprobs=True, top_logprobs=top_logprobs)
    data = _post("/chat/completions", payload, timeout)
    choice = data["choices"][0]
    content = ((choice.get("logprobs") or {}).get("content")) or []
    usage = data.get("usage") or {}
    return {"text": choice["message"]["content"] or "",
            "prompt_tokens": usage.get("prompt_tokens"),
            "top_logprobs": content[0].get("top_logprobs") if content else None}


def embed(model: str, texts: list[str], batch_size: int = 32, timeout: float = 600) -> np.ndarray:
    out = []
    for start in range(0, len(texts), batch_size):
        data = _post("/embeddings", {"model": model, "input": texts[start:start + batch_size]}, timeout)
        rows = sorted(data["data"], key=lambda d: d["index"])
        out.extend(r["embedding"] for r in rows)
    return np.asarray(out, dtype=np.float32)
