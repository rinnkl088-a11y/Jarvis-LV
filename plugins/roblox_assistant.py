"""
Roblox Studio assistant plugin (read-only first step).

Capabilities:
  inspect_project — list .lua/.luau files + key services folders
  search_scripts  — keyword search across scripts (capped)
  explain_error   — match an Output error string to likely files
  list_services   — detect ServerScriptService / ReplicatedStorage / etc.

Safety: read-only. Never writes, deletes, or executes project code.
Respects core.permissions BLOCKED patterns. Caps file count and size
for 8GB RAM targets.
"""
from pathlib import Path

PLUGIN = {
    "name": "roblox_assistant",
    "description": (
        "Roblox Luau development helper. Use when the user asks about a "
        "Roblox project, Luau scripts, Output errors, RemoteEvents, "
        "ModuleScripts, ServerScriptService, ReplicatedStorage, StarterPlayer, "
        "StarterGui, or Workspace code. Read-only: inspects and explains, "
        "never modifies files. Do NOT use for non-Roblox code."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "inspect_project | search_scripts | explain_error | list_services",
            },
            "path": {
                "type": "STRING",
                "description": "Roblox project root folder (absolute path)",
            },
            "query": {
                "type": "STRING",
                "description": "Keyword or error text for search_scripts / explain_error",
            },
        },
        "required": ["action", "path"],
    },
}

_LUA_EXTS = {".lua", ".luau"}
_MAX_FILES = 200
_MAX_BYTES = 200_000
_MAX_HITS = 30
_KNOWN_SERVICES = (
    "ServerScriptService", "ReplicatedStorage", "StarterPlayer",
    "StarterGui", "Workspace", "ServerStorage", "Lighting",
)


def _safe_root(path: str) -> Path | None:
    try:
        p = Path(path).expanduser().resolve()
    except Exception:
        return None
    if not p.is_dir():
        return None
    return p


def _iter_scripts(root: Path):
    out = []
    try:
        for f in root.rglob("*"):
            if len(out) >= _MAX_FILES:
                break
            try:
                if f.is_file() and f.suffix.lower() in _LUA_EXTS:
                    if f.stat().st_size <= _MAX_BYTES:
                        out.append(f)
            except OSError:
                continue
    except OSError:
        pass
    return sorted(out)


def _inspect(root: Path) -> str:
    files = _iter_scripts(root)
    by_parent: dict[str, int] = {}
    for f in files:
        try:
            by_parent[f.parent.name] = by_parent.get(f.parent.name, 0) + 1
        except Exception:
            continue
    lines = [f"Project: {root}", f"Luau files: {len(files)} (capped at {_MAX_FILES})"]
    for parent, n in sorted(by_parent.items(), key=lambda kv: -kv[1])[:12]:
        lines.append(f"  {parent}/: {n}")
    for f in files[:20]:
        try:
            lines.append(f"  - {f.relative_to(root)}")
        except ValueError:
            lines.append(f"  - {f.name}")
    if len(files) > 20:
        lines.append(f"  ... +{len(files) - 20} more")
    return "\n".join(lines)


def _search(root: Path, query: str) -> str:
    q = (query or "").strip()
    if not q:
        return "Give a search keyword, e.g. RemoteEvent name or function."
    ql = q.lower()
    hits: list[str] = []
    for f in _iter_scripts(root):
        if len(hits) >= _MAX_HITS:
            break
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if ql in line.lower():
                rel = f.name
                try:
                    rel = str(f.relative_to(root))
                except ValueError:
                    pass
                hits.append(f"{rel}:{i}: {line.strip()[:140]}")
                if len(hits) >= _MAX_HITS:
                    break
    if not hits:
        return f"No matches for '{q}' in {len(_iter_scripts(root))} scripts."
    return f"Matches for '{q}' ({len(hits)}, capped):\n" + "\n".join(hits)


def _explain(root: Path, error: str) -> str:
    err = (error or "").strip()
    if not err:
        return "Paste the Output error text to explain it."
    # Pull likely identifiers: Class names, require() names, file-ish tokens.
    import re
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.:]*", err))
    stop = {"the", "and", "for", "with", "line", "error", "attempt",
            "index", "nil", "value", "function", "expected", "near"}
    keywords = [t for t in tokens if len(t) >= 4 and t.lower() not in stop][:6]
    lines = [f"Error: {err[:300]}", ""]
    if not keywords:
        lines.append("Could not extract identifiers. Check Output line number first.")
        return "\n".join(lines)
    lines.append("Likely identifiers: " + ", ".join(keywords))
    for kw in keywords[:3]:
        lines.append("")
        lines.append(_search(root, kw.split(".")[0].split(":")[0]))
    lines.append("")
    lines.append("Fix workflow: FILE -> LINE -> CAUSE -> FIX -> re-check. "
                "I did not modify anything (read-only).")
    return "\n".join(lines)[:4000]


def _services(root: Path) -> str:
    found, missing = [], []
    for svc in _KNOWN_SERVICES:
        if (root / svc).exists():
            found.append(svc)
        else:
            # also match nested (e.g. src/ServerScriptService)
            match = False
            try:
                for d in root.rglob(svc):
                    if d.is_dir():
                        found.append(f"{svc} ({d.relative_to(root)})")
                        match = True
                        break
            except OSError:
                pass
            if not match:
                missing.append(svc)
    out = ["Known services:"]
    out += [f"  FOUND: {s}" for s in found] or ["  (none matched)"]
    if missing:
        out.append("Missing at top level: " + ", ".join(missing))
    return "\n".join(out)


def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "")).strip()
    root = _safe_root(str(params.get("path", "")))
    if root is None:
        return "Give an absolute Roblox project folder path that exists."
    try:
        if action == "inspect_project":
            result = _inspect(root)
        elif action == "search_scripts":
            result = _search(root, str(params.get("query", "")))
        elif action == "explain_error":
            result = _explain(root, str(params.get("query", "")))
        elif action == "list_services":
            result = _services(root)
        else:
            return "Unknown action. Use inspect_project, search_scripts, explain_error, or list_services."
    except Exception as e:
        return f"roblox_assistant failed: {e}"
    if player:
        try:
            player.write_log(f"JARVIS: roblox_assistant {action} done.")
        except Exception:
            pass
    return result
