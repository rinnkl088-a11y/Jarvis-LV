"""
core/ai_router.py — provider-agnostic AI layer (PHASE 1, additive).

main.py keeps using google-genai directly. New code can route through
ModelRouter: primary -> fallback -> graceful error, with timeouts/retries.
API keys are never logged (length only).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass


def _redact(s: str) -> str:
    if not s:
        return "<empty>"
    return f"<key len={len(s)}>"


@dataclass
class ProviderConfig:
    provider: str = "gemini"
    base_url: str = ""
    api_key: str = ""
    model: str = "models/gemini-3.1-flash-live-preview"
    fallback_model: str = ""
    vision_model: str = ""
    timeout_s: float = 30.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        try:
            timeout = float(os.getenv("AI_TIMEOUT_S", "30"))
        except ValueError:
            timeout = 30.0
        try:
            retries = int(os.getenv("AI_MAX_RETRIES", "2"))
        except ValueError:
            retries = 2
        cfg = cls(
            provider=os.getenv("AI_PROVIDER", "gemini"),
            base_url=os.getenv("AI_BASE_URL", ""),
            api_key=os.getenv("AI_API_KEY", ""),
            model=os.getenv("AI_MODEL", "models/gemini-3.1-flash-live-preview"),
            fallback_model=os.getenv("AI_FALLBACK_MODEL", ""),
            vision_model=os.getenv("AI_VISION_MODEL", ""),
            timeout_s=timeout,
            max_retries=max(0, min(retries, 5)),
        )
        if not cfg.api_key:
            try:
                from memory.config_manager import get_gemini_key
                cfg.api_key = get_gemini_key() or ""
            except Exception:
                pass
        return cfg

    def safe_summary(self) -> str:
        return (
            f"provider={self.provider} model={self.model} "
            f"fallback={self.fallback_model or '-'} key={_redact(self.api_key)}"
        )


@dataclass
class RouterResult:
    ok: bool
    model: str = ""
    output: str = ""
    error: str = ""
    attempts: int = 0
    elapsed_s: float = 0.0


class RetryManager:
    def __init__(self, max_retries: int = 2, base_delay_s: float = 0.8):
        self.max_retries = max(0, min(max_retries, 5))
        self.base_delay_s = base_delay_s

    def delay_for(self, attempt: int) -> float:
        return self.base_delay_s * (2 ** max(0, attempt))


class ContextManager:
    def __init__(self, max_chars: int = 24_000):
        self.max_chars = max_chars
        self._chunks: list[str] = []

    def add(self, text: str) -> None:
        if text:
            self._chunks.append(text[-4000:])
            self._trim()

    def _trim(self) -> None:
        total = sum(len(c) for c in self._chunks)
        while self._chunks and total > self.max_chars:
            dropped = self._chunks.pop(0)
            total -= len(dropped)

    def build(self) -> str:
        return "\n".join(self._chunks)[-self.max_chars:]

    def clear(self) -> None:
        self._chunks.clear()


class ModelRouter:
    def __init__(self, config: ProviderConfig | None = None):
        self.config = config or ProviderConfig.from_env()
        self.retry = RetryManager(self.config.max_retries)
        self.context = ContextManager()

    def route(self, prompt: str, call_fn=None) -> RouterResult:
        t0 = time.monotonic()
        models = [self.config.model]
        if self.config.fallback_model and self.config.fallback_model != self.config.model:
            models.append(self.config.fallback_model)
        last_err = "no model configured"
        attempts = 0
        for model in models:
            if not model:
                continue
            for attempt in range(self.retry.max_retries + 1):
                attempts += 1
                try:
                    if call_fn is None:
                        return RouterResult(
                            ok=False, model=model, error=(
                                "AI OFFLINE — no call function wired. "
                                "Local tools and UI remain available."
                            ), attempts=attempts,
                            elapsed_s=time.monotonic() - t0,
                        )
                    out = call_fn(model, prompt, self.config.timeout_s)
                    self.context.add(prompt[-2000:])
                    self.context.add(str(out)[-2000:])
                    return RouterResult(ok=True, model=model, output=str(out),
                                        attempts=attempts,
                                        elapsed_s=time.monotonic() - t0)
                except Exception as e:
                    last_err = f"{type(e).__name__}: {e}"[:300]
                    if attempt < self.retry.max_retries:
                        time.sleep(self.retry.delay_for(attempt))
        return RouterResult(ok=False, model="", error=last_err[:300],
                            attempts=attempts,
                            elapsed_s=time.monotonic() - t0)
