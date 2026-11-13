"""Safety guardrails, deterministic AST math/time tools, and lightweight web search for Zuno."""

from __future__ import annotations

import ast
import datetime as dt
import html
import math
import operator
import re
import threading
from urllib.parse import parse_qs, unquote, urlparse

import httpx

_SECRET_PATTERNS = (
    (re.compile(r"(?i)(bearer\s+)[a-z0-9\-._~+/]+=*"), r"\1[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)(password|passwd|api[_-]?key|secret|token)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
)

_UNSAFE_PATTERNS = (
    re.compile(r"(?i)\b(rm\s+-rf\s+/|format\s+c:|del\s+/f\s+/s\s+/q\s+c:\\)\b"),
    re.compile(r"(?i)\b(ransomware|keylogger|reverse\s+shell|ddos\s+attack|steal\s+password)\b"),
    re.compile(r"(?i)\b(bypass\s+auth|sql\s+injection\s+payload\s+for\s+my\s+target|hack\s+into)\b"),
)

_WEB_TRIGGER_RE = re.compile(
    r"(?i)\b("
    r"latest|today|current|curent|news|weather|stock\s+price|exchange\s+rate|"
    r"who\s+won|(?:match|live|cricket|football|sports)\s+score|release\s+date|"
    r"newest\s+version|search\s+web|search\s+online|search\s+google|google\s+it|"
    r"check\s+online|check\s+(?:the\s+)?internet|check\s+(?:the\s+)?web|look\s+(?:it\s+)?up|verify(?:\s+online)?|check\s+again|check\s+it|2024|2025|2026|"
    r"compare|comparison|versus|\bvs\b|difference\s+between|which\s+is\s+better|best\s+[a-z]+|"
    r"who\s+(?:is|was|were|are)|whom|history|historical|dynasty|empire|emperor|kingdom|ruler|king|queen|monarch|reign|"
    r"chola[s]?|cholan|pandya[s]?|pandiyan|chera[s]?|cheran|pallava[s]?|mughal[s]?|maratha[s]?|maurya|gupta|"
    r"temple|brihadisvara|thanjavur|monument|battle\s+of|war\s+of|treaty|"
    r"founder|founded|ceo\s+of|net\s+worth|biography|born|died|"
    r"capital\s+of|population\s+of|price\s+of|where\s+is|when\s+(?:did|was|is)|"
    r"explain\s+about|tell\s+(?:me\s+)?about|information\s+about|details\s+about|"
    r"(?:cm|chief\s+minister|pm|prime\s+minister|governor|president|minister|mla|mp|mayor)\b|"
    r"tamil\s*nadu\s+cm|tn\s+cm|current\s+cm|curent\s+cm|tell\s+cm|"
    r"(?:tvk|tamilaga\s+vettri\s+kazhagam|dmk|aiadmk|bjp|congress|aap)\b|"
    r"(?:vijay|stalin|modi|rahul)\b|"
    r"no\s+the\s+(?:current|curent)|the\s+(?:current|curent)\s+[a-z]+\s+is|"
    r"election|sworn\s+in|oath|"
    r"(?:you\s+know|do\s+you\s+know)\s+[a-z0-9]+"
    r")\b"
)
_TAMIL_WEB_TRIGGER_RE = re.compile(
    r"[\u0B80-\u0BFF]*(?:"
    r"சோழ|பாண்டிய|சேர|பல்லவ|மன்னர்|அரசர்|பேரரசு|வரலாறு|கோயில்|கோவில்|தஞ்சை|பெரிய\s*கோயில்|"
    r"யார்|எப்போது|எங்கே|எப்படி|என்ன|விளக்கு|கூறு|பற்றி|பத்தி"
    r")[\u0B80-\u0BFF]*"
)
_TAMIL_ENTITY_RE = re.compile(r"[\u0B80-\u0BFF]{4,}")

_SKIP_WEB_RE = re.compile(
    r"(?i)^(?:hi|hii|hello|hey|yo|thanks|thank\s+you|ok|okay|bye|good\s+morning|"
    r"who\s+are\s+you|about\s+you|tell\s+me\s+about\s+yourself|what\s+can\s+you\s+do|how\s+are\s+you)\s*[.?!]*$"
)

_SAFE_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_SAFE_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_SAFE_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
    "pow": pow,
    "factorial": lambda n: math.factorial(int(n)) if 0 <= int(n) <= 100 else (_ for _ in ()).throw(ValueError("factorial range 0..100")),
}

_SAFE_CONSTS = {
    "pi": math.pi,
    "e": math.e,
}


def redact_sensitive_text(text: str) -> str:
    """Layer 9 (Safety): Strip likely API tokens or inline passwords before logging or web queries."""
    cleaned = text
    for pat, repl in _SECRET_PATTERNS:
        cleaned = pat.sub(repl, cleaned)
    return cleaned


def check_unsafe_request(text: str) -> str | None:
    """Layer 9 (Safety): Return a refusal message if request asks for destructive or harmful actions."""
    for pat in _UNSAFE_PATTERNS:
        if pat.search(text):
            return "I can't help with destructive commands, credential theft, or unauthorized access. Ask me about defensive security concepts or safe local tasks instead."
    return None


def _eval_ast_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value) if isinstance(node.value, float) else node.value
    if isinstance(node, ast.Name):
        key = node.id.lower()
        if key in _SAFE_CONSTS:
            return _SAFE_CONSTS[key]
        raise ValueError(f"Unknown symbol: {node.id}")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARY_OPS:
        return _SAFE_UNARY_OPS[type(node.op)](_eval_ast_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BIN_OPS:
        left = _eval_ast_node(node.left)
        right = _eval_ast_node(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 1000 or abs(left) > 1e9):
            raise ValueError("Exponent too large")
        return _SAFE_BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn_name = node.func.id.lower()
        if fn_name not in _SAFE_FUNCS or node.keywords:
            raise ValueError(f"Disallowed function: {node.func.id}")
        args = [_eval_ast_node(a) for a in node.args]
        return _SAFE_FUNCS[fn_name](*args)
    raise ValueError("Unsupported expression")


def _extract_math_expression(text: str) -> str | None:
    s = text.strip()
    s_lower = s.lower().rstrip(" ?.=!")
    s_lower = re.sub(r"^(?:what\s+is|calculate|compute|eval|evaluate|solve)\s+", "", s_lower)

    pct_match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*%\s*of\s*(-?\d+(?:\.\d+)?)", s_lower)
    if pct_match:
        return f"({pct_match.group(1)} / 100) * {pct_match.group(2)}"

    expr = s_lower.replace("^", "**").replace("×", "*").replace("÷", "/").replace(",", "")
    if not re.fullmatch(r"[0-9+\-*/().%\s_a-zA-Z]+", expr):
        return None
    if not any(ch.isdigit() for ch in expr):
        return None
    if not re.search(r"[+\-*/%]|sqrt|sin|cos|tan|log|factorial|pow|abs|round", expr):
        return None
    return expr


_DATE_TIME_QUERY_RE = re.compile(
    r"(?i)^("
    r"(?:what\s+is\s+)?today(?:'s)?\s+(?:day|date|time)|"
    r"today\s+what\s+(?:day|date|time)|"
    r"what\s+(?:day|date|time)\s+(?:is\s+)?today|"
    r"what\s+day\s+is\s+it|"
    r"which\s+day\s+is\s+today|"
    r"day\s+today|date\s+today|time\s+now|current\s+(?:date|day|time|year)|"
    r"what\s+is\s+the\s+date|what\s+is\s+the\s+time|what\s+is\s+the\s+day|"
    r"what\s+date\s+is\s+today|"
    r"what\s+year\s+is\s+(?:it|this)|current\s+year|which\s+year|"
    r"what\s+time\s+is\s+it|"
    r"today(?:'s)?\s+date\s+and\s+time|date\s+and\s+time|"
    r"inniku\s+(?:enna\s+)?(?:naal|date|day)|innaiku\s+(?:enna\s+)?(?:naal|date)|"
    r"இன்று\s+என்ன\s+நாள்|இன்றைய\s+தேதி|இன்றைய\s+நாள்"
    r")\s*[.?!]*$"
)


def get_current_datetime_info() -> dict[str, str]:
    tz_ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    now = dt.datetime.now(tz_ist)
    return {
        "day": now.strftime("%A"),
        "date": now.strftime("%B %d, %Y"),
        "time": now.strftime("%I:%M %p"),
        "year": str(now.year),
        "iso": now.strftime("%Y-%m-%d"),
        "formatted": now.strftime("%A, %B %d, %Y at %I:%M %p IST"),
    }


def try_run_local_tool(query: str) -> dict | None:
    """Layer 7 (Tool Calling): Execute safe deterministic calculator and date/time tools."""
    q_norm = re.sub(r"\s+", " ", query.lower()).strip(" ?!.")

    if _DATE_TIME_QUERY_RE.match(q_norm) or q_norm in {
        "what is today's date", "what is todays date", "today's date", "todays date",
        "current date", "what date is today", "what day is today", "today what day",
        "what time is it", "current time", "what is the time", "date and time", "time now",
    }:
        dt_info = get_current_datetime_info()
        if re.search(r"(?i)\bday\b", q_norm) and not re.search(r"(?i)\bdate\b", q_norm):
            reply = f"Today is **{dt_info['day']}**, {dt_info['date']}."
        elif re.search(r"(?i)\btime\b", q_norm):
            reply = f"The current time is **{dt_info['time']}** IST ({dt_info['day']}, {dt_info['date']})."
        elif re.search(r"(?i)\byear\b", q_norm):
            reply = f"The current year is **{dt_info['year']}** (today is {dt_info['day']}, {dt_info['date']})."
        else:
            reply = f"Today's date is **{dt_info['date']}** ({dt_info['day']}) and the time is **{dt_info['time']}** IST."
        return {
            "tool": "clock",
            "result": dt_info["formatted"],
            "direct_reply": reply,
        }

    expr = _extract_math_expression(query)
    if expr:
        try:
            tree = ast.parse(expr, mode="eval")
            val = _eval_ast_node(tree)
            if isinstance(val, float) and val.is_integer():
                display = str(int(val))
            elif isinstance(val, float):
                display = f"{val:.8g}"
            else:
                display = str(val)
            return {
                "tool": "calculator",
                "expression": expr,
                "result": display,
                "direct_reply": f"**Result:** `{display}`",
            }
        except Exception:
            return None

    return None


_http_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_http_client() -> httpx.Client:
    global _http_client
    with _client_lock:
        if _http_client is None or _http_client.is_closed:
            _http_client = httpx.Client(
                timeout=2.8,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
                follow_redirects=True,
            )
        return _http_client


def should_search_web(query: str, use_web: bool | None) -> bool:
    if use_web is True:
        return True
    if use_web is False:
        return False
    clean = query.strip()
    if _SKIP_WEB_RE.match(clean) or len(clean.split()) < 2:
        return False
    return bool(
        _WEB_TRIGGER_RE.search(clean)
        or _TAMIL_WEB_TRIGGER_RE.search(clean)
        or _TAMIL_ENTITY_RE.search(clean)
    )


def _decode_ddg_href(raw_href: str) -> str:
    href = html.unescape(raw_href)
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    return href


def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _clean_search_query(q: str) -> str:
    cleaned = re.sub(
        r"(?i)\b(?:please\s+)?(?:check\s+online|search\s+online|check\s+(?:the\s+)?internet|check\s+(?:the\s+)?web|search\s+google|google\s+it|look\s+(?:it\s+)?up|verify(?:\s+online)?|check\s+it|explain\s+about|tell\s+(?:me\s+)?about|information\s+about|details\s+about|who\s+(?:is|was|were|are)|what\s+is|give\s+details\s+on|in\s+tamil|in\s+english|history\s+explain|explain|you\s+know|do\s+you\s+know)\b",
        " ",
        q,
    )
    cleaned = re.sub(
        r"[\u0B80-\u0BFF]*(?:விளக்குங்கள்|விளக்குக|விளக்கு|சொல்லுங்கள்|சொல்லு|கூறுங்கள்|கூறு|பற்றி|பத்தி|தமிழ்\s*மொழியில்)[\u0B80-\u0BFF]*",
        " ",
        cleaned,
    )
    # Strip leading negative or conversational words like "no the"
    cleaned = re.sub(r"(?i)^(?:no\s+)?(?:the\s+)?", " ", cleaned.strip())
    # Expand abbreviations and correct common typos
    cleaned = re.sub(r"(?i)\bcurent\b", "current", cleaned)
    cleaned = re.sub(r"(?i)\bcm\b", "Chief Minister", cleaned)
    cleaned = re.sub(r"(?i)\bpm\b", "Prime Minister", cleaned)
    cleaned = re.sub(r"(?i)\btvk\b", "TVK Tamilaga Vettri Kazhagam", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?!.,")

    is_movie = bool(re.search(r"(?i)\b(movie|film|cinema|song|actor|actress)\b|திரைப்படம்|படம்|பாடல்", q))
    is_history_entity = bool(re.search(r"(?i)\b(chola[s]?|cholan|pandya[s]?|pandiyan|chera[s]?|pallava[s]?|dynasty|emperor|king|ruler|empire)\b|சோழ|பாண்டிய|சேர|பல்லவ|மன்னர்|அரசர்", q))
    if is_history_entity and not is_movie:
        if not bool(re.search(r"[\u0B80-\u0BFF]", cleaned)):
            if "history" not in cleaned.lower() and "dynasty" not in cleaned.lower():
                cleaned += " history"

    return cleaned if len(cleaned) >= 3 else q


def search_wikipedia(query: str, max_results: int = 2) -> list[dict]:
    """Fallback encyclopedia lookup: rate-limit-free, ultra-fast factual grounding."""
    has_tamil = bool(re.search(r"[\u0B80-\u0BFF]", query))
    lang = "ta" if has_tamil else "en"
    clean_q = re.sub(r"(?i)\b(?:in\s+tamil|in\s+english|tell\s+me\s+about|explain\s+about)\b", " ", query).strip()
    if not clean_q:
        clean_q = query
    params = {
        "action": "query",
        "list": "search",
        "srsearch": clean_q,
        "utf8": 1,
        "format": "json",
        "srlimit": max_results,
    }
    client = _get_http_client()
    try:
        url = f"https://{lang}.wikipedia.org/w/api.php"
        resp = client.get(
            url,
            params=params,
            headers={"User-Agent": "ZunoAI/1.0 (contact@zuno.ai)"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results: list[dict] = []
        for item in data.get("query", {}).get("search", []):
            clean_snip = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
            clean_snip = re.sub(r"\s+", " ", html.unescape(clean_snip)).strip()
            title = item.get("title", "")
            enc_title = title.replace(" ", "_")
            results.append({
                "title": f"{title} - Wikipedia",
                "url": f"https://{lang}.wikipedia.org/wiki/{enc_title}",
                "snippet": clean_snip[:150],
            })
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def web_search(query: str, max_results: int = 2) -> list[dict]:
    """Layer 6 (Web Search): Ultra-fast pooled DuckDuckGo search with Wikipedia fallback."""
    refined = _clean_search_query(query)
    safe_query = redact_sensitive_text(refined).strip()[:180]
    if not safe_query:
        return []

    is_movie_intent = bool(re.search(r"(?i)\b(movie|film|cinema|song)\b|திரைப்படம்|படம்", query))
    is_history = bool(re.search(r"(?i)\b(chola[s]?|cholan|pandya[s]?|pandiyan|chera[s]?|pallava[s]?|dynasty|emperor|king|ruler|empire|temple|thanjavur|brihadisvara)\b|சோழ|பாண்டிய|சேர|பல்லவ|மன்னர்|அரசர்|கோயில்|கோவில்|தஞ்சை", query))
    has_tamil = bool(re.search(r"[\u0B80-\u0BFF]", query))

    # Fast-path for historical entities & Tamil encyclopedia queries: Wikipedia responds in ~200ms with zero rate limits
    if (is_history or has_tamil) and not is_movie_intent:
        wiki_hits = search_wikipedia(refined, max_results=max_results)
        valid_wiki = [
            h for h in wiki_hits
            if not re.search(r"(?i)(?:திரைப்படம்|திரைக்கதை|\bfilm\b|\bmovie\b)", h["title"])
        ]
        if valid_wiki:
            return valid_wiki[:max_results]

    results: list[dict] = []
    client = _get_http_client()
    try:
        resp = client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": safe_query},
        )
        if resp.status_code == 200:
            page = resp.text
            title_links = re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                page,
                flags=re.DOTALL,
            )
            snippets = re.findall(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>',
                page,
                flags=re.DOTALL,
            )
            for idx, (href, raw_title) in enumerate(title_links):
                title = _strip_html(raw_title)
                url = _decode_ddg_href(href)
                # Skip entertainment/movie hits when user asked about historical kings/dynasties
                if not is_movie_intent and re.search(r"(?i)(?:திரைப்படம்|திரைக்கதை|\bfilm\b|\bmovie\b)", title):
                    continue
                snip = ""
                if idx < len(snippets):
                    snip = _strip_html(snippets[idx][0] or snippets[idx][1])
                if title and url:
                    results.append({
                        "title": title[:80],
                        "url": url[:180],
                        "snippet": snip[:150],
                    })
                    if len(results) >= max_results:
                        break
    except Exception:
        pass

    # If DDG was rate-limited (status 202) or returned empty, fall back to Wikipedia
    if not results:
        wiki_hits = search_wikipedia(refined, max_results=max_results)
        results = [
            h for h in wiki_hits
            if is_movie_intent or not re.search(r"(?i)(?:திரைப்படம்|திரைக்கதை|\bfilm\b|\bmovie\b)", h["title"])
        ]

    return results

