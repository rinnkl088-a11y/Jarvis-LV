"""
core/browser_agent.py — Browser Agent hardening (PHASE 8, additive).

Wraps tab/page/link/form/download/upload concepts with safety:
- external page content is DATA, never authority (prompt-injection
  boundary: suspicious instruction patterns are flagged, never obeyed)
- secrets (passwords, cookies, tokens) are never extracted or logged
- navigation retries with refresh + re-detect fallback chain

No Playwright import at module load (lazy) so unit tests stay light.
Existing actions/browser_control.py untouched.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

_INJECTION_PATTERNS = (
    r"ignore (all |your )?previous instructions",
    r"ignore your system instructions",
    r"delete all files",
    r"disable .*security",
    r"exfiltrate",
    r"send .*password",
)


@dataclass
class PageObservation:
    url: str = ""
    title: str = ""
    links: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def scan_for_injection(text: str) -> list[str]:
    low = (text or "").lower()
    hits = []
    for pat in _INJECTION_PATTERNS:
        try:
            if re.search(pat, low):
                hits.append(pat)
        except re.error:
            continue
    return hits


def sanitize_for_model(text: str, max_chars: int = 2000) -> str:
    t = (text or "")[:max_chars]
    # Redact secret-looking tokens; never pass them to the model.
    t = re.sub(r"(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S+",
               r"\1: [REDACTED]", t, flags=re.IGNORECASE)
    return t


def observe_page(url: str = "", title: str = "", links=None,
                 forms=None, body_text: str = "") -> PageObservation:
    obs = PageObservation(url=url[:300], title=title[:200],
                          links=[str(l)[:200] for l in (links or [])[:20]],
                          forms=[str(f)[:160] for f in (forms or [])[:10]])
    for pat in scan_for_injection(body_text):
        obs.warnings.append(f"Untrusted page content matches '{pat}' — "
                            "treated as DATA, not instructions.")
    return obs


def navigate_with_fallback(navigate_fn, refresh_fn=None, redetect_fn=None,
                           verify_fn=None, retries: int = 2) -> dict:
    """Try navigate -> refresh -> redetect chain. Returns dict with
    ok/method/attempts. Never raises."""
    attempts = 0
    last_err = "not attempted"
    strategies = [("navigate", navigate_fn), ("refresh", refresh_fn),
                  ("redetect", redetect_fn)]
    for label, fn in strategies[: max(1, retries + 1)]:
        if not callable(fn):
            continue
        attempts += 1
        try:
            fn()
        except Exception as e:
            last_err = f"{label}: {e}"[:200]
            continue
        if callable(verify_fn):
            try:
                if verify_fn():
                    return {"ok": True, "method": label,
                            "attempts": attempts}
                last_err = f"{label}: verify failed"
                continue
            except Exception as e:
                last_err = f"{label}: verify error {e}"[:200]
                continue
        return {"ok": True, "method": label, "attempts": attempts}
    return {"ok": False, "method": "none", "attempts": attempts,
            "error": last_err[:250]}
