"""
core/coding_agent.py — Coding Agent (PHASE 7, additive).

Loop: ANALYZE -> PLAN -> MODIFY(propose only) -> TEST -> OBSERVE
  -> REPAIR -> TEST AGAIN. Never claims code works without running
validation when execution is available. Never auto-commits, never
deletes, never runs tests outside the given project root. Destructive
commands (rm -rf, format, push --force) are BLOCKED.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

BLOCKED_TOKENS = ("rm -rf", "rm -r /", ":(){", "format c:",
                  "push --force", "del /f /s /q c:\\")


@dataclass
class CodeReport:
    structure: list[str] = field(default_factory=list)
    test_command: str = ""
    passed: bool = False
    output: str = ""
    elapsed_s: float = 0.0


def is_blocked_command(cmd: str) -> bool:
    low = (cmd or "").lower()
    return any(t in low for t in BLOCKED_TOKENS)


def analyze_project(root: str | Path, max_files: int = 60) -> list[str]:
    p = Path(root)
    if not p.is_dir():
        return [f"Not a directory: {root}"]
    out = []
    for f in sorted(p.rglob("*.py")):
        if len(out) >= max_files:
            out.append(f"... +more (capped at {max_files})")
            break
        try:
            rel = f.relative_to(p)
        except ValueError:
            rel = f.name
        out.append(str(rel))
    tests = [s for s in out if "test" in s.lower()]
    out.append(f"__summary__: {len(out)} python files, {len(tests)} test files")
    return out[: max_files + 1]


def run_tests(root: str | Path, command: str = "python -m pytest -q",
              timeout_s: float = 120.0) -> CodeReport:
    rep = CodeReport(test_command=command)
    if is_blocked_command(command):
        rep.output = "BLOCKED command refused."
        return rep
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            command, shell=True, cwd=str(root), capture_output=True,
            text=True, timeout=timeout_s)
        rep.passed = (proc.returncode == 0)
        tail = (proc.stdout or "")[-2000:] + (proc.stderr or "")[-1000:]
        rep.output = tail[-3000:] or "(no output)"
    except subprocess.TimeoutExpired:
        rep.output = f"TIMEOUT after {timeout_s:.0f}s."
    except Exception as e:
        rep.output = f"Failed to run: {e}"[:300]
    rep.elapsed_s = time.monotonic() - t0
    return rep


def explain_diff(before: str, after: str) -> str:
    import difflib
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(),
                                "before", "after", lineterm="")
    lines = list(diff)[:60]
    return "\n".join(lines) if lines else "(no changes)"
