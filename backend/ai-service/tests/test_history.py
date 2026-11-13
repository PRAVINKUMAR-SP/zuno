"""Unit tests for token-aware conversation history trimming and turn-pair preservation."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from context.history import select_history, pair_conversation_turns
from context.tokenizer import count_tokens


def test_pair_conversation_turns():
    msgs = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I am great."},
    ]
    turns = pair_conversation_turns(msgs)
    assert len(turns) == 2
    assert turns[0][0]["content"] == "Hello"
    assert turns[0][1]["content"] == "Hi there!"
    assert turns[1][0]["content"] == "How are you?"
    assert turns[1][1]["content"] == "I am great."


def test_select_history_within_budget():
    msgs = [
        {"role": "user", "content": "Turn 1 user"},
        {"role": "assistant", "content": "Turn 1 assistant"},
        {"role": "user", "content": "Turn 2 user"},
        {"role": "assistant", "content": "Turn 2 assistant"},
    ]
    # Large budget: keep all
    kept = select_history(msgs, max_tokens=500, count_tokens_fn=count_tokens)
    assert len(kept) == 4
    assert kept[0]["content"] == "Turn 1 user"
    assert kept[3]["content"] == "Turn 2 assistant"


def test_select_history_drops_oldest_first():
    msgs = [
        {"role": "user", "content": "Turn 1: very long discussion about ancient civilizations and their rulers"},
        {"role": "assistant", "content": "Turn 1: detailed response about ancient dynasties and empires in India"},
        {"role": "user", "content": "Turn 2 user short"},
        {"role": "assistant", "content": "Turn 2 assistant short"},
    ]
    # Small budget: keep only the latest turn pair (Turn 2)
    kept = select_history(msgs, max_tokens=25, count_tokens_fn=count_tokens)
    assert len(kept) == 2
    assert kept[0]["content"] == "Turn 2 user short"
    assert kept[1]["content"] == "Turn 2 assistant short"


def test_select_history_zero_budget():
    msgs = [{"role": "user", "content": "Hello"}]
    kept = select_history(msgs, max_tokens=0, count_tokens_fn=count_tokens)
    assert kept == []
