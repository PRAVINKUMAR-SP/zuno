"""Token-aware conversation history selection preserving user-assistant turn pairs."""

from __future__ import annotations

from typing import Callable


def pair_conversation_turns(messages: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    """Group conversation turns into atomic units (preferably [user, assistant] pairs).

    Ensures that assistant responses are never kept without their corresponding user prompt.
    """
    cleaned: list[dict[str, str]] = [
        {"role": m.get("role", "user"), "content": m.get("content", "").strip()}
        for m in messages
        if m.get("role") in ("user", "assistant") and m.get("content", "").strip()
    ]
    if not cleaned:
        return []

    turns: list[list[dict[str, str]]] = []
    i = 0
    while i < len(cleaned):
        current = cleaned[i]
        if current["role"] == "user":
            if i + 1 < len(cleaned) and cleaned[i + 1]["role"] == "assistant":
                turns.append([current, cleaned[i + 1]])
                i += 2
            else:
                turns.append([current])
                i += 1
        else:
            # Standalone assistant turn
            turns.append([current])
            i += 1
    return turns


def select_history(
    messages: list[dict[str, str]],
    max_tokens: int,
    count_tokens_fn: Callable[[str], int],
) -> list[dict[str, str]]:
    """Select the most recent conversation turns within the allowed token budget.

    Preserves atomic (user, assistant) pairs and drops older turns first when the budget is constrained.
    """
    if not messages or max_tokens <= 0:
        return []

    turns = pair_conversation_turns(messages)
    selected_turns: list[list[dict[str, str]]] = []
    consumed_tokens = 0

    # Traverse from newest to oldest turns
    for turn in reversed(turns):
        turn_text = "\n".join(m["content"] for m in turn)
        turn_tokens = count_tokens_fn(turn_text) + (len(turn) * 4)  # ~4 tokens per ChatML wrapper
        if consumed_tokens + turn_tokens > max_tokens:
            break
        selected_turns.append(turn)
        consumed_tokens += turn_tokens

    # Restore chronological order
    selected_turns.reverse()
    result: list[dict[str, str]] = []
    for turn in selected_turns:
        result.extend(turn)
    return result

