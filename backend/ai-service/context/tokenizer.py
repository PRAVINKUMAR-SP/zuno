"""Token counting and prompt formatting matching Qwen3-4B on llama-server."""

from __future__ import annotations

import os
import threading
from typing import Any

import httpx

_tokenizer_lock = threading.Lock()
_tokenizer_instance: Any = None
_LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://10.32.13.83:8000").rstrip("/")


def get_tokenizer():
    """Load or return the cached Qwen tokenizer singleton with Qwen3 special tokens."""
    global _tokenizer_instance
    if _tokenizer_instance is not None:
        return _tokenizer_instance

    with _tokenizer_lock:
        if _tokenizer_instance is not None:
            return _tokenizer_instance
        try:
            from transformers import AutoTokenizer
            tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct", local_files_only=True)
            tok.add_tokens(["<think>", "</think>"], special_tokens=True)
            _tokenizer_instance = tok
        except Exception:
            try:
                from transformers import AutoTokenizer
                tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")
                tok.add_tokens(["<think>", "</think>"], special_tokens=True)
                _tokenizer_instance = tok
            except Exception:
                _tokenizer_instance = None
    return _tokenizer_instance


def format_chat_prompt(
    messages: list[dict[str, str]],
    add_generation_prompt: bool = True,
    prefill_think: bool = True,
) -> str:
    """Format messages into ChatML standard representation with empty thinking block."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    if add_generation_prompt:
        if prefill_think:
            parts.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
        else:
            parts.append("<|im_start|>assistant\n")
    return "".join(parts)


def count_tokens(text: str) -> int:
    """Accurately count tokens for a given text string."""
    if not text:
        return 0
    tok = get_tokenizer()
    if tok is not None:
        return len(tok.encode(text, add_special_tokens=False))

    # Fallback to remote llama-server /tokenize
    try:
        resp = httpx.post(f"{_LLM_BASE_URL}/tokenize", json={"content": text}, timeout=1.5)
        if resp.status_code == 200:
            return len(resp.json().get("tokens", []))
    except Exception:
        pass

    # Heuristic fallback (3.2 chars per token for Latin, 1.2 for Indic)
    tamil_chars = sum(1 for c in text if "\u0B80" <= c <= "\u0BFF")
    other_chars = len(text) - tamil_chars
    return max(1, int(other_chars / 3.4) + int(tamil_chars / 1.3))


def count_messages_tokens(
    messages: list[dict[str, str]],
    add_generation_prompt: bool = True,
    prefill_think: bool = True,
) -> int:
    """Count total prompt tokens including ChatML role wrappers and generation prompt."""
    prompt = format_chat_prompt(
        messages,
        add_generation_prompt=add_generation_prompt,
        prefill_think=prefill_think,
    )
    tok = get_tokenizer()
    if tok is not None:
        return len(tok.encode(prompt, add_special_tokens=False))

    try:
        resp = httpx.post(f"{_LLM_BASE_URL}/tokenize", json={"content": prompt}, timeout=2.0)
        if resp.status_code == 200:
            return len(resp.json().get("tokens", []))
    except Exception:
        pass

    return count_tokens(prompt)


def verify_count_with_server(prompt: str) -> tuple[int, int, bool]:
    """Verify local tokenizer token count against remote llama-server /tokenize endpoint."""
    local_count = count_tokens(prompt)
    try:
        resp = httpx.post(f"{_LLM_BASE_URL}/tokenize", json={"content": prompt}, timeout=2.0)
        if resp.status_code == 200:
            remote_count = len(resp.json().get("tokens", []))
            return local_count, remote_count, (local_count == remote_count)
    except Exception as exc:
        return local_count, -1, False
    return local_count, -1, False

