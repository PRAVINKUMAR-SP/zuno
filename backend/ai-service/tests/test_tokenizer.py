"""Unit tests for Qwen3 tokenizer and ChatML prompt formatting."""

import pytest
import sys
from pathlib import Path

# Add backend/ai-service to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from context.tokenizer import count_tokens, count_messages_tokens, format_chat_prompt, verify_count_with_server


def test_count_tokens_english():
    text = "Hello world! How are you doing today?"
    tokens = count_tokens(text)
    assert tokens > 0
    assert 7 <= tokens <= 12


def test_count_tokens_tamil():
    text = "வணக்கம்! நீங்கள் எப்படி இருக்கிறீர்கள்?"
    tokens = count_tokens(text)
    assert tokens > 0
    # Tamil characters decompose into multiple subwords in byte-level BPE
    assert 10 <= tokens <= 55


def test_count_tokens_java_code():
    code = """public class Student {
    private String name;

    public Student(String name) {
        this.name = name;
    }

    public String getName() {
        return name;
    }
}"""
    tokens = count_tokens(code)
    assert tokens > 0
    assert 30 <= tokens <= 60


def test_format_chat_prompt_chatml():
    messages = [
        {"role": "system", "content": "You are Zuno."},
        {"role": "user", "content": "What is 2+2?"},
    ]
    prompt = format_chat_prompt(messages, add_generation_prompt=True, prefill_think=True)
    assert "<|im_start|>system\nYou are Zuno.<|im_end|>\n" in prompt
    assert "<|im_start|>user\nWhat is 2+2?<|im_end|>\n" in prompt
    assert "<|im_start|>assistant\n<think>\n\n</think>\n\n" in prompt


def test_count_messages_tokens_consistency():
    messages = [
        {"role": "system", "content": "You are Zuno."},
        {"role": "user", "content": "Hello world!"},
    ]
    count = count_messages_tokens(messages)
    assert count == 25, f"Expected 25 tokens for standard ChatML hello world, got {count}"


def test_tokenizer_server_verification():
    prompt = "<|im_start|>system\nYou are Zuno.<|im_end|>\n<|im_start|>user\nHello!<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    local_count, remote_count, is_match = verify_count_with_server(prompt)
    if remote_count > 0:
        assert is_match is True, f"Token mismatch: local={local_count}, remote={remote_count}"
