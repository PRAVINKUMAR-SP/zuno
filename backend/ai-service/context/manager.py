"""Central token-aware context manager and prompt budget orchestrator for Zuno AI."""

from __future__ import annotations

import logging
from typing import Any

from .budget import calculate_budget
from .history import select_history
from .selector import select_rag_documents, select_web_results
from .tokenizer import count_messages_tokens, count_tokens, format_chat_prompt

logger = logging.getLogger("zuno.context")


def build_context(
    system_prompt: str,
    current_question: str,
    conversation_history: list[dict[str, str]],
    intent: str,
    is_tamil: bool = False,
    rag_documents: list[dict] | None = None,
    web_results: list[dict] | None = None,
    followup_hint: str | None = None,
    language_hint: str | None = None,
    context_size: int = 2048,
) -> tuple[str, int, list[dict], list[str], dict[str, Any]]:
    """Assemble a token-validated prompt within the strict 2,048 context budget.

    Selection priority:
        1. Current user question (Never silently removed).
        2. Essential system instructions (Never removed).
        3. Most recent conversation turns (Preserved as atomic user/assistant pairs).
        4. Relevant RAG documents.
        5. Web search snippets.
        6. Older conversation turns.

    Returns:
        (formatted_chatml_prompt, max_output_tokens, sources, tools_used, context_stats)
    """
    budget = calculate_budget(intent=intent, is_tamil=is_tamil, context_size=context_size)
    max_prompt = int(budget["max_prompt_tokens"])
    max_output = int(budget["max_output_tokens"])
    safety_margin = int(budget["safety_margin"])

    # 1. Base mandatory components
    base_system = system_prompt.strip()
    clean_question = current_question.strip()

    mandatory_messages = [
        {"role": "system", "content": base_system},
        {"role": "user", "content": clean_question},
    ]
    mandatory_tokens = count_messages_tokens(mandatory_messages)

    if mandatory_tokens > max_prompt:
        raise ValueError(
            f"Current question and essential instructions ({mandatory_tokens} tokens) "
            f"exceed allowed prompt budget ({max_prompt} tokens). Please ask a shorter question."
        )

    # 2. Allocate remaining capacity across history, RAG, and Web
    remaining_for_extras = max_prompt - mandatory_tokens

    # Dynamic quotas: 45% history, 35% RAG, 20% Web
    history_quota = int(remaining_for_extras * 0.45)
    rag_quota = int(remaining_for_extras * 0.35)
    web_quota = int(remaining_for_extras * 0.20)

    # If no RAG or no Web, redistribute quotas to history
    if not rag_documents:
        history_quota += rag_quota
        rag_quota = 0
    if not web_results:
        history_quota += web_quota
        web_quota = 0

    # Select history turns within quota
    kept_history = select_history(
        conversation_history,
        max_tokens=history_quota,
        count_tokens_fn=count_tokens,
    )

    # Select RAG documents within quota
    selected_rag, rag_lines, _ = select_rag_documents(
        rag_documents or [],
        max_tokens=rag_quota,
        count_tokens_fn=count_tokens,
    )

    # Select Web results within quota
    selected_web, web_lines, _ = select_web_results(
        web_results or [],
        max_tokens=web_quota,
        count_tokens_fn=count_tokens,
    )

    # Format augmented turn context for the current user question
    turn_notes: list[str] = []
    if followup_hint:
        turn_notes.append(followup_hint)
    if language_hint:
        turn_notes.append(language_hint)

    tools_used: list[str] = []
    sources: list[dict] = []

    if rag_lines:
        tools_used.append("rag")
        for doc in selected_rag:
            sources.append({"kind": "doc", "title": doc.get("name", "Document")})
        turn_notes.append(
            "Attached document context (you ALREADY read this uploaded file; answer directly from it):\n"
            + "\n".join(rag_lines)
        )

    if web_lines:
        tools_used.append("web")
        for w in selected_web:
            sources.append({"kind": "web", "title": w.get("title", "Web"), "url": w.get("url", "")})
        if is_tamil:
            turn_notes.append(
                "நேரலை உண்மைத் தகவல்கள் (Verified Facts):\n"
                + "\n".join(web_lines)
                + "\n\nவிதிகள்: மேலே உள்ள உண்மைத் தகவல்களின் அடிப்படையில் எளிய, சரியான தமிழ் வாக்கியங்களில் பதில் அளியுங்கள். தொடர்பற்ற சொற்களுடன் குழப்ப வேண்டாம்."
            )
        else:
            turn_notes.append(
                "LIVE VERIFIED WEB RESULTS (Retrieved online):\n"
                + "\n".join(web_lines)
                + "\n\nCRITICAL INSTRUCTION: Use these verified facts. Never contradict them with outdated training data. Cite sources."
            )

    # Build final message sequence
    def compose_messages(history_msgs: list[dict[str, str]], active_notes: list[str]) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = [{"role": "system", "content": base_system}]
        msgs.extend(history_msgs)
        user_content = clean_question
        if active_notes:
            user_content = "\n\n".join([*active_notes, f"User request: {clean_question}"])
        msgs.append({"role": "user", "content": user_content})
        return msgs

    final_messages = compose_messages(kept_history, turn_notes)
    current_tokens = count_messages_tokens(final_messages)

    # 3. Dynamic adjustment loop: Trim strictly in reverse priority if budget exceeded
    while current_tokens > max_prompt:
        if kept_history:
            # Remove oldest turn from history
            kept_history = kept_history[2:] if len(kept_history) >= 2 else []
            final_messages = compose_messages(kept_history, turn_notes)
            current_tokens = count_messages_tokens(final_messages)
            continue

        if selected_web and web_lines:
            # Remove lowest-ranked web result
            selected_web.pop()
            web_lines.pop()
            sources = [s for s in sources if s.get("kind") != "web"]
            for w in selected_web:
                sources.append({"kind": "web", "title": w.get("title", "Web"), "url": w.get("url", "")})
            turn_notes = [n for n in turn_notes if not n.startswith(("LIVE VERIFIED", "நேரலை"))]
            if web_lines:
                turn_notes.append("LIVE VERIFIED WEB RESULTS:\n" + "\n".join(web_lines))
            else:
                tools_used = [t for t in tools_used if t != "web"]
            final_messages = compose_messages(kept_history, turn_notes)
            current_tokens = count_messages_tokens(final_messages)
            continue

        if selected_rag and rag_lines:
            # Remove lowest-ranked RAG document
            selected_rag.pop()
            rag_lines.pop()
            sources = [s for s in sources if s.get("kind") != "doc"]
            for doc in selected_rag:
                sources.append({"kind": "doc", "title": doc.get("name", "Document")})
            turn_notes = [n for n in turn_notes if not n.startswith("Attached document context")]
            if rag_lines:
                turn_notes.append("Attached document context:\n" + "\n".join(rag_lines))
            else:
                tools_used = [t for t in tools_used if t != "rag"]
            final_messages = compose_messages(kept_history, turn_notes)
            current_tokens = count_messages_tokens(final_messages)
            continue

        # If only mandatory question and system prompt remain and still exceed
        if current_tokens > max_prompt:
            raise ValueError(
                f"Question and essential instructions ({current_tokens} tokens) exceed "
                f"context budget ({max_prompt} tokens)."
            )
        break

    unused_tokens = context_size - current_tokens - max_output - safety_margin
    formatted_prompt = format_chat_prompt(final_messages, add_generation_prompt=True, prefill_think=True)

    stats = {
        "intent": intent,
        "context_size": context_size,
        "prompt_tokens": current_tokens,
        "output_reserve": max_output,
        "safety_margin": safety_margin,
        "unused_tokens": max(0, unused_tokens),
        "history_messages": len(kept_history),
        "rag_documents": len(selected_rag),
        "web_snippets": len(selected_web),
        "validation": "PASSED",
    }

    # Structured context log (Never log private user conversation content)
    print(
        f"\n[ZERO CONTEXT]\n"
        f"Intent: {stats['intent']}\n"
        f"Context size: {stats['context_size']}\n"
        f"Prompt tokens: {stats['prompt_tokens']}\n"
        f"Output reserve: {stats['output_reserve']}\n"
        f"Safety margin: {stats['safety_margin']}\n"
        f"Unused tokens: {stats['unused_tokens']}\n"
        f"History messages: {stats['history_messages']}\n"
        f"RAG documents: {stats['rag_documents']}\n"
        f"Web snippets: {stats['web_snippets']}\n"
        f"Context validation: {stats['validation']}"
    )

    return formatted_prompt, max_output, sources, tools_used, stats

