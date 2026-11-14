"""Classifier to determine if a user query benefits from an XKCD visual comic."""

import re

# Explicit user requests for a comic or visual illustration
_EXPLICIT_VISUAL_RE = re.compile(
    r"(?i)\b("
    r"draw|drawing|comic|cartoon|xkcd|illustrat(?:e|ion)|visualize|visual\s+explanation|"
    r"image|images|picture|pictures|diagram|diagrams|sketch|photo|photos|"
    r"stick\s+figure|show\s+(?:a\s+)?comic|make\s+(?:a\s+)?comic"
    r")\b"
)

# Concepts that strongly benefit from visual 4-panel educational comics
_CONCEPTUAL_VISUAL_RE = re.compile(
    r"(?i)\b("
    r"how\s+(?:does|do|can)\s+[a-z0-9_ -]+\s+work|"
    r"explain\s+(?:how|the\s+concept\s+of|the\s+difference\s+between|architecture|workflow|process|stages\s+of)|"
    r"difference\s+between|"
    r"lifecycle\s+of|life\s+cycle|start\s+and\s+end|birth\s+and\s+death|human\s+life|stages\s+of\s+life|"
    r"architecture\s+of|flow\s+of|"
    r"what\s+happens\s+when|"
    r"request\s+(?:and\s+)?response|api|client\s+server|"
    r"neural\s+network|machine\s+learning|deep\s+learning|"
    r"docker|container|git\s+branch|merge\s+conflict|"
    r"database\s+index|recursion|deadlock|concurrency|"
    r"inheritance|polymorphism|microservices"
    r")\b"
)

# Blacklist: never generate comics for greetings, clock, or trivial math
_NON_VISUAL_RE = re.compile(
    r"(?i)^("
    r"hi|hii|hello|hey|yo|thanks|thank\s+you|ok|okay|bye|"
    r"what\s+is\s+today|today\s+what\s+day|current\s+time|what\s+time\s+is\s+it|"
    r"who\s+are\s+you|what\s+is\s+your\s+name|"
    r"\d+\s*[\+\-\*\/]\s*\d+"
    r")\s*[.?!]*$"
)


def should_generate_visual(query: str, intent: str = "simple", response_text: str = "") -> bool:
    """Determine whether to invoke the XKCD comic generator for a given turn."""
    clean_q = query.strip()
    if not clean_q or _NON_VISUAL_RE.match(clean_q):
        return False

    # 1. Explicit request: always generate
    if _EXPLICIT_VISUAL_RE.search(clean_q):
        return True

    # 2. Skip simple greetings or short single-word queries
    if intent in ("greeting", "safety") or len(clean_q.split()) < 3:
        return False

    # 3. Conceptual topics in detailed/coding modes
    if intent in ("detailed", "coding") and _CONCEPTUAL_VISUAL_RE.search(clean_q):
        return True

    # 4. Check if the response explains a multi-step process or architecture
    if len(response_text) > 180 and _CONCEPTUAL_VISUAL_RE.search(clean_q):
        return True

    return False

