"""
core/gaming.py — Gaming Agent (PHASE 10, additive, legitimate use only).

Supports: game detection (Steam/Epic manifests, read-only), launch
(via injectable launcher — production wires open_app/tool registry),
performance ticks (system_agent snapshot), session summary.

Explicitly OUT of scope and refused: anti-cheat bypass, stealth
automation, credential theft, multiplayer cheating, security evasion.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

REFUSED = ("anti-cheat", "anticheat", "aimbot", "wallhack", "bypass",
           "stealth automation")


@dataclass
class GameSession:
    title: str
    started_at: float = field(default_factory=time.monotonic)
    perf_ticks: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_at

    def cap(self, n: int = 20) -> None:
        self.perf_ticks = self.perf_ticks[-n:]


def check_allowed(request: str) -> str:
    low = (request or "").lower()
    for pat in REFUSED:
        if pat in low:
            return (f"Refused: '{pat}' is out of scope. I support launching, "
                    f"configuring, performance monitoring, and accessibility — "
                    f"never cheat bypass or evasion.")
    return ""


def _steam_dirs() -> list[Path]:
    cands = [Path(p) for p in (
        r"C:\Program Files (x86)\Steam",
        r"C:\Program Files\Steam",
        Path.home() / ".steam" / "steam",
        Path.home() / ".local" / "share" / "Steam",
    )]
    return [p for p in cands if p.is_dir()]


def detect_games(max_results: int = 30) -> list[dict]:
    """Read-only scan of Steam appmanifest + Epic .item files."""
    out: list[dict] = []
    for steam in _steam_dirs():
        for lib in [steam] + [Path(p) for p in
                              _library_folders(steam)]:
            apps = lib / "steamapps"
            if not apps.is_dir():
                continue
            for mf in sorted(apps.glob("appmanifest_*.acf"))[:max_results]:
                try:
                    text = mf.read_text(encoding="utf-8", errors="ignore")
                    name = _acf_value(text, "name") or mf.stem
                    out.append({"title": name[:80], "source": "steam",
                                "manifest": str(mf)})
                    if len(out) >= max_results:
                        return out
                except OSError:
                    continue
    epic = Path(r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests")
    if epic.is_dir():
        import json
        for item in sorted(epic.glob("*.item"))[:max_results]:
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                out.append({"title": str(data.get("DisplayName",
                                                  item.stem))[:80],
                            "source": "epic", "manifest": str(item)})
                if len(out) >= max_results:
                    break
            except (OSError, ValueError):
                continue
    return out


def _library_folders(steam: Path) -> list[str]:
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    import re
    return re.findall(r'"path"\s+"([^"]+)"', text)[:8]


def _acf_value(text: str, key: str) -> str:
    import re
    m = re.search(rf'"{re.escape(key)}"\s+"([^"]+)"', text)
    return m.group(1) if m else ""


def launch(title: str, launcher_fn=None,
           known_games: list[dict] | None = None) -> dict:
    refused = check_allowed(title)
    if refused:
        return {"ok": False, "error": refused}
    games = known_games if known_games is not None else detect_games()
    match = next((g for g in games
                  if title.lower() in g["title"].lower()), None)
    if match is None:
        return {"ok": False,
                "error": f"Game '{title}' not found in Steam/Epic libraries. "
                         f"Launch it manually once, or check the title."}
    if not callable(launcher_fn):
        return {"ok": True, "dry_run": True,
                "detail": f"Found '{match['title']}' ({match['source']}). "
                          f"No launcher wired — wire open_app to launch."}
    try:
        detail = launcher_fn(match)
    except Exception as e:
        return {"ok": False, "error": f"Launch failed: {e}"[:200]}
    return {"ok": True, "detail": str(detail)[:300],
            "session": GameSession(title=match["title"])}


def perf_tick(session: GameSession | None = None) -> dict:
    try:
        from core.system_agent import snapshot
        snap = snapshot(top_n=5)
        tick = {"at": time.monotonic(),
                "cpu": snap.cpu_pct, "ram": snap.ram, "gpu": snap.gpu,
                "thermal": snap.thermal}
    except Exception as e:
        tick = {"at": time.monotonic(), "error": str(e)[:150]}
    if session is not None:
        session.perf_ticks = (session.perf_ticks + [tick])[-20:]
    return tick
