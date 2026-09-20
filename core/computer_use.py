"""
core/computer_use.py — safe computer-use ladder (PHASE 4, additive).

Priority: native API > app API > browser DOM > OCR > visual > raw input.
Every action verifies: re-observe after acting, compare expectation,
report VERIFIED or NOT-VERIFIED — never claim success blindly.
Existing actions/computer_control.py untouched; this orchestrates with
verification on top.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class UseResult:
    ok: bool
    verified: bool = False
    detail: str = ""
    method: str = ""


def list_windows() -> list[str]:
    try:
        import pygetwindow as gw
        return [t.strip() for t in gw.getAllTitles() if t and t.strip()][:30]
    except Exception as e:
        return [f"<window list unavailable: {e}>"[:120]]


def _reobserve(check_fn, timeout_s: float = 5.0,
               interval_s: float = 0.5) -> bool:
    end = time.monotonic() + max(1.0, timeout_s)
    while time.monotonic() < end:
        try:
            if check_fn():
                return True
        except Exception:
            pass
        time.sleep(interval_s)
    return False


def act_and_verify(description: str, act_fn, check_fn,
                   method: str = "native-api",
                   timeout_s: float = 5.0) -> UseResult:
    """Run act_fn(), then poll check_fn() until expectation holds."""
    try:
        act_fn()
    except Exception as e:
        return UseResult(ok=False, verified=False,
                         detail=f"{description} failed to execute: {e}"[:250],
                         method=method)
    ok = _reobserve(check_fn, timeout_s)
    return UseResult(ok=ok, verified=ok, method=method,
                     detail=(f"{description}: VERIFIED via {method}."
                             if ok else f"{description}: NOT VERIFIED — "
                             f"expected state did not appear.").strip())


def focus_window_verified(title_fragment: str, timeout_s: float = 5.0,
                          focus_fn=None) -> UseResult:
    frag = (title_fragment or "").lower()
    if not frag:
        return UseResult(ok=False, detail="Empty window title.")

    def _act():
        if callable(focus_fn):
            focus_fn(title_fragment)
            return
        try:
            import pygetwindow as gw
            for w in gw.getAllWindows():
                if frag in (w.title or "").lower():
                    w.activate()
                    return
        except Exception as e:
            raise RuntimeError(e)
        raise RuntimeError(f"No window matches '{title_fragment}'.")

    def _check() -> bool:
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            return bool(active and frag in (active.title or "").lower())
        except Exception:
            return False

    return act_and_verify(f"Focus '{title_fragment}'", _act, _check,
                          method="native-api", timeout_s=timeout_s)
