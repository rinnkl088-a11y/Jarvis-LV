"""
core/memory2.py — layered memory (PHASE 9, additive).

Layers: SHORT_TERM (session buffer) | EPISODIC (history.jsonl) |
SEMANTIC (facts) | PREFERENCES | PROCEDURAL (workflows).
Existing memory/memory_manager.py untouched; this reads it when
available and adds search/update/forget/summarize with scoring.

Privacy: store() refuses secrets (keys, tokens, passwords).
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
import sys

SHORT_TERM = "short_term"
EPISODIC = "episodic"
SEMANTIC = "semantic"
PREFERENCES = "preferences"
PROCEDURAL = "procedural"

LAYERS = (SHORT_TERM, EPISODIC, SEMANTIC, PREFERENCES, PROCEDURAL)

_SECRET_PAT = re.compile(r"(api[_-]?key|token|password|secret|credential)",
                         re.IGNORECASE)
_MAX_SHORT = 30


def _base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_lock = threading.Lock()
_short: list[dict] = []


def _looks_secret(text: str) -> bool:
    return bool(_SECRET_PAT.search(text or ""))


def store(layer: str, text: str, topic: str = "") -> dict:
    text = (text or "").strip()[:1000]
    if not text:
        return {"ok": False, "error": "empty"}
    if layer not in LAYERS:
        return {"ok": False, "error": f"unknown layer '{layer}'"}
    if _looks_secret(text):
        return {"ok": False, "error": "refused: looks like a secret"}
    rec = {"ts": time.time(), "layer": layer, "topic": topic[:80], "text": text}
    with _lock:
        if layer == SHORT_TERM:
            _short.append(rec)
            del _short[:-_MAX_SHORT]
        else:
            try:
                from core.history import append as _append
                _append(f"{layer}:{topic}" if topic else layer, text)
            except Exception as e:
                return {"ok": False, "error": str(e)[:150]}
    return {"ok": True}


def _score(query: str, text: str) -> float:
    q = query.lower().split()
    t = text.lower()
    if not q:
        return 0.0
    hit = sum(1 for w in q if w in t)
    return hit / len(q)


def search(query: str, layers=None, limit: int = 8) -> list[dict]:
    layers = layers or [SEMANTIC, PREFERENCES, PROCEDURAL, EPISODIC]
    out: list[dict] = []
    with _lock:
        for r in _short:
            if r["layer"] in layers:
                s = _score(query, r["text"])
                if s > 0:
                    out.append({**r, "score": s})
    try:
        from core.history import recent as _recent
        for r in _recent(200):
            role = str(r.get("role", ""))
            if ":" in role:
                layer = role.split(":")[0]
            else:
                layer = role if role in LAYERS else EPISODIC
            if layer in layers:
                s = _score(query, str(r.get("text", "")))
                if s > 0:
                    out.append({"layer": layer, "text": r.get("text", ""),
                                "ts": r.get("ts", 0), "score": s})
    except Exception:
        pass
    # Semantic facts from long_term.json when present.
    try:
        p = _base() / "memory" / "long_term.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for cat, vals in data.items():
                if isinstance(vals, dict):
                    for k, v in vals.items():
                        txt = f"{cat}.{k}: {v}"
                        s = _score(query, txt)
                        if s > 0 and SEMANTIC in layers:
                            out.append({"layer": SEMANTIC, "text": txt,
                                        "ts": 0, "score": s + 0.1})
    except (OSError, ValueError):
        pass
    out.sort(key=lambda r: (r.get("score", 0), r.get("ts", 0)), reverse=True)
    return out[:limit]


def forget(topic: str, layers=None) -> int:
    topic = (topic or "").lower().strip()
    if not topic:
        return 0
    layers = set(layers or [])
    n = 0
    with _lock:
        global _short
        before = len(_short)
        _short = [r for r in _short
                  if topic not in r["text"].lower() or
                  (layers and r["layer"] not in layers)]
        n += before - len(_short)
    # Episodic file entries are editable too: drop matching lines.
    try:
        from core.history import _HISTORY as _hf
        lines = _hf.read_text(encoding="utf-8").splitlines()
        keep = []
        for line in lines:
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                keep.append(line)
                continue
            role = str(rec.get("role", ""))
            layer = role.split(":")[0] if ":" in role else (
                role if role in LAYERS else EPISODIC)
            if topic in str(rec.get("text", "")).lower() and \
                    (not layers or layer in layers):
                n += 1
                continue
            keep.append(line)
        if n:
            _hf.write_text("\n".join(keep) + ("\n" if keep else ""),
                           encoding="utf-8")
    except OSError:
        pass
    return n


def summarize(layer: str = SEMANTIC, limit: int = 10) -> str:
    items = search("", layers=[layer], limit=1)  # empty query -> recent
    if not items:
        try:
            from core.history import recent as _recent
            items = [{"text": r.get("text", "")}
                     for r in _recent(limit)]
        except Exception:
            return ""
    lines = [str(i.get("text", ""))[:160] for i in items[:limit] if i.get("text")]
    return "\n".join(lines)[:1500]
