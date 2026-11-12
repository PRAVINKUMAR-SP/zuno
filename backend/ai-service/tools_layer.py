"""Safety guardrails, deterministic AST math/time tools, and lightweight web search for Zuno."""

from __future__ import annotations

import ast
import datetime as dt
import html
import math
import operator
import re
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
    r"(?i)\b(latest|today|current|news|weather|stock\s+price|exchange\s+rate|"
    r"who\s+won|(?:match|live|cricket|football|sports)\s+score|release\s+date|"
    r"newest\s+version|search\s+web|search\s+online|look\s+up\s+online|2025|2026)\b"
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


def try_run_local_tool(query: str) -> dict | None:
    """Layer 7 (Tool Calling): Execute safe deterministic calculator and date/time tools."""
    q_norm = re.sub(r"\s+", " ", query.lower()).strip(" ?!.")

    if q_norm in {
        "what is today's date", "what is todays date", "today's date", "todays date",
        "current date", "what date is today", "what day is today",
        "what time is it", "current time", "what is the time", "date and time",
    }:
        now = dt.datetime.now()
        formatted = now.strftime("%A, %B %d, %Y at %I:%M %p")
        return {
            "tool": "clock",
            "result": formatted,
            "direct_reply": f"Current local date and time: **{formatted}**.",
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


def should_search_web(query: str, use_web: bool | None) -> bool:
    if use_web is True:
        return True
    if use_web is False:
        return False
    return bool(_WEB_TRIGGER_RE.search(query))


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


def web_search(query: str, max_results: int = 3) -> list[dict]:
    """Layer 6 (Web Search): Fetch top DuckDuckGo HTML search results safely."""
    safe_query = redact_sensitive_text(query).strip()[:220]
    if not safe_query:
        return []

    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": safe_query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; ZunoAI/1.0)"},
            timeout=5.5,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return []
    except Exception:
        return []

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

    results: list[dict] = []
    for idx, (href, raw_title) in enumerate(title_links[:max_results]):
        title = _strip_html(raw_title)
        url = _decode_ddg_href(href)
        snip = ""
        if idx < len(snippets):
            snip = _strip_html(snippets[idx][0] or snippets[idx][1])
        if title and url:
            results.append({
                "title": title[:120],
                "url": url[:220],
                "snippet": snip[:260],
            })
    return results

