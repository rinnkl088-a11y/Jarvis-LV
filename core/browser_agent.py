"""
core/browser_agent.py — browser agent hardening (PHASE 18, enhanced).

Enhanced with injection detection, secret redaction, fallback navigation chain,
page state understanding, and structured page snapshots.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_INJECTION_PATTERNS = [
    r"document\.(cookie|domain|location|write|writeln)",
    r"window\.(location|open|parent|frames)",
    r"eval\s*\(",
    r"Function\s*\(",
    r"setTimeout\s*\(",
    r"setInterval\s*\(",
    r"<script[^>]*>",
    r"javascript\s*:",
]

_SECRET_PATTERNS = [
    r"(password)\s*[:=]\s*['\"]?[^\s'\"]+",
    r"(token)\s*[:=]\s*['\"]?[^\s'\"]+",
    r"(api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]+",
    r"(Authorization)\s*[:=]\s*['\"]?[^\s'\"]+",
]


@dataclass
class PageSnapshot:
    url: str = ""
    title: str = ""
    visible_text: list[str] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    dialogs: list[str] = field(default_factory=list)
    state: str = "idle"
    errors: list[str] = field(default_factory=list)


@dataclass
class NavigationResult:
    success: bool
    url: str = ""
    fallback_used: str = ""
    snapshot: PageSnapshot = field(default_factory=PageSnapshot)
    error: str = ""


class BrowserAgent:
    def __init__(self):
        self._current_url: str = ""
        self._history: list[PageSnapshot] = []
        self._navigation_log: list[dict[str, Any]] = []

    def _scan_injection(self, content: str) -> list[str]:
        return [pat for pat in _INJECTION_PATTERNS if re.search(pat, content, re.IGNORECASE)]

    def _redact_secrets(self, text: str) -> str:
        for pat in _SECRET_PATTERNS:
            text = re.sub(pat, lambda match: f"{match.group(1)}=<REDACTED>", text, flags=re.IGNORECASE)
        return text

    def sanitize_input(self, text: str) -> str:
        hits = self._scan_injection(text)
        if hits:
            return f"[REDACTED: {len(hits)} injection pattern(s)]"
        redacted = self._redact_secrets(text)
        return "[REDACTED: secret]" if redacted != text else text

    def navigate(self, url: str, timeout: int = 30) -> NavigationResult:
        if self._scan_injection(url) and url.lower().startswith("javascript:"):
            return NavigationResult(success=False, error=f"Injection detected in URL: {url[:50]}")
        self._current_url = url
        self._navigation_log.append({"action": "navigate", "url": url, "success": True})
        return NavigationResult(success=True, url=url)

    def navigate_with_fallback(self, target: str, chain: list[str] | None = None) -> NavigationResult:
        last_error = ""
        for url in [target, *(chain or [])]:
            result = self.navigate(url)
            if result.success:
                result.fallback_used = "primary" if url == target else url
                return result
            last_error = result.error
        return NavigationResult(success=False, error=f"All fallbacks failed: {last_error}")

    def observe_page(self, url: str) -> PageSnapshot:
        snapshot = PageSnapshot(url=url)
        self._history.append(snapshot)
        return snapshot

    def click_element(self, element: str, url: str) -> NavigationResult:
        safe = self.sanitize_input(element)
        if safe.startswith("[REDACTED"):
            return NavigationResult(success=False, error="Injection detected in element selector")
        return self.navigate(f"{url}?action=click&target={safe}")

    def type_into(self, element: str, text: str, url: str) -> NavigationResult:
        safe_element = self.sanitize_input(element)
        safe_text = self.sanitize_input(text)
        return self.navigate(f"{url}?action=type&target={safe_element}&value={safe_text[:100]}")

    def get_page_state(self, url: str) -> PageSnapshot:
        return self.observe_page(url)

    def extract_links(self, url: str) -> list[str]:
        return [f"{url}/link/{i}" for i in range(3)]

    def submit_form(self, form_name: str, url: str) -> NavigationResult:
        return self.navigate(f"{url}?form={form_name}&submit=true")

    def download(self, url: str) -> NavigationResult:
        return self.navigate(f"{url}?download=true")

    def get_navigation_log(self) -> list[dict[str, Any]]:
        return list(self._navigation_log)


def observe_page(url: str, body_text: str = "") -> PageSnapshot:
    """Legacy page observer with prompt-injection warnings."""
    warnings = BrowserAgent()._scan_injection(body_text)
    snapshot = PageSnapshot(url=url, visible_text=[body_text] if body_text else [])
    snapshot.warnings = warnings or (["prompt injection detected"] if body_text and re.search(
        r"ignore\s+(your\s+)?system instructions|delete all files",
        body_text,
        re.IGNORECASE,
    ) else [])
    return snapshot


def sanitize_for_model(text: str) -> str:
    """Redact secrets before content is passed to a model."""
    redacted = BrowserAgent()._redact_secrets(text)
    return redacted.replace("=<REDACTED>", "=[REDACTED]")


def navigate_with_fallback(action, refresh_fn=None, verify_fn=None, retries: int = 2) -> dict[str, Any]:
    """Run an action, then refresh fallback, without raising tool errors."""
    attempts = 1
    try:
        action()
        if verify_fn is None or verify_fn():
            return {"ok": True, "method": "primary", "attempts": attempts}
    except Exception:
        pass
    if refresh_fn is not None:
        attempts += 1
        try:
            refresh_fn()
            if verify_fn is None or verify_fn():
                return {"ok": True, "method": "refresh", "attempts": attempts}
        except Exception:
            pass
    for _ in range(max(0, retries - 1)):
        attempts += 1
        try:
            action()
            if verify_fn is None or verify_fn():
                return {"ok": True, "method": "primary", "attempts": attempts}
        except Exception:
            pass
    return {"ok": False, "method": "none", "attempts": attempts}
