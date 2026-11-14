"""Context budget calculation and prompt limit allocation for Zuno AI."""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory for config imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import CONTEXT_SIZE, OUTPUT_BUDGETS, SAFETY_MARGIN


def resolve_output_limit(intent: str, is_tamil: bool = False) -> int:
    """Resolve the maximum tokens reserved for generation based on intent and language."""
    key = intent.lower().strip()
    if is_tamil:
        if key in ("simple", "simple_english", "greeting"):
            return OUTPUT_BUDGETS.get("simple_tamil", 120)
        if key in ("detailed", "detailed_english"):
            return OUTPUT_BUDGETS.get("detailed_tamil", 220)

    if key in ("coding", "code_generation", "code"):
        return OUTPUT_BUDGETS.get("code_generation", 900)
    if key in ("debugging", "debug"):
        return OUTPUT_BUDGETS.get("debugging", 600)
    if key in ("detailed", "explain"):
        return OUTPUT_BUDGETS.get("detailed", 480)
    if key in ("greeting", "hi"):
        return OUTPUT_BUDGETS.get("greeting", 40)
    return OUTPUT_BUDGETS.get(key, OUTPUT_BUDGETS["simple"])


def calculate_budget(
    intent: str,
    is_tamil: bool = False,
    context_size: int = CONTEXT_SIZE,
    safety_margin: int = SAFETY_MARGIN,
) -> dict[str, int | str]:
    """Calculate the maximum prompt tokens allowed while strictly reserving generation budget.

    Formula:
        prompt_limit = context_size - output_reserve - safety_margin
    """
    output_limit = resolve_output_limit(intent, is_tamil=is_tamil)
    prompt_limit = context_size - output_limit - safety_margin

    if prompt_limit <= 0:
        raise ValueError(
            f"Invalid context budget: context_size={context_size} is too small for "
            f"output_limit={output_limit} + safety_margin={safety_margin}"
        )

    return {
        "context_size": context_size,
        "max_output_tokens": output_limit,
        "max_prompt_tokens": prompt_limit,
        "safety_margin": safety_margin,
        "intent": intent,
        "is_tamil": is_tamil,
    }

