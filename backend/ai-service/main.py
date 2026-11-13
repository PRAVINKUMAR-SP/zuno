import asyncio
import datetime as dt
import json
import os
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import llm_client
import rag_store
import tools_layer

load_dotenv()

MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen3-4B-Q4_K_M")


def get_base_system_prompt(is_tamil: bool = False) -> str:
    now_ist = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    today_str = now_ist.strftime("%A, %B %d, %Y")
    if is_tamil:
        return (
            "You are Zuno (ZERO), a helpful assistant.\n"
            f"Today: {today_str}.\n"
            "Rules for Tamil:\n"
            "1. Reply in clear, natural, grammatically correct Tamil script (தமிழ்) using 2-3 short sentences.\n"
            "2. Provide accurate historical facts based on context. Raja Raja Cholan (முதலாம் இராசராச சோழன்) is the great Chola emperor who built Thanjavur Brihadisvara Temple (தஞ்சைப் பெரிய கோயில்). Never confuse historical kings with grammar ('இலக்கணம்') or food ('சோளம்').\n"
            "3. Never repeat any sentence."
        )
    return (
        "You are Zuno (ZERO), a helpful, accurate personal AI assistant.\n\n"
        f"Today's date is {today_str} (Year {now_ist.year}).\n"
        "1. Answer concisely in natural language directly.\n"
        "2. For current events, offices (CM, PM, TVK = Tamilaga Vettri Kazhagam, Vijay), strictly rely on provided live web context. Never say 'I cannot check the internet' — web search is active.\n"
        "3. When user provides updates or corrections, verify and confirm them gracefully without debate.\n"
        "4. Historical entities: Raja Raja Cholan / Cholas / Pandyas are ancient kings and empires, never grammar terms."
    )

INTENT_SETTINGS = {
    "greeting": {
        "max_tokens": 40,
        "max_seconds": 12.0,
        "style": "Answer warmly in 1 short sentence.",
    },
    "simple": {
        "max_tokens": 140,
        "max_seconds": 22.0,
        "style": "Answer directly and accurately in 2-4 concise sentences without filler or repetition.",
    },
    "detailed": {
        "max_tokens": 480,
        "max_seconds": 60.0,
        "style": "Explain clearly using structured points or short paragraphs with accurate facts, avoiding any repetition.",
    },
    "coding": {
        "max_tokens": 900,
        "max_seconds": 105.0,
        "style": "Provide complete, runnable code inside a fenced markdown code block, then briefly explain how it works.",
    },
    "debugging": {
        "max_tokens": 600,
        "max_seconds": 70.0,
        "style": "Identify the likely root cause clearly and provide the exact fix or corrected code.",
    },
}

GREETING_HINTS = {
    "hi", "hii", "hello", "hey", "yo", "sup", "vanakkam", "good morning", "good evening",
    "good afternoon", "good night", "thanks", "thank you", "ok", "okay", "bye", "nice",
    "how are you", "who are you",
}
DEBUGGING_PATTERNS = (
    "fix ", "fix this", "debug", "error", "exception", "traceback", "stacktrace",
    "not working", "doesn't work", "doesnt work", "won't run", "failed", "crash", "bug",
    "issue", "404", "500", "nullpointer",
)
CODING_PATTERNS = (
    "create ", "write code", "write a program", "program", "complete code", "build ",
    "implement", "code example", "show sample code", "sample code",
    "snippet", "sql query", "calculator", "api endpoint", "react component", "java code",
)
DETAILED_PATTERNS = (
    "explain", "in detail", "step by step", "with examples", "with example", "full explanation",
    "tutorial", "how to ", "how do ", "how does ", "why does ", "why do ", "difference between",
    "compare", "advantages", "features", "architecture", "tell me about", "describe",
    "summarize", "list ", "interview", "theriyuma", "sollu", "connect ",
)
FOLLOWUP_DETAILED_HINTS = (
    "explain this", "explain it", "more details", "tell me more", "elaborate", "go deeper",
)
FOLLOWUP_EXAMPLE_HINTS = (
    "give me an example", "give an example", "show me an example", "show example",
    "example please", "for example",
)
_CODE_DOMAIN_RE = re.compile(
    r"(?i)\b(java|spring\s*boot|spring|react|python|javascript|typescript|sql|mysql|"
    r"rest\s*api|endpoint|html|css|c\+\+|code|program|class|function|method)\b|```|@"
)

inference_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="zuno-llm")
active_cancel_lock = threading.Lock()
active_cancel_event: threading.Event | None = None


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?think>", "", text)
    return text.strip()


def trim_conversation(
    messages: list[dict[str, str]], max_chars: int = 2400, max_turns: int = 10
) -> list[dict[str, str]]:
    """Component 1 (Input Handler): Retain recent conversation context within token budget."""
    kept: list[dict[str, str]] = []
    total = 0
    for msg in reversed(messages):
        content = msg.get("content", "").strip()
        role = msg.get("role", "user")
        if role not in ("user", "assistant") or not content:
            continue
        if len(kept) >= max_turns:
            break
        if total + len(content) > max_chars and kept:
            break
        kept.append({"role": role, "content": content})
        total += len(content)
    kept.reverse()
    return kept


def classify_question(
    messages: list[dict[str, str]], requested_mode: str = "auto"
) -> Literal["greeting", "simple", "detailed", "coding", "debugging"]:
    """Component 2 (Intent Classifier): Determine user intent and required depth."""
    if requested_mode == "fast":
        return "simple"
    if requested_mode == "detailed":
        return "detailed"

    last_user = ""
    prior_context: list[str] = []
    user_turns = 0
    for msg in reversed(messages):
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()
        if role in ("user", "assistant") and content and last_user:
            if len(prior_context) < 4:
                prior_context.append(content)
        if role == "user" and content:
            user_turns += 1
            if not last_user:
                last_user = content

    normalized = re.sub(r"\s+", " ", last_user.lower()).strip(" ?!.,")
    if not normalized or normalized in GREETING_HINTS:
        return "greeting"
    if any(pat in normalized for pat in DEBUGGING_PATTERNS):
        return "debugging"
    if normalized.startswith(("explain ", "describe ", "walk me through ", "what does ")) or "line by line" in normalized:
        return "detailed"
    if user_turns > 1 and any(hint in normalized for hint in FOLLOWUP_EXAMPLE_HINTS):
        return "coding" if _CODE_DOMAIN_RE.search(" ".join(prior_context)) else "detailed"
    if any(pat in normalized for pat in CODING_PATTERNS):
        return "coding"
    if any(pat in normalized for pat in DETAILED_PATTERNS):
        return "detailed"
    if user_turns > 1 and any(hint in normalized for hint in FOLLOWUP_DETAILED_HINTS):
        return "detailed"

    words = re.findall(r"[a-zA-Z0-9\u0B80-\u0BFF']+", normalized)
    if len(words) >= 8:
        return "detailed"
    return "simple"


def get_response_settings(intent: str) -> dict:
    """Component 3 (Response Planner): Pick output budget and instruction style for the intent."""
    return INTENT_SETTINGS.get(intent, INTENT_SETTINGS["simple"])


def _followup_instruction(messages: list[dict[str, str]]) -> str | None:
    """Add a compact follow-up anchor only when the user's latest turn actually refers to prior context."""
    convo = [m for m in messages if m.get("role") in ("user", "assistant") and m.get("content", "").strip()]
    if len(convo) < 2:
        return None
    last_user = convo[-1]["content"].strip()
    is_reference = bool(re.search(
        r"(?i)\b(this|that|it|above|example|previous|same|more|continue|elaborate|why|how\s+so|tell\s+me\s+more)\b",
        last_user,
    ))
    is_format_directive = bool(re.search(
        r"(?i)\b(in\s+tamil|in\s+python|in\s+java|in\s+detail|give\s+an\s+example|code\s+example)\b",
        last_user,
    )) and len(last_user.split()) <= 4

    if is_reference or is_format_directive:
        return "Conversation rule: Treat the latest user message as a direct follow-up to the immediately preceding topic in the chat history."
    return None


_TAMIL_SCRIPT_RE = re.compile(r"[\u0B80-\u0BFF]")
_TAMIL_REQUEST_RE = re.compile(r"(?i)(?:\bin\s+tamil\b|\btamil(?:il|la)?\b|தமிழ்)")


def _is_tamil_turn(messages: list[dict[str, str]]) -> bool:
    convo = [m for m in messages if m.get("role") == "user" and m.get("content", "").strip()]
    if not convo:
        return False
    last_user = convo[-1]["content"].strip()
    return bool(_TAMIL_SCRIPT_RE.search(last_user) or _TAMIL_REQUEST_RE.search(last_user))


def _language_instruction(messages: list[dict[str, str]]) -> str | None:
    """Add explicit language guidance based on the current turn, preventing language leak across turns."""
    if _is_tamil_turn(messages):
        return (
            "Language rule: The user requested Tamil. Reply clearly in natural, grammatical Tamil script (தமிழ்) using 2-4 short, accurate sentences or bullet points. "
            "Provide true historical or factual information based on the retrieved context. Never confuse historical figures (like Raja Raja Cholan / முதலாம் இராஜராஜ சோழன் / சோழ மன்னர்) with grammar rules ('இலக்கணம்') or food ('சோளம்'). Never repeat any sentence or phrase."
        )

    # If current turn is in English but previous messages had Tamil, explicitly reset to English
    convo = [m for m in messages if m.get("content", "").strip()]
    had_tamil_prior = any(
        _TAMIL_SCRIPT_RE.search(m.get("content", ""))
        for m in convo[:-1]
    )
    if had_tamil_prior:
        return (
            "Language rule: The user's latest query is in English. Reply in clear, fluent English only. "
            "Do NOT reply in Tamil."
        )
    return None


def build_qwen_prompt(
    messages: list[dict[str, str]],
    intent: str,
    augmented_context: list[str] | None = None,
    is_tamil: bool = False,
) -> str:
    settings = get_response_settings(intent)
    extra_system = [
        m.get("content", "").strip()
        for m in messages
        if m.get("role") == "system" and m.get("content", "").strip()
    ]
    # Keep base system instructions + dynamic date + style at the front.
    system_prompt = "\n".join([get_base_system_prompt(is_tamil=is_tamil), *extra_system, f"Response guide: {settings['style']}"])
    parts = [f"<|im_start|>system\n{system_prompt}<|im_end|>\n"]
    trimmed = trim_conversation(messages)
    followup_hint = _followup_instruction(messages)
    language_hint = _language_instruction(messages)
    turn_notes = (
        ([followup_hint] if followup_hint else [])
        + ([language_hint] if language_hint else [])
        + (augmented_context or [])
    )

    for idx, msg in enumerate(trimmed):
        content = msg["content"]
        if idx == len(trimmed) - 1 and msg["role"] == "user" and turn_notes:
            content = "\n\n".join([*turn_notes, f"User request: {content}"])
        parts.append(f"<|im_start|>{msg['role']}\n{content}<|im_end|>\n")
    # Pre-fill empty <think> block so Qwen3 skips reasoning tokens and starts answering immediately.
    parts.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    return "".join(parts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    health_status = llm_client.check_server_health()
    print(f"[Zuno AI] Connected to remote inference server: {health_status}")
    yield


app = FastAPI(title="Zuno AI Service", version="2.0.0", lifespan=lifespan)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    mode: Literal["auto", "fast", "detailed"] = "auto"
    use_web: bool | None = None
    doc_ids: list[str] | None = None
    max_seconds: float | None = None
    max_tokens: int | None = None
    temperature: float = 0.5


@app.get("/health")
def health():
    health_info = llm_client.check_server_health()
    return {
        "status": "ok" if health_info.get("ready") else "degraded",
        "ready": health_info.get("ready", False),
        "server": health_info.get("url"),
        "model": health_info.get("model", MODEL_NAME),
        "pingMs": health_info.get("pingMs", 0),
        "docsCount": len(rag_store.list_docs()),
    }


@app.get("/v1/docs")
def list_knowledge_docs():
    return {"docs": rag_store.list_docs()}


@app.post("/v1/docs")
async def upload_knowledge_doc(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        doc = rag_store.add_document(file.filename or "document.txt", raw)
        return doc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/v1/docs/{doc_id}")
def delete_knowledge_doc(doc_id: str):
    if not rag_store.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "id": doc_id}


def _resolve_limits(req: ChatRequest, intent: str, is_tamil: bool = False) -> tuple[float, int]:
    settings = get_response_settings(intent)
    max_sec = req.max_seconds if req.max_seconds is not None else float(settings["max_seconds"])
    max_tok = req.max_tokens if req.max_tokens is not None else int(settings["max_tokens"])
    if is_tamil:
        if intent == "simple" and req.max_tokens is None:
            max_tok = min(max_tok, 120)
        elif intent == "detailed" and req.max_tokens is None:
            max_tok = min(max_tok, 220)
        if intent == "detailed" and req.max_seconds is None:
            max_sec = min(max_sec, 35.0)
    return max_sec, max_tok


def _strip_trailing_orphan_heading(text: str) -> str:
    """Remove incomplete trailing list numbers or headings (e.g. '2.' or '### 3. Next') left after truncation."""
    lines = text.splitlines()
    orphan_re = re.compile(r"^\s*(?:\d+\.|[-*+]|\#{1,6}\s+(?:\d+\.\s*)?.*)\s*$")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if re.match(r"^\d+\.$", last) or re.match(r"^[-*+]$", last):
            lines.pop()
            continue
        if re.match(r"^#{1,6}\s+.+$", last) and orphan_re.match(last):
            lines.pop()
            continue
        break
    return "\n".join(lines).strip()


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?।])\s+")
_BROKEN_TAMIL_RE = re.compile(r"(?:\s[\u0BBE-\u0BCD\u0BD7]|[\u0BBE-\u0BCD\u0BD7]{3,})")


def _dedupe_repeated_text(text: str) -> str:
    """Remove duplicate paragraphs and consecutive/repeated sentences outside code blocks."""
    if not text or "```" in text:
        return text

    seen_paras: set[str] = set()
    kept_paras: list[str] = []
    seen_sentences: set[str] = set()
    seen_tails: set[str] = set()

    for para in text.split("\n\n"):
        norm_para = re.sub(r"\s+", " ", para).strip()
        if not norm_para or _BROKEN_TAMIL_RE.search(para):
            continue
        if len(norm_para) >= 24 and norm_para in seen_paras:
            continue
        seen_paras.add(norm_para)

        parts = _SENTENCE_SPLIT_RE.split(para.strip())
        unique_parts: list[str] = []
        for sent in parts:
            norm_sent = re.sub(r"\s+", " ", sent).strip()
            if not norm_sent or _BROKEN_TAMIL_RE.search(sent):
                continue
            tail_key = norm_sent[-32:] if len(norm_sent) >= 32 else ""
            if (len(norm_sent) >= 22 and norm_sent in seen_sentences) or (tail_key and tail_key in seen_tails):
                continue
            if len(norm_sent) >= 22:
                seen_sentences.add(norm_sent)
            if tail_key:
                seen_tails.add(tail_key)
            unique_parts.append(sent.strip())
        if unique_parts:
            kept_paras.append(" ".join(unique_parts))

    return "\n\n".join(kept_paras).strip() or text


def _has_stream_repetition_loop(text: str) -> bool:
    """Detect repeated paragraphs, repeated sentences, repeated clauses, or broken Tamil marks mid-stream."""
    if len(text) < 70 or "```" in text:
        return False
    if _BROKEN_TAMIL_RE.search(text[-60:]):
        return True

    paras = [re.sub(r"\s+", " ", p).strip() for p in text.split("\n\n") if len(p.strip()) >= 28]
    if len(paras) >= 2 and len(paras) != len(set(paras)):
        return True

    sentences = [
        re.sub(r"\s+", " ", s).strip()
        for s in _SENTENCE_SPLIT_RE.split(text)
        if len(s.strip()) >= 24
    ]
    if len(sentences) >= 2:
        if len(sentences) != len(set(sentences)):
            return True
        tails = [s[-32:] for s in sentences if len(s) >= 32]
        if len(tails) >= 2 and len(tails) != len(set(tails)):
            return True
    return False


def format_response(text: str, truncated: bool) -> str:
    """Component 5 (Response Formatter): Hide thinking, dedupe loops, close code blocks, avoid broken endings."""
    cleaned = clean_text(text)
    if not cleaned:
        return cleaned

    cleaned = _dedupe_repeated_text(cleaned)

    if cleaned.count("```") % 2 == 1:
        last_nl = cleaned.rfind("\n")
        if last_nl > 0 and truncated:
            cleaned = cleaned[:last_nl].rstrip()
        return cleaned.rstrip() + "\n```"

    cleaned = _strip_trailing_orphan_heading(cleaned)
    if not truncated or cleaned.endswith((".", "!", "?", "।", "`", ")", "\"")):
        return cleaned

    last_end = max(
        cleaned.rfind(". "),
        cleaned.rfind("! "),
        cleaned.rfind("? "),
        cleaned.rfind(".\n"),
        cleaned.rfind("!\n"),
        cleaned.rfind("?\n"),
        cleaned.rfind("\n"),
    )
    if last_end >= 6:
        candidate = cleaned[:last_end].strip() if cleaned[last_end] == "\n" else cleaned[: last_end + 1].strip()
        return _strip_trailing_orphan_heading(candidate) or candidate
    last_space = cleaned.rfind(" ")
    if last_space >= 6:
        return cleaned[:last_space].rstrip(" ,;:-") + "."
    return cleaned


def _begin_generation() -> threading.Event:
    """Cancel any in-flight generation and return a fresh cancellation event."""
    global active_cancel_event
    cancel_event = threading.Event()
    with active_cancel_lock:
        if active_cancel_event is not None:
            active_cancel_event.set()
        active_cancel_event = cancel_event
    return cancel_event


def _run_inference(
    prompt: str,
    intent: str,
    max_seconds: float,
    max_tokens: int,
    temperature: float,
    repeat_penalty: float,
    out_queue: queue.Queue,
    cancel_event: threading.Event,
    tools_used: list[str] | None = None,
    sources: list[dict] | None = None,
) -> None:
    """Component 4 (AI Engine): Stream completion inside single worker thread (deadlock-free)."""
    start = time.perf_counter()
    first_token_ms: int | None = None
    stopped_by_budget = False
    stopped_by_repetition = False
    hit_length = False
    chunks: list[str] = []
    stream = None

    try:
        generated_tokens = 0
        in_think = False
        first_token_at: float | None = None
        for delta, finish_reason in llm_client.stream_completion(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
            cancel_event=cancel_event,
        ):
            if cancel_event.is_set():
                break

            if finish_reason == "length":
                hit_length = True

            if delta:
                if "<think>" in delta:
                    before_think, after_think = delta.split("<think>", 1)
                    if "</think>" in after_think:
                        delta = before_think + after_think.split("</think>", 1)[1]
                        in_think = False
                    else:
                        in_think = True
                        delta = before_think
                elif in_think:
                    if "</think>" in delta:
                        in_think = False
                        delta = delta.split("</think>", 1)[1]
                    else:
                        delta = ""

            if delta:
                now = time.perf_counter()
                if first_token_at is None:
                    first_token_at = now
                    first_token_ms = int((now - start) * 1000)
                generated_tokens += 1
                chunks.append(delta)
                out_queue.put(("token", delta))
                if (generated_tokens >= 18 and ("\n" in delta or "." in delta or "!" in delta or "?" in delta)) or generated_tokens % 16 == 0:
                    if _has_stream_repetition_loop("".join(chunks)):
                        stopped_by_repetition = True
                        break

            now = time.perf_counter()
            if (first_token_at is not None and (now - first_token_at) >= max_seconds) or (now - start) >= max_seconds + 20.0:
                stopped_by_budget = True
                break

        # Guard against rare 0-token immediate <|im_end|> emission after </think>.
        if not cancel_event.is_set() and not clean_text("".join(chunks)):
            retry_raw = llm_client.generate_completion(
                prompt=prompt + "Sure, ",
                max_tokens=min(max_tokens, 64),
                temperature=0.5,
                stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
            )
            retry_text = clean_text("Sure, " + retry_raw)
            if retry_text and retry_text != "Sure,":
                chunks.append(retry_text)
                out_queue.put(("token", retry_text))
                if first_token_ms is None:
                    first_token_ms = int((time.perf_counter() - start) * 1000)

        if not cancel_event.is_set():
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            raw_text = "".join(chunks)
            needs_trim = stopped_by_budget or hit_length or stopped_by_repetition
            final_text = format_response(raw_text, needs_trim)
            out_queue.put((
                "done",
                {
                    "content": final_text,
                    "elapsedMs": elapsed_ms,
                    "firstTokenMs": first_token_ms or elapsed_ms,
                    "truncated": stopped_by_budget or hit_length,
                    "intent": intent,
                    "toolsUsed": tools_used or [],
                    "sources": sources or [],
                },
            ))
    except Exception as exc:
        if not cancel_event.is_set():
            out_queue.put(("error", str(exc)))
    finally:
        out_queue.put(None)


_EXPLICIT_READ_FILE_RE = re.compile(
    r"(?i)^(?:please\s+)?(?:read|show|display|open|print|view)\s+(?:the\s+|my\s+|this\s+)?(?:attached\s+|uploaded\s+)?(?:file|doc|document|pdf|[\w.-]+\.(?:pdf|txt|md|csv|json|java|py|js))\s*[.?!]*$"
)
_VAGUE_WRITE_FILE_RE = re.compile(
    r"(?i)^(?:please\s+)?(?:write|save|modify|edit|update)\s+(?:to\s+)?(?:the\s+|this\s+)?(?:file|doc|document|pdf)\s*[.?!]*$"
)


def _prepare_turn_context(
    raw_messages: list[dict[str, str]],
    use_web: bool | None,
    doc_ids: list[str] | None = None,
    intent: str = "simple",
    is_tamil: bool = False,
) -> tuple[str | None, list[str], list[str], list[dict]]:
    """Run Safety, Tool Calling, Document RAG, and Web Search layers before generation."""
    user_msgs = [m.get("content", "").strip() for m in raw_messages if m.get("role") == "user" and m.get("content", "").strip()]
    last_user = user_msgs[-1] if user_msgs else ""
    safe_user = tools_layer.redact_sensitive_text(last_user)

    refusal = tools_layer.check_unsafe_request(safe_user)
    if refusal:
        return refusal, [], ["safety"], []

    tool_hit = tools_layer.try_run_local_tool(safe_user)
    if tool_hit:
        return tool_hit["direct_reply"], [], [tool_hit["tool"]], []

    if _EXPLICIT_READ_FILE_RE.match(safe_user):
        preview = rag_store.read_doc_preview(safe_user, doc_ids=doc_ids)
        if preview is None:
            return (
                "No document is attached in this chat yet. Click **Attach doc** below to upload a PDF, text, or code file.",
                [],
                ["rag"],
                [],
            )
        suffix = "\n\n*(Showing opening extract; ask a specific question or say \"summarize the file\" for more.)*" if preview["truncated"] else ""
        reply = f"**{preview['name']}** ({preview['totalChars']} chars):\n\n{preview['text']}{suffix}"
        return reply, [], ["rag"], [{"kind": "doc", "title": preview["name"]}]

    if _VAGUE_WRITE_FILE_RE.match(safe_user):
        all_docs = rag_store.list_docs()
        docs = [d for d in all_docs if doc_ids is None or d["id"] in set(doc_ids)]
        if docs:
            doc_name = docs[-1]["name"]
            return (
                f"For safety, Zuno doesn't overwrite files on your disk directly — **but I can draft or rewrite `{doc_name}` right here in chat for you to copy.** Tell me what you want written (for example: *\"rewrite {doc_name} as a clean summary\"* or *\"draft a cover letter from {doc_name}\"*).",
                [],
                ["safety"],
                [{"kind": "doc", "title": doc_name}],
            )
        return (
            "For safety, Zuno doesn't write files to disk directly — tell me the filename or content you need and I will draft the full text or code here for you to copy.",
            [],
            ["safety"],
            [],
        )

    _META_SEARCH_CMD_RE = re.compile(
        r"(?i)^(?:please\s+)?(?:check\s+online|search\s+online|check\s+(?:the\s+)?(?:web|internet)|search\s+google|google\s+it|look\s+(?:it\s+)?up|verify(?:\s+online)?|check\s+again|check\s+it)\s*[.?!]*$"
    )
    is_meta_search = bool(_META_SEARCH_CMD_RE.match(safe_user))

    retrieval_query = safe_user
    if is_meta_search:
        # User commanded "check online": ground search in the preceding conversation topic
        if len(user_msgs) >= 3:
            retrieval_query = f"{user_msgs[-3]} {user_msgs[-2]}"
        elif len(user_msgs) >= 2:
            retrieval_query = user_msgs[-2]
    elif len(safe_user.split()) <= 6 and len(user_msgs) >= 2:
        retrieval_query = f"{user_msgs[-2]} {safe_user}"

    augmented_context: list[str] = []
    tools_used: list[str] = []
    sources: list[dict] = []
    seen_sources: set[tuple[str, str]] = set()

    doc_hits = rag_store.search_docs(retrieval_query, doc_ids=doc_ids)
    if doc_hits:
        tools_used.append("rag")
        lines = []
        for hit in doc_hits:
            lines.append(f"[{hit['name']}] {hit['snippet']}")
            key = ("doc", hit["name"])
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append({"kind": "doc", "title": hit["name"]})
        augmented_context.append(
            "Attached document context (you ALREADY read this uploaded file; answer directly from it and never say you cannot read files):\n"
            + "\n".join(lines)
        )

    explicit_web_words = bool(
        is_meta_search
        or re.search(r"(?i)\b(search\s+web|search\s+online|look\s+up\s+online|check\s+online|check\s+internet)\b", safe_user)
    )
    run_web = (use_web is True) or is_meta_search or (
        use_web is None
        and (tools_layer.should_search_web(safe_user, None) or tools_layer.should_search_web(retrieval_query, None))
        and (not doc_hits or explicit_web_words)
    )
    if run_web:
        web_hits = tools_layer.web_search(retrieval_query)
        if web_hits:
            tools_used.append("web")
            web_lines = []
            for item in web_hits:
                web_lines.append(f"- {item['title']}: {item['snippet'][:140]}")
                key = ("web", item["title"])
                if key not in seen_sources:
                    seen_sources.add(key)
                    sources.append({"kind": "web", "title": item["title"], "url": item["url"]})
            if is_tamil:
                augmented_context.append(
                    "நேரலை உண்மைத் தகவல்கள் (Verified Facts):\n"
                    + "\n".join(web_lines)
                    + "\n\nவிதிகள்: மேலே உள்ள உண்மைத் தகவல்களின் அடிப்படையில் எளிய, சரியான தமிழ் வாக்கியங்களில் பதில் அளியுங்கள். இலக்கணம் அல்லது சோளம் போன்ற தொடர்பற்ற சொற்களுடன் குழப்ப வேண்டாம்."
                )
            else:
                augmented_context.append(
                    "LIVE VERIFIED WEB RESULTS (Retrieved online November 2026):\n"
                    + "\n".join(web_lines)
                    + "\n\nCRITICAL INSTRUCTION FOR CURRENT FACTS:\n"
                    + "- Use these verified current facts. Never contradict them with outdated pre-2024 training data.\n"
                    + "- If the user made a statement or correction (e.g. current Chief Minister or office holder), verify it against these facts and confirm the updated status.\n"
                    + "- Cite source titles in your answer and never say you cannot access the internet."
                )

    return None, augmented_context, tools_used, sources


class _CompletedFuture:
    def result(self):
        return None


def _submit_inference(req: ChatRequest):
    raw_messages = [m.model_dump() for m in req.messages]
    intent = classify_question(raw_messages, req.mode)
    is_tamil = _is_tamil_turn(raw_messages)
    direct_reply, augmented_context, tools_used, sources = _prepare_turn_context(
        raw_messages, req.use_web, req.doc_ids, intent=intent, is_tamil=is_tamil
    )
    cancel_event = _begin_generation()
    out_queue: queue.Queue = queue.Queue()

    if sources:
        out_queue.put(("sources", sources))

    if direct_reply is not None:
        direct_intent = "simple"
        out_queue.put(("token", direct_reply))
        out_queue.put((
            "done",
            {
                "content": direct_reply,
                "elapsedMs": 15,
                "firstTokenMs": 15,
                "truncated": False,
                "intent": direct_intent,
                "toolsUsed": tools_used,
                "sources": sources,
            },
        ))
        out_queue.put(None)
        return _CompletedFuture(), out_queue, cancel_event

    prompt = build_qwen_prompt(raw_messages, intent, augmented_context, is_tamil=is_tamil)
    max_seconds, max_tokens = _resolve_limits(req, intent, is_tamil=is_tamil)
    repeat_penalty = 1.18 if is_tamil else 1.15
    future = inference_executor.submit(
        _run_inference,
        prompt,
        intent,
        max_seconds,
        max_tokens,
        req.temperature,
        repeat_penalty,
        out_queue,
        cancel_event,
        tools_used,
        sources,
    )
    return future, out_queue, cancel_event


@app.post("/v1/chat/stream")
async def chat_stream(req: ChatRequest):
    _, out_queue, cancel_event = _submit_inference(req)

    async def event_generator():
        last_emit = time.monotonic()
        pending_item: tuple[str, object] | None = None
        # Emit initial metadata event
        meta_payload = json.dumps({"type": "meta", "model": MODEL_NAME, "mode": req.mode})
        yield f"event: meta\ndata: {meta_payload}\n\n"

        try:
            while True:
                if pending_item is not None:
                    item = pending_item
                    pending_item = None
                else:
                    try:
                        item = out_queue.get_nowait()
                    except queue.Empty:
                        now = time.monotonic()
                        if now - last_emit >= 2.5:
                            last_emit = now
                            yield ": keepalive\n\n"
                        await asyncio.sleep(0.015)
                        continue

                if item is None:
                    break

                last_emit = time.monotonic()
                kind, value = item
                if kind == "sources":
                    src_payload = json.dumps({"type": "sources", "sources": value})
                    yield f"event: sources\ndata: {src_payload}\n\n"
                elif kind == "token":
                    # Drain consecutive token chunks in order to keep SSE frames smooth and compact.
                    token_parts = [str(value)]
                    while True:
                        try:
                            nxt = out_queue.get_nowait()
                        except queue.Empty:
                            break
                        if nxt is None or nxt[0] != "token":
                            pending_item = nxt
                            break
                        token_parts.append(str(nxt[1]))
                    chunk_text = "".join(token_parts)
                    payload = json.dumps({"type": "token", "content": chunk_text, "text": chunk_text})
                    yield f"event: token\ndata: {payload}\n\n"
                elif kind == "done":
                    done_payload = json.dumps({
                        "type": "done",
                        "finishReason": "stop",
                        "totalMs": value.get("elapsedMs", 0) if isinstance(value, dict) else 0,
                        **(value if isinstance(value, dict) else {}),
                    })
                    yield f"event: done\ndata: {done_payload}\n\n"
                elif kind == "error":
                    err_payload = json.dumps({
                        "type": "error",
                        "code": "GENERATION_FAILED",
                        "message": str(value),
                    })
                    yield f"event: error\ndata: {err_payload}\n\n"
        except asyncio.CancelledError:
            cancel_event.set()
            raise
        finally:
            cancel_event.set()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/chat")
def chat_sync(req: ChatRequest):
    future, out_queue, _ = _submit_inference(req)
    future.result()

    done_data = {"content": "", "elapsedMs": 0, "firstTokenMs": 0, "truncated": False}
    while True:
        try:
            item = out_queue.get(timeout=60.0)
        except queue.Empty:
            break
        if item is None:
            break
        kind, value = item
        if kind == "done":
            done_data = value
        elif kind == "error":
            raise HTTPException(status_code=500, detail=value)

    return {**done_data, "model": MODEL_NAME}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("ZUNO_AI_PORT", "8001"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
