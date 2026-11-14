"""Generates focused visual descriptions and prompts for the XKCD Artist ONNX model."""

import re

# High-signal concept prompt templates to ensure semantic relevance
_CONCEPT_TEMPLATES = [
    (re.compile(r"(?i)\bapi\b"), "A four-panel stick figure comic explaining an API: a user requests a menu, the waiter forwards it to the kitchen, the kitchen prepares data, and the waiter returns the response."),
    (re.compile(r"(?i)\b(neural\s+network|deep\s+learning|machine\s+learning|ai)\b"), "A four-panel stick figure comic showing a scientist teaching a computer to recognize shapes with trial and error feedback."),
    (re.compile(r"(?i)\b(git|branch|merge|conflict)\b"), "A four-panel stick figure comic about two programmers working on separate branches and dealing with a merge conflict."),
    (re.compile(r"(?i)\b(docker|container|kubernetes)\b"), "A four-panel stick figure comic about a developer shipping a software container so it runs anywhere."),
    (re.compile(r"(?i)\b(database|sql|index)\b"), "A four-panel stick figure comic about searching a giant library with and without an index card catalog."),
    (re.compile(r"(?i)\b(recursion)\b"), "A four-panel stick figure comic about a person looking into a mirror reflecting another mirror to explain recursion."),
    (re.compile(r"(?i)\b(deadlock|concurrency|thread)\b"), "A four-panel stick figure comic showing two stick figures trying to cross a narrow bridge at the exact same time causing a deadlock."),
    (re.compile(r"(?i)\b(cloud|cloud\s+computing)\b"), "A four-panel stick figure comic explaining cloud computing as renting computers in a remote server warehouse."),
    (re.compile(r"(?i)\b(human\s+life|life\s+cycle|start\s+and\s+end|birth\s+and\s+death|stages\s+of\s+life)\b"), "A four-panel stick figure comic showing the stages of human life: birth, growing up and learning, adulthood and working, and peaceful old age."),
]


def generate_comic_prompt(query: str, response_text: str = "") -> tuple[str, str]:
    """Return a tuple of (title, render_prompt) suitable for XKCD Artist ONNX generation."""
    clean_q = re.sub(
        r"(?i)\b(?:please\s+)?(?:draw|show|make|create|give\s+full\s+details\s+how|give\s+details)\s+(?:a\s+)?(?:comic|cartoon|xkcd|diagram|image|images)?\s*(?:about|of|explaining|on|with\s+images|with\s+pictures)?\b",
        "",
        query,
    )
    clean_q = re.sub(r"(?i)\b(?:with\s+images?|with\s+pictures?)\b", "", clean_q)
    clean_q = re.sub(r"\s+", " ", clean_q).strip(" ?.!")
    title = clean_q.title() if clean_q else "Visual Concept"

    # 1. Match curated high-signal concept template
    for pattern, prompt in _CONCEPT_TEMPLATES:
        if pattern.search(query):
            return title, prompt

    # 2. Dynamic synthesis from query
    first_sentence = ""
    if response_text:
        sentences = [s.strip() for s in re.split(r"[.!?।]\s+", response_text) if s.strip()]
        if sentences:
            first_sentence = sentences[0][:120]

    if first_sentence:
        render_prompt = f"A four-panel stick figure comic illustrating: {clean_q}. {first_sentence}."
    else:
        render_prompt = f"A four-panel stick figure educational comic explaining {clean_q}."

    return title, render_prompt
