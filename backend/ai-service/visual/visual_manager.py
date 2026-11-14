"""Orchestrator for visual classification, comic script generation, and rendering."""

import logging
import threading

from visual.visual_classifier import should_generate_visual
from visual.comic_script_generator import generate_comic_prompt
from visual.comic_client import generate_comic
from visual.relevance_checker import validate_comic_payload

logger = logging.getLogger("visual-manager")


def maybe_generate_visual(
    query: str,
    response_text: str = "",
    intent: str = "simple",
    cancel_event: threading.Event | None = None,
) -> dict | None:
    """Evaluate whether to generate an XKCD comic and fetch it if approved."""
    if cancel_event is not None and cancel_event.is_set():
        return None

    if not should_generate_visual(query, intent=intent, response_text=response_text):
        return None

    logger.info(f"Visual generation triggered for query: {query[:50]}")
    title, prompt = generate_comic_prompt(query, response_text)

    if cancel_event is not None and cancel_event.is_set():
        return None

    comic_data = generate_comic(prompt=prompt, title=title)
    if validate_comic_payload(comic_data):
        logger.info(f"Visual comic successfully generated: {comic_data.get('imageUrl')}")
        return comic_data

    logger.info("Visual comic generation skipped or returned invalid payload.")
    return None

