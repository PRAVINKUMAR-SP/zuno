"""Ranking and token-budgeted selection of RAG and Web retrieved content."""

from __future__ import annotations

from typing import Callable


def select_rag_documents(
    doc_hits: list[dict],
    max_tokens: int,
    count_tokens_fn: Callable[[str], int],
) -> tuple[list[dict], list[str], int]:
    """Select the highest-ranked RAG excerpts that fit within the allowed token budget.

    Returns:
        (selected_hits, formatted_lines, consumed_tokens)
    """
    if not doc_hits or max_tokens <= 0:
        return [], [], 0

    selected: list[dict] = []
    lines: list[str] = []
    consumed = 0

    # Documents are already sorted by relevance score descending
    for hit in doc_hits:
        name = hit.get("name", "Document")
        snippet = hit.get("snippet", "").strip()
        if not snippet:
            continue
        line = f"[{name}] {snippet}"
        line_tokens = count_tokens_fn(line)
        if consumed + line_tokens > max_tokens:
            # If the first document is slightly larger, try trimming snippet to fit
            remaining = max_tokens - consumed
            if not selected and remaining >= 30:
                approx_chars = remaining * 3
                trimmed_snip = snippet[:approx_chars].rsplit(" ", 1)[0] + "..."
                trimmed_line = f"[{name}] {trimmed_snip}"
                t_tokens = count_tokens_fn(trimmed_line)
                if t_tokens <= max_tokens:
                    selected.append({**hit, "snippet": trimmed_snip})
                    lines.append(trimmed_line)
                    consumed += t_tokens
            break

        selected.append(hit)
        lines.append(line)
        consumed += line_tokens

    return selected, lines, consumed


def select_web_results(
    web_hits: list[dict],
    max_tokens: int,
    count_tokens_fn: Callable[[str], int],
) -> tuple[list[dict], list[str], int]:
    """Select the highest-ranked Web search snippets that fit within the allowed token budget.

    Returns:
        (selected_hits, formatted_lines, consumed_tokens)
    """
    if not web_hits or max_tokens <= 0:
        return [], [], 0

    selected: list[dict] = []
    lines: list[str] = []
    consumed = 0

    for item in web_hits:
        title = item.get("title", "").strip()
        snippet = item.get("snippet", "").strip()
        if not snippet and not title:
            continue
        line = f"- {title}: {snippet}"
        line_tokens = count_tokens_fn(line)
        if consumed + line_tokens > max_tokens:
            remaining = max_tokens - consumed
            if not selected and remaining >= 25:
                approx_chars = remaining * 3
                trimmed_snip = snippet[:approx_chars].rsplit(" ", 1)[0] + "..."
                trimmed_line = f"- {title}: {trimmed_snip}"
                t_tokens = count_tokens_fn(trimmed_line)
                if t_tokens <= max_tokens:
                    selected.append({**item, "snippet": trimmed_snip})
                    lines.append(trimmed_line)
                    consumed += t_tokens
            break

        selected.append(item)
        lines.append(line)
        consumed += line_tokens

    return selected, lines, consumed

