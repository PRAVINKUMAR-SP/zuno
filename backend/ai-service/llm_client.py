"""OpenAI-compatible HTTP client for remote llama-server inference."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Generator

import httpx

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://10.32.13.83:8000").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "/home/opffarmy/ZERO/models/Qwen3-4B-Q4_K_M.gguf")
CONNECT_TIMEOUT = float(os.getenv("LLM_CONNECT_TIMEOUT", "6.0"))
READ_TIMEOUT = float(os.getenv("LLM_READ_TIMEOUT", "60.0"))

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def get_llm_client() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None or _client.is_closed:
            _client = httpx.Client(
                timeout=httpx.Timeout(
                    connect=CONNECT_TIMEOUT,
                    read=READ_TIMEOUT,
                    write=10.0,
                    pool=10.0,
                ),
                limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
            )
        return _client


_health_cache = {"data": None, "ts": 0.0}

def check_server_health() -> dict:
    """Check connectivity to remote llama-server and list loaded model."""
    now = time.time()
    if _health_cache["data"] and (now - _health_cache["ts"] < 3.0):
        return _health_cache["data"]

    # Fast TCP probe first (0.3s) to avoid HTTP timeouts when port 8000 is down
    try:
        from urllib.parse import urlparse
        import socket
        parsed = urlparse(LLM_BASE_URL)
        host = parsed.hostname or "10.32.13.83"
        port = parsed.port or 8000
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            s.connect((host, port))
    except Exception:
        result = {
            "status": "down",
            "ready": False,
            "url": LLM_BASE_URL,
            "error": "port unreachable",
        }
        _health_cache["data"] = result
        _health_cache["ts"] = now
        return result

    client = get_llm_client()
    url = f"{LLM_BASE_URL}/v1/models"
    try:
        t0 = time.perf_counter()
        resp = client.get(url, timeout=3.0)
        ping_ms = round((time.perf_counter() - t0) * 1000, 1)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", []) or data.get("models", [])
            model_id = models[0].get("id") or models[0].get("name") if models else LLM_MODEL
            result = {
                "status": "ok",
                "ready": True,
                "url": LLM_BASE_URL,
                "model": os.path.basename(str(model_id)),
                "pingMs": ping_ms,
            }
            _health_cache["data"] = result
            _health_cache["ts"] = now
            return result
        result = {
            "status": "degraded",
            "ready": False,
            "url": LLM_BASE_URL,
            "httpCode": resp.status_code,
            "pingMs": ping_ms,
        }
        _health_cache["data"] = result
        _health_cache["ts"] = now
        return result
    except Exception as exc:
        result = {
            "status": "down",
            "ready": False,
            "url": LLM_BASE_URL,
            "error": str(exc),
        }
        _health_cache["data"] = result
        _health_cache["ts"] = now
        return result


def stream_completion(
    prompt: str,
    max_tokens: int = 150,
    temperature: float = 0.5,
    stop: list[str] | None = None,
    cancel_event: threading.Event | None = None,
) -> Generator[tuple[str, str | None], None, None]:
    """Stream token deltas from remote llama-server /v1/completions endpoint.

    Yields (delta_text, finish_reason).
    """
    client = get_llm_client()
    url = f"{LLM_BASE_URL}/v1/completions"
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.8,
        "top_k": 20,
        "stop": stop or ["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
        "stream": True,
    }

    req = client.build_request("POST", url, json=payload)
    resp = client.send(req, stream=True)
    try:
        if resp.status_code != 200:
            error_body = resp.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Remote LLM returned HTTP {resp.status_code}: {error_body}")

        for line in resp.iter_lines():
            if cancel_event is not None and cancel_event.is_set():
                break
            if not line:
                continue
            if line.startswith("data: "):
                body = line[6:].strip()
                if body == "[DONE]":
                    break
                try:
                    data = json.loads(body)
                    choice = data["choices"][0]
                    delta = choice.get("text", "")
                    finish_reason = choice.get("finish_reason")
                    yield delta, finish_reason
                    if finish_reason is not None and finish_reason != "":
                        break
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
    finally:
        resp.close()


def generate_completion(
    prompt: str,
    max_tokens: int = 150,
    temperature: float = 0.5,
    stop: list[str] | None = None,
) -> str:
    """Synchronous single completion from remote llama-server."""
    client = get_llm_client()
    url = f"{LLM_BASE_URL}/v1/completions"
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.8,
        "top_k": 20,
        "stop": stop or ["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
        "stream": False,
    }
    resp = client.post(url, json=payload, timeout=READ_TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"Remote LLM returned HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    return data["choices"][0].get("text", "")

