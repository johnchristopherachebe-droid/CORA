"""CORA skills: reusable capabilities. Built-in skills are deterministic (no model needed) and work offline.

Stored skills (the existing `cora_skills` table: name, description, instructions) are plain-language instruction sets that
need a language model to run, so in provider-independent mode they are listed but reported as unavailable, never faked.
"""
import ast
import math
import operator
import os
import re
from datetime import datetime, timezone

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv, ast.Pow: operator.pow}
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round}


def safe_eval(expression: str):
    """Evaluate arithmetic only. No names, attributes or arbitrary calls."""
    tree = ast.parse(expression.strip(), mode="eval")

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and (abs(right) > 64 or abs(left) > 1e9):
                raise ValueError("Exponent too large.")
            return _BIN[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords and len(node.args) <= 2:
            return _FUNCS[node.func.id](*[walk(a) for a in node.args])
        raise ValueError("Unsupported expression.")
    return walk(tree)


_WORD_OPS = ((r"\bto the power of\b", "**"), (r"\bmultiplied by\b", "*"), (r"\bdivided by\b", "/"), (r"\btimes\b", "*"),
             (r"\bplus\b", "+"), (r"\bminus\b", "-"), (r"\bover\b", "/"))


def _extract_expression(text: str):
    lowered = (text or "").lower().replace(",", "")
    percent = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:%|percent)\s*of\s*(-?\d+(?:\.\d+)?)", lowered)
    if percent:
        return f"({percent.group(1)} / 100) * {percent.group(2)}"
    root = re.search(r"square root of\s*(\d+(?:\.\d+)?)", lowered)
    if root:
        return f"sqrt({root.group(1)})"
    for pattern, symbol in _WORD_OPS:
        lowered = re.sub(pattern, f" {symbol} ", lowered)
    lowered = re.sub(r"(?<=\d)\s*x\s*(?=\d)", " * ", lowered).replace("^", "**").replace("×", "*").replace("÷", "/")
    found = re.findall(r"[\d.()+\-*/\s]{3,}", lowered)
    for candidate in sorted(found, key=len, reverse=True):
        candidate = candidate.strip()
        if re.search(r"\d", candidate) and re.search(r"[+\-*/]", candidate.lstrip("-+")):
            return candidate
    return None


def _calc_match(text):
    expression = _extract_expression(text)
    return {"expression": expression} if expression else None


def _calc_run(args, ctx=None):
    expression = args["expression"]
    try:
        value = safe_eval(expression)
    except ZeroDivisionError:
        return {"ok": False, "answer": "That divides by zero, which has no answer.", "explanation": f"Evaluated {expression}."}
    except (ValueError, SyntaxError, TypeError, OverflowError):
        return {"ok": False, "answer": "", "explanation": "I could not read that as a plain arithmetic expression."}
    shown = int(value) if isinstance(value, float) and value.is_integer() and abs(value) < 1e15 else round(value, 10) if isinstance(value, float) else value
    return {"ok": True, "answer": f"{expression.strip()} = {shown}", "explanation": "Calculated exactly with CORA's built-in calculator (no AI model involved).", "value": shown}


def _time_match(text):
    t = (text or "").lower()
    if re.search(r"\bwhat(?:'s| is)?(?: the)? (?:date|day|time)\b|\bwhat day is (?:it|today)\b|\btoday(?:'s)? date\b|\bcurrent (?:date|time)\b", t):
        return {}
    return None


def _time_run(args, ctx=None):
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(os.getenv("CORA_TIMEZONE", "UTC").strip() or "UTC")
    except Exception:
        zone = timezone.utc
    moment = (ctx or {}).get("now") or datetime.now(zone)
    return {"ok": True, "answer": moment.strftime("It is %A %d %B %Y, %H:%M (%Z)."), "explanation": "Read from the server clock."}


BUILTIN = {
    "calculator": {"description": "Exact arithmetic: + - * / ** %, brackets, percentages, square roots.", "match": _calc_match, "run": _calc_run, "needs_model": False},
    "date_time": {"description": "Today's date, day and time from the server clock.", "match": _time_match, "run": _time_run, "needs_model": False},
}


def select(text):
    """Skills that apply to this text, as [(name, args)]."""
    chosen = []
    for name, skill in BUILTIN.items():
        args = skill["match"](text)
        if args is not None:
            chosen.append((name, args))
    return chosen


def run(name, args, ctx=None):
    if name not in BUILTIN:
        return {"ok": False, "answer": "", "explanation": "Unknown skill."}
    return BUILTIN[name]["run"](args, ctx)


def list_skills(get_connection=None):
    skills = [{"name": n, "description": s["description"], "kind": "built-in", "needs_model": False, "available_offline": True} for n, s in BUILTIN.items()]
    if get_connection:
        try:
            with get_connection() as conn:
                rows = conn.execute("SELECT name, description FROM cora_skills ORDER BY name").fetchall()
            skills += [{"name": r[0], "description": r[1], "kind": "stored instructions", "needs_model": True, "available_offline": False} for r in rows]
        except Exception:
            pass  # the older table may not exist yet
    return skills
