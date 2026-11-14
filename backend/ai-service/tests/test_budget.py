"""Unit tests for token budget calculation across all intents and languages."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from context.budget import calculate_budget, resolve_output_limit


def test_greeting_budget():
    b = calculate_budget(intent="greeting")
    assert b["max_output_tokens"] == 40
    assert b["max_prompt_tokens"] == 1912
    assert b["context_size"] == 2048
    assert b["safety_margin"] == 96


def test_simple_english_budget():
    b = calculate_budget(intent="simple", is_tamil=False)
    assert b["max_output_tokens"] == 140
    assert b["max_prompt_tokens"] == 1812
    assert b["context_size"] == 2048


def test_simple_tamil_budget():
    b = calculate_budget(intent="simple", is_tamil=True)
    assert b["max_output_tokens"] == 120
    assert b["max_prompt_tokens"] == 1832
    assert b["context_size"] == 2048


def test_detailed_budget():
    b = calculate_budget(intent="detailed", is_tamil=False)
    assert b["max_output_tokens"] == 480
    assert b["max_prompt_tokens"] == 1472
    assert b["context_size"] == 2048


def test_debugging_budget():
    b = calculate_budget(intent="debugging")
    assert b["max_output_tokens"] == 600
    assert b["max_prompt_tokens"] == 1352
    assert b["context_size"] == 2048


def test_code_generation_budget():
    b = calculate_budget(intent="code_generation")
    assert b["max_output_tokens"] == 900
    assert b["max_prompt_tokens"] == 1052
    assert b["context_size"] == 2048


def test_budget_invariance_sum():
    for intent in ["greeting", "simple", "detailed", "debugging", "coding"]:
        b = calculate_budget(intent=intent)
        total = b["max_prompt_tokens"] + b["max_output_tokens"] + b["safety_margin"]
        assert total == 2048, f"Invariant violated for {intent}: {total} != 2048"


def test_invalid_context_budget_overflow():
    with pytest.raises(ValueError):
        calculate_budget(intent="coding", context_size=500)

