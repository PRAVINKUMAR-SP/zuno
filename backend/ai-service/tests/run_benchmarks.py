import json
import time
import urllib.request

BASE = "http://127.0.0.1:8001"

def run_bench(name, payload):
    req = urllib.request.Request(
        f"{BASE}/v1/chat/stream",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    first_token_time = None
    tokens = []
    done_data = {}
    sources = []
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        for raw in resp:
            line = raw.decode("utf-8").rstrip()
            if line.startswith("data:"):
                try:
                    d = json.loads(line[5:].strip())
                    ev_type = d.get("type")
                    if ev_type == "token":
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - t0
                        tokens.append(d.get("content", ""))
                    elif ev_type == "sources":
                        sources = d.get("sources", [])
                    elif ev_type == "done":
                        done_data = d
                except Exception:
                    pass

    total_time = time.perf_counter() - t0
    ttft = first_token_time if first_token_time is not None else total_time
    content = "".join(tokens)
    out_tokens = len(tokens)
    gen_time = max(0.01, (total_time - ttft))
    tps = round(out_tokens / gen_time, 1) if out_tokens > 1 else 0.0

    return {
        "name": name,
        "ttft_ms": round(ttft * 1000, 1),
        "total_s": round(total_time, 2),
        "tokens": out_tokens,
        "tps": tps,
        "tools": done_data.get("toolsUsed", []),
        "sources_count": len(sources) or len(done_data.get("sources", [])),
        "intent": done_data.get("intent", ""),
        "sample": content[:100].replace("\n", " ").strip(),
    }

benchmarks = [
    ("Deterministic Clock Tool", {"messages": [{"role": "user", "content": "today what day"}], "mode": "auto"}),
    ("Greeting Query", {"messages": [{"role": "user", "content": "Hi"}], "mode": "auto"}),
    ("Simple English Fact", {"messages": [{"role": "user", "content": "What is an API in 2 sentences?"}], "mode": "auto"}),
    ("Web Auto Search (CM)", {"messages": [{"role": "user", "content": "Tell TamilNadu CM"}], "mode": "auto"}),
    ("Tamil Historical Query", {"messages": [{"role": "user", "content": "ராஜ ராஜ சோழன் பற்றி தமிழ் மொழியில் விளக்குங்கள்"}], "mode": "auto"}),
    ("Coding Query", {"messages": [{"role": "user", "content": "Write a Python function to check palindrome"}], "mode": "auto"}),
]

results = []
for name, p in benchmarks:
    res = run_bench(name, p)
    results.append(res)
    print(f"BENCHMARK: {name:<26} | TTFT: {res['ttft_ms']:>6.1f}ms | Total: {res['total_s']:>5.2f}s | Tokens: {res['tokens']:>3} | TPS: {res['tps']:>4.1f}")

print("\n" + "="*80)
print(json.dumps(results, indent=2, ensure_ascii=False))
