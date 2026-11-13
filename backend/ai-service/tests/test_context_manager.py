"""Unit tests for the central context manager and prompt budget orchestrator."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from context.manager import build_context
from context.tokenizer import count_tokens


def test_build_context_basic():
    system_prompt = "You are Zuno AI assistant."
    question = "Explain Java OOP in simple English."
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello! How can I help you?"},
    ]
    prompt, max_output, sources, tools_used, stats = build_context(
        system_prompt=system_prompt,
        current_question=question,
        conversation_history=history,
        intent="simple",
        is_tamil=False,
    )

    assert "You are Zuno AI assistant." in prompt
    assert "Explain Java OOP in simple English." in prompt
    assert max_output == 140
    assert stats["prompt_tokens"] <= 1812
    assert stats["context_size"] == 2048
    assert stats["validation"] == "PASSED"


def test_build_context_rag_and_web_budgeting():
    system_prompt = "You are Zuno AI assistant."
    question = "Who is Raja Raja Chola?"
    docs = [
        {"name": "cholas.txt", "snippet": "Raja Raja Chola I built the Brihadisvara Temple in Thanjavur in 1010 CE."},
        {"name": "other.txt", "snippet": "Unrelated document about geography."},
    ]
    web = [
        {"title": "Rajaraja I - Wikipedia", "url": "https://en.wikipedia.org/wiki/Rajaraja_I", "snippet": "Rajaraja I was a Chola emperor."}
    ]

    prompt, max_output, sources, tools_used, stats = build_context(
        system_prompt=system_prompt,
        current_question=question,
        conversation_history=[],
        intent="detailed",
        rag_documents=docs,
        web_results=web,
    )

    assert max_output == 480
    assert "rag" in tools_used
    assert "web" in tools_used
    assert any(s["title"] == "cholas.txt" for s in sources)
    assert any(s["title"] == "Rajaraja I - Wikipedia" for s in sources)
    assert stats["prompt_tokens"] <= 1472


def test_build_context_oversized_question_rejected():
    system_prompt = "You are Zuno."
    # 2500 tokens of gibberish question exceeding the 2048 context
    massive_question = "word " * 3000
    with pytest.raises(ValueError) as excinfo:
        build_context(
            system_prompt=system_prompt,
            current_question=massive_question,
            conversation_history=[],
            intent="detailed",
        )
    assert "exceed" in str(excinfo.value)


def test_build_context_preserves_question_drops_history_under_load():
    system_prompt = "You are Zuno, a helpful assistant with essential safety instructions."
    question = "Explain Java Polymorphism."
    # Create 20 long turns of history that exceed 1,052 tokens
    long_history = []
    for i in range(20):
        long_history.append({"role": "user", "content": f"Turn {i} question about programming architecture and object oriented systems with examples."})
        long_history.append({"role": "assistant", "content": f"Turn {i} detailed explanation with Java sample code, class declarations, and architectural patterns." * 2})

    prompt, max_output, sources, tools_used, stats = build_context(
        system_prompt=system_prompt,
        current_question=question,
        conversation_history=long_history,
        intent="coding",  # Coding has strict 1,052 max prompt tokens
    )

    assert "Explain Java Polymorphism." in prompt
    assert "essential safety instructions" in prompt
    assert stats["prompt_tokens"] <= 1052
    assert max_output == 900
    assert stats["history_messages"] < 40  # Old history trimmed to stay within budget
