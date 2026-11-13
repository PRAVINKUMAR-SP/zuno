"""Lightweight on-disk BM25 Document RAG store for Zuno (zero extra ML RAM)."""

from __future__ import annotations

import io
import json
import math
import re
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

from PyPDF2 import PdfReader

STORE_DIR = Path(__file__).resolve().parent / "knowledge_base"
INDEX_FILE = STORE_DIR / "docs.json"
MAX_DOC_BYTES = 2 * 1024 * 1024  # 2 MB safety limit per document
MAX_CHUNKS_PER_DOC = 80

SUPPORTED_TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".csv", ".json", ".java", ".py", ".js", ".jsx",
    ".ts", ".tsx", ".html", ".css", ".sql", ".xml", ".yml", ".yaml", ".properties", ".log",
}

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i",
    "in", "is", "it", "me", "my", "of", "on", "or", "tell", "that", "the",
    "this", "to", "was", "what", "when", "where", "which", "who", "why", "with", "you",
}

_store_lock = threading.Lock()


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+|[\u0B80-\u0BFF]+", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOP_WORDS]


def _load_index() -> list[dict]:
    if not INDEX_FILE.exists():
        return []
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_index(docs: list[dict]) -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_text(filename: str, raw_bytes: bytes) -> str:
    """Extract clean UTF-8 text from supported text files and PDFs."""
    if len(raw_bytes) > MAX_DOC_BYTES:
        raise ValueError("File exceeds 2 MB limit.")

    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = []
        for page in reader.pages[:60]:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                pages.append(page_text)
        text = "\n\n".join(pages)
    elif ext in SUPPORTED_TEXT_EXTS or ext == "":
        text = raw_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Upload PDF, TXT, MD, CSV, JSON, or code files.")

    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        raise ValueError("No readable text found in document.")
    return cleaned


def chunk_text(text: str, chunk_size: int = 520, overlap: int = 80) -> list[str]:
    """Split text into paragraph-friendly overlapping chunks."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(para) and len(chunks) < MAX_CHUNKS_PER_DOC:
                end = min(len(para), start + chunk_size)
                chunks.append(para[start:end].strip())
                if end == len(para):
                    break
                start = max(start + 1, end - overlap)
            continue

        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            tail = current[-overlap:].strip() if current and overlap > 0 else ""
            current = f"{tail}\n{para}".strip() if tail and len(tail) + len(para) + 1 <= chunk_size else para

        if len(chunks) >= MAX_CHUNKS_PER_DOC:
            break

    if current and len(chunks) < MAX_CHUNKS_PER_DOC:
        chunks.append(current.strip())
    return chunks


def add_document(filename: str, raw_bytes: bytes) -> dict:
    """Parse, chunk, and persist an uploaded document into the local RAG index."""
    safe_name = Path(filename).name[:120] or "document.txt"
    text = extract_text(safe_name, raw_bytes)
    chunks = chunk_text(text)
    with _store_lock:
        docs = _load_index()
        existing_id = next((d.get("id") for d in docs if d.get("name") == safe_name and d.get("id")), None)
        doc_entry = {
            "id": existing_id or uuid.uuid4().hex[:10],
            "name": safe_name,
            "chars": len(text),
            "chunkCount": len(chunks),
            "uploadedAt": int(time.time()),
            "chunks": [{"text": c, "tokens": _tokenize(f"{safe_name} {c}")} for c in chunks],
        }
        docs = [d for d in docs if d.get("name") != safe_name]
        docs.append(doc_entry)
        _save_index(docs)

    return {
        "id": doc_entry["id"],
        "name": doc_entry["name"],
        "chars": doc_entry["chars"],
        "chunkCount": doc_entry["chunkCount"],
        "uploadedAt": doc_entry["uploadedAt"],
    }


def list_docs() -> list[dict]:
    with _store_lock:
        docs = _load_index()
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "chars": d.get("chars", 0),
            "chunkCount": d.get("chunkCount", len(d.get("chunks", []))),
            "uploadedAt": d.get("uploadedAt", 0),
        }
        for d in docs
    ]


def delete_document(doc_id: str) -> bool:
    with _store_lock:
        docs = _load_index()
        remaining = [d for d in docs if d.get("id") != doc_id]
        if len(remaining) == len(docs):
            return False
        _save_index(remaining)
        return True


_DOC_INTENT_RE = re.compile(
    r"(?i)\b(file|doc|docs|document|documents|pdf|attached|uploaded|attachment|"
    r"summarize|summary|read|contents?|resume|cv|notes?)\b"
)


def _match_target_doc(docs: list[dict], query: str) -> dict:
    """Pick the document explicitly named in query, or fall back to the most recently uploaded one."""
    q_lower = query.lower()
    for doc in reversed(docs):
        name = doc.get("name", "")
        stem = Path(name).stem.lower()
        if name.lower() in q_lower or (len(stem) >= 3 and stem in q_lower):
            return doc
    return docs[-1]


def _filter_docs(docs: list[dict], doc_ids: list[str] | None, query: str) -> list[dict]:
    # If the caller specifically provided doc_ids (e.g. conversation has attachments)
    if doc_ids is not None:
        if not doc_ids:
            # Conversation has no attachments - only match if the query explicitly names a document
            q_lower = query.lower()
            return [
                d for d in docs
                if d.get("name", "").lower() in q_lower
                or (len(Path(d.get("name", "")).stem) >= 4 and Path(d.get("name", "")).stem.lower() in q_lower)
            ]
        id_set = set(doc_ids)
        return [d for d in docs if d.get("id") in id_set]

    # If doc_ids is None (direct query without doc scope):
    # Only match if the query specifically refers to a file/document or names an uploaded file
    q_lower = query.lower()
    if _DOC_INTENT_RE.search(query) or any(Path(d.get("name", "")).stem.lower() in q_lower for d in docs):
        return docs
    return []


def read_doc_preview(query: str, max_chars: int = 2600, doc_ids: list[str] | None = None) -> dict | None:
    """Return clean extracted text for explicit 'read/show the file' commands."""
    with _store_lock:
        docs = _filter_docs(_load_index(), doc_ids, query)
    if not docs:
        return None
    target = _match_target_doc(docs, query)
    chunks = [ch.get("text", "") for ch in target.get("chunks", []) if ch.get("text")]
    combined = "\n\n".join(chunks).strip()
    if not combined:
        return None
    truncated = len(combined) > max_chars
    return {
        "name": target.get("name", "document"),
        "text": combined[:max_chars].rstrip() if truncated else combined,
        "truncated": truncated,
        "totalChars": target.get("chars", len(combined)),
    }


def search_docs(
    query: str,
    top_k: int = 4,
    max_total_chars: int = 1800,
    doc_ids: list[str] | None = None,
) -> list[dict]:
    """Retrieve top matching document chunks with BM25, falling back to leading chunks for generic file queries."""
    with _store_lock:
        docs = _filter_docs(_load_index(), doc_ids, query)

    if not docs:
        return []

    query_tokens = _tokenize(query)
    flat_chunks: list[tuple[str, str, list[str]]] = []
    for doc in docs:
        name = doc.get("name", "document")
        for ch in doc.get("chunks", []):
            toks = ch.get("tokens") or _tokenize(ch.get("text", ""))
            flat_chunks.append((name, ch.get("text", ""), toks))

    if not flat_chunks:
        return []

    n_chunks = len(flat_chunks)
    avg_len = sum(len(c[2]) for c in flat_chunks) / max(1, n_chunks)
    df: Counter[str] = Counter()
    for _, _, toks in flat_chunks:
        for term in set(toks):
            df[term] += 1

    k1 = 1.5
    b = 0.75
    scored: list[tuple[float, str, str]] = []
    query_lower = query.lower()

    for name, text, toks in flat_chunks:
        if not toks:
            continue
        tf = Counter(toks)
        dl = len(toks)
        score = 0.0
        matched_terms = 0
        for term in query_tokens:
            freq = tf.get(term, 0)
            if freq == 0:
                continue
            matched_terms += 1
            idf = math.log(1.0 + (n_chunks - df[term] + 0.5) / (df[term] + 0.5))
            denom = freq + k1 * (1.0 - b + b * (dl / max(1.0, avg_len)))
            score += idf * ((freq * (k1 + 1.0)) / denom)

        is_named = name.lower() in query_lower or Path(name).stem.lower() in query_lower
        if is_named:
            score += 2.0

        # Require either:
        # 1. Document explicitly named in query, OR
        # 2. At least 2 distinct query keywords match, OR
        # 3. High BM25 score (>= 2.5)
        if is_named or (matched_terms >= 2 and score >= 1.2) or score >= 2.5:
            scored.append((score, name, text))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected: list[dict] = []
    used_chars = 0
    for score, name, text in scored[: top_k * 2]:
        snippet = text[:400].strip()
        if used_chars + len(snippet) > max_total_chars and selected:
            break
        selected.append({"name": name, "score": round(score, 2), "snippet": snippet})
        used_chars += len(snippet)
        if len(selected) >= top_k:
            break

    # Fallback: if the user asked generically about "the file" / "pdf" / "summarize" / "read",
    # return the opening chunks of the matching or most recent document.
    if not selected and (_DOC_INTENT_RE.search(query) or any(Path(d.get("name", "")).stem.lower() in query_lower for d in docs)):
        target = _match_target_doc(docs, query)
        t_name = target.get("name", "document")
        for ch in target.get("chunks", [])[:top_k]:
            snippet = ch.get("text", "")[:400].strip()
            if not snippet:
                continue
            if used_chars + len(snippet) > max_total_chars and selected:
                break
            selected.append({"name": t_name, "score": 1.0, "snippet": snippet})
            used_chars += len(snippet)

    return selected

