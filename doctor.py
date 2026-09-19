"""
JARVIS doctor — diagnose environment without exposing secrets.

Run:  python doctor.py   (or: python -m doctor)
Checks: Python, deps, mic/audio, API config, permissions,
screen capture, optional integrations. Exit 0 = usable.
"""
from __future__ import annotations

import importlib.util
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_PY = (3, 11)
MAX_PY = (3, 13)

CORE_DEPS = ["PyQt6", "sounddevice", "numpy", "google.genai",
             "playwright", "psutil", "fastapi", "uvicorn", "cryptography"]
OPTIONAL_DEPS = ["openwakeword", "pynvml", "wmi", "pywin32"]


def _has(mod: str) -> bool:
    base = mod.split(".")[0]
    try:
        return importlib.util.find_spec(base) is not None
    except (ImportError, ValueError):
        return False


def check_python() -> tuple[bool, str]:
    v = sys.version_info[:2]
    ok = MIN_PY <= v <= (99, 99)
    note = f"{platform.python_version()} (need >={MIN_PY[0]}.{MIN_PY[1]})"
    if v < MIN_PY:
        return False, note + " — UPGRADE REQUIRED"
    if v > MAX_PY:
        return True, note + " — newer than tested, continuing"
    return ok, note


def check_api() -> tuple[bool, str]:
    # Never print the key itself — length only.
    try:
        sys.path.insert(0, str(HERE))
        from memory.config_manager import get_gemini_key
        import os
        key = os.getenv("AI_API_KEY") or (get_gemini_key() or "")
        if key and len(key) > 15:
            return True, f"API key present (len={len(key)}, hidden)"
        return False, "no API key — paste free Gemini key on first launch"
    except Exception as e:
        return False, f"config read failed: {e}"


def check_audio() -> tuple[bool, str]:
    if not _has("sounddevice"):
        return False, "sounddevice missing — voice I/O unavailable"
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        return True, f"{len(devs)} audio devices listed"
    except Exception as e:
        return False, f"audio query failed: {e}"[:120]


def check_screen() -> tuple[bool, str]:
    if _has("mss"):
        return True, "mss available"
    return False, "mss missing — vision capture degraded"


def main() -> int:
    print("JARVIS doctor —", platform.system(), platform.release())
    ok_all = True

    ok, msg = check_python()
    print(f"[{'OK' if ok else 'FAIL'}] Python: {msg}")
    ok_all &= ok

    for dep in CORE_DEPS:
        has = _has(dep)
        print(f"[{'OK' if has else '--'}] dep {dep}: {'found' if has else 'missing'}")
        if dep in ("PyQt6", "sounddevice", "numpy", "google.genai"):
            ok_all &= has

    for dep in OPTIONAL_DEPS:
        print(f"[--] optional {dep}: {'found' if _has(dep) else 'not installed'}")

    ok, msg = check_api()
    print(f"[{'OK' if ok else 'FAIL'}] API: {msg}")

    ok, msg = check_audio()
    print(f"[{'OK' if ok else '--'}] Audio: {msg}")

    ok, msg = check_screen()
    print(f"[{'OK' if ok else '--'}] Screen: {msg}")

    # New infra self-check (additive modules must import cleanly).
    for mod in ("core.event_bus", "core.permissions",
                "core.ai_router", "core.task_center",
                "plugins.roblox_assistant"):
        try:
            __import__(mod)
            print(f"[OK] import {mod}")
        except Exception as e:
            print(f"[FAIL] import {mod}: {e}")
            ok_all = False

    face = HERE / "core" / "face_model.obj"
    print(f"[{'OK' if face.exists() else '--'}] avatar face_model.obj: "
          f"{'present' if face.exists() else 'missing (core HUD fallback)'}")

    print("doctor done —", "usable" if ok_all else "issues above (degraded mode OK)")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
