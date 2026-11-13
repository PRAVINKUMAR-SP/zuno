"""End-to-end regression tests for Zuno AI streaming pipeline and multi-lingual factual accuracy."""

import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8001"


def test_health():
    print("[TEST 1] Checking /health...")
    req = urllib.request.Request(f"{BASE_URL}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("ready") is True, f"Expected ready=True, got {data}"
        print(f"  PASS: health ok (model={data.get('model')})")


def _read_sse_events(url: str, payload: dict, max_read_seconds: float = 50.0):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    events = []
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=max_read_seconds) as resp:
        current_event = None
        for raw_line in resp:
            if time.time() - t0 > max_read_seconds:
                break
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()
                try:
                    parsed = json.loads(data_str)
                    ev_type = current_event or parsed.get("type")
                    events.append({"event": ev_type, "data": parsed})
                    if ev_type == "done":
                        break
                except json.JSONDecodeError:
                    pass
                current_event = None
    return events


def test_greeting_stream():
    print("[TEST 2] Testing greeting stream...")
    events = _read_sse_events(
        f"{BASE_URL}/v1/chat/stream",
        {"messages": [{"role": "user", "content": "Hi"}], "mode": "auto"},
        max_read_seconds=15.0,
    )
    event_names = [e["event"] for e in events]
    assert "meta" in event_names, f"Expected meta event in {event_names}"
    assert "token" in event_names, f"Expected token event in {event_names}"
    assert "done" in event_names, f"Expected done event in {event_names}"

    tokens = [e["data"].get("content", "") or e["data"].get("text", "") for e in events if e["event"] == "token"]
    full_text = "".join(tokens)
    print(f"  PASS: Greeting completed smoothly ({len(tokens)} tokens): '{full_text[:50]}...'")


def test_web_auto_historical_query():
    print("[TEST 3] Testing Web Auto historical entity grounding (Cholas)...")
    events = _read_sse_events(
        f"{BASE_URL}/v1/chat/stream",
        {"messages": [{"role": "user", "content": "cholas history explain"}], "mode": "auto"},
        max_read_seconds=45.0,
    )
    event_names = [e["event"] for e in events]
    tokens = [e["data"].get("content", "") or e["data"].get("text", "") for e in events if e["event"] == "token"]
    full_text = "".join(tokens).lower()

    # Check for sources event or sources in done event
    done_ev = next((e["data"] for e in events if e["event"] == "done"), {})
    sources = done_ev.get("sources", [])
    print(f"  Sources found: {len(sources)}")
    print(f"  Response sample: {full_text[:120]}...")

    # Must NOT hallucinate that Raja Raja Chola is Tamil grammar
    assert "grammar" not in full_text and "இலக்கண" not in full_text, (
        f"Detected grammar hallucination in response: {full_text}"
    )
    print("  PASS: Factual historical grounding verified (no grammar hallucination)")


def test_language_leak_prevention():
    print("[TEST 4] Testing language leak prevention across turns...")
    # Multi-turn: Turn 1 Tamil, Turn 2 English
    messages = [
        {"role": "user", "content": "வணக்கம்"},
        {"role": "assistant", "content": "வணக்கம்! உங்களுக்கு எவ்வாறு உதவ முடியும்?"},
        {"role": "user", "content": "Explain who built Thanjavur big temple in 2 short sentences."},
    ]
    events = _read_sse_events(
        f"{BASE_URL}/v1/chat/stream",
        {"messages": messages, "mode": "auto"},
        max_read_seconds=30.0,
    )
    tokens = [e["data"].get("content", "") or e["data"].get("text", "") for e in events if e["event"] == "token"]
    full_text = "".join(tokens)
    print(f"  Turn 2 response: {full_text[:100]}...")

    # Must be in English, not Tamil
    tamil_chars = sum(1 for c in full_text if "\u0B80" <= c <= "\u0BFF")
    english_chars = sum(1 for c in full_text if "a" <= c.lower() <= "z")
    assert english_chars > tamil_chars, f"Response should be in English, got: {full_text}"
    print("  PASS: Turn 2 correctly responded in English despite prior Tamil turn")


def test_stream_abort_and_recovery():
    print("[TEST 5] Testing client disconnect abort and worker recovery...")
    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/stream",
        data=json.dumps({"messages": [{"role": "user", "content": "write a story"}], "mode": "detailed"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    resp = urllib.request.urlopen(req, timeout=10)
    # Read first couple of lines then abort
    for _ in range(3):
        resp.readline()
    resp.close()
    abort_duration = time.time() - t0
    print(f"  Stream closed mid-flight in {abort_duration:.2f}s")

    # Immediate follow-up query to verify thread pool was not stuck in deadlock
    t1 = time.time()
    follow_req = urllib.request.Request(f"{BASE_URL}/health")
    with urllib.request.urlopen(follow_req, timeout=5) as health_resp:
        h_data = json.loads(health_resp.read().decode("utf-8"))
        assert h_data.get("ready") is True
    print(f"  PASS: Server healthy and receptive immediately after abort ({time.time() - t1:.2f}s)")


if __name__ == "__main__":
    test_health()
    test_greeting_stream()
    test_web_auto_historical_query()
    test_language_leak_prevention()
    test_stream_abort_and_recovery()
    print("\nALL REGRESSION TESTS PASSED SUCCESSFULLY!")
