"""
core/vision.py — Vision Engine (PHASE 4, additive).

Separates CAPTURE from ANALYSIS from ACTION. Existing
actions/screen_processor.py is untouched; this wraps it with:

- sampling cache (TTL) + change hash (no continuous full-res stream)
- downscale cap (token/compute guard for 8GB targets)
- structured Observation: screen, applications, visible_text,
  ui_elements, warnings, observations
- injectable analyze_fn(image_bytes, kind) for model or mock

Kinds: SCREEN | WEBCAM | SCREENSHOT | IMAGE_FILE
"""
from __future__ import annotations

import hashlib
import io
import threading
import time
from dataclasses import dataclass, field

SCREEN = "SCREEN"
WEBCAM = "WEBCAM"
SCREENSHOT = "SCREENSHOT"
IMAGE_FILE = "IMAGE_FILE"

_MAX_DIM = 1280
_CACHE_TTL_S = 2.0


@dataclass
class Observation:
    kind: str = SCREEN
    screen: str = ""
    applications: list[str] = field(default_factory=list)
    visible_text: list[str] = field(default_factory=list)
    ui_elements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    captured_at: float = field(default_factory=time.monotonic)
    changed_since_last: bool = True


_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, bytes, str]] = {}  # kind -> (ts, raw, hash)


def _downscale(raw: bytes) -> bytes:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        scale = min(1.0, _MAX_DIM / max(1, max(w, h)))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except Exception:
        return raw


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]


def capture(kind: str = SCREEN, region: dict | None = None,
            force: bool = False) -> tuple[bytes, bool]:
    """Returns (jpeg_bytes, changed). Cached TTL unless force."""
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(kind)
        if hit and not force and (now - hit[0]) < _CACHE_TTL_S:
            return hit[1], False
    raw = _capture_uncached(kind, region)
    small = _downscale(raw)
    digest = _hash(small)
    with _cache_lock:
        prev = _cache.get(kind)
        changed = prev is None or prev[2] != digest
        _cache[kind] = (now, small, digest)
    return small, changed


def _capture_uncached(kind: str, region: dict | None) -> bytes:
    if kind == IMAGE_FILE and isinstance(region, dict) and region.get("path"):
        try:
            with open(region["path"], "rb") as f:
                return f.read(5_000_000)
        except OSError as e:
            raise RuntimeError(f"Cannot read image file: {e}")
    if kind in (SCREEN, SCREENSHOT):
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                mon = sct.monitors[1 if len(sct.monitors) > 1 else 0]
                if isinstance(region, dict) and region:
                    mon = {**mon, **{k: region[k] for k in
                                     ("left", "top", "width", "height")
                                     if k in region}}
                shot = sct.grab(mon)
                return mss.tools.to_png(shot.rgb, shot.size)
        except Exception as e:
            raise RuntimeError(f"Screen capture unavailable: {e}"[:200])
    if kind == WEBCAM:
        try:
            from actions.screen_processor import _capture_camera
            data = _capture_camera()
            if isinstance(data, tuple):
                return data[0]
            return data
        except Exception as e:
            raise RuntimeError(f"Webcam unavailable: {e}"[:200])
    raise ValueError(f"Unknown vision kind '{kind}'.")


def clear_cache(kind: str | None = None) -> None:
    with _cache_lock:
        if kind:
            _cache.pop(kind, None)
        else:
            _cache.clear()


def _local_context() -> dict:
    apps: list[str] = []
    try:
        import pygetwindow as gw
        for t in gw.getAllTitles():
            if t and t.strip():
                apps.append(t.strip()[:80])
                if len(apps) >= 12:
                    break
    except Exception:
        pass
    return {"applications": apps}


def analyze(image: bytes, kind: str = SCREEN,
            analyze_fn=None) -> Observation:
    """Build structured Observation. analyze_fn(image, kind) may return a
    dict with any Observation fields (model or mock). Default: local-only
    context, honestly marked — never fabricated UI elements."""
    obs = Observation(kind=kind)
    obs.screen = (f"{kind} frame, {len(image)} bytes, "
                  f"downscaled to max {_MAX_DIM}px.")
    ctx = _local_context()
    obs.applications = ctx["applications"]
    if callable(analyze_fn):
        try:
            out = analyze_fn(image, kind) or {}
            for key in ("screen", "applications", "visible_text",
                        "ui_elements", "warnings", "observations"):
                val = out.get(key)
                if isinstance(val, str) and key == "screen" and val:
                    obs.screen = val[:500]
                elif isinstance(val, list) and key != "screen":
                    obs.__dict__[key] = [str(v)[:160] for v in val[:20]]
        except Exception as e:
            obs.warnings.append(f"analyzer failed: {e}"[:160])
    else:
        obs.observations.append("Local-only frame: no vision model wired. "
                                "Use analyze_fn for model judgments.")
    return obs


def observe(kind: str = SCREEN, region: dict | None = None,
            analyze_fn=None, force: bool = False) -> Observation:
    img, changed = capture(kind, region, force)
    obs = analyze(img, kind, analyze_fn)
    obs.changed_since_last = changed
    return obs
