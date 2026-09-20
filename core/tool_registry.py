"""
core/tool_registry.py — unified Tool Registry (PHASE 2, additive).

Wraps ActionRegistry + PluginRegistry + inline declarations into one
standardized view: name, description, parameters, permission, risk,
timeout, verify, rollback, source. No loader rewrites; old TOOL dicts
without new keys load with safe defaults.

Timeout IS enforced here via a worker thread (concurrent.futures).
Blocked tools refuse without running. Destructive tools report their
gate but do not auto-confirm — the caller (confirm.py UI banner) owns
confirmation; the registry never forges it.
"""
from __future__ import annotations

import concurrent.futures
import threading
from dataclasses import dataclass

from core.tool_schema import (ToolSpec, risk_for_permission,
                              DEFAULT_TIMEOUT_S, BLOCKED, DESTRUCTIVE)
from core.tool_metadata import lookup as _overlay_lookup

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="toolreg")
_EXECUTOR_LOCK = threading.Lock()


@dataclass
class ToolResult:
    ok: bool
    output: str = ""
    error: str = ""
    timed_out: bool = False
    blocked: bool = False


class ToolRegistry:
    def __init__(self, action_registry=None, plugin_registry=None,
                 inline_decls: list[dict] | None = None):
        self._actions = action_registry
        self._plugins = plugin_registry
        self._inline = {d.get("name"): d for d in (inline_decls or ())
                        if isinstance(d, dict) and d.get("name")}
        self._specs: dict[str, ToolSpec] = {}
        self._build_specs()

    # -- spec building ----------------------------------------------------
    def _perm_for(self, name: str, tool_dict: dict | None) -> str:
        if isinstance(tool_dict, dict) and tool_dict.get("permission"):
            return str(tool_dict["permission"])
        ov = _overlay_lookup(name)
        if ov.get("permission"):
            return str(ov["permission"])
        try:
            from core.permissions import classify as _classify
            legacy = _classify(name)
            return {"SAFE": "SAFE", "SENSITIVE": "SENSITIVE",
                    "DESTRUCTIVE": "DESTRUCTIVE",
                    "BLOCKED": "BLOCKED"}.get(legacy, "SENSITIVE")
        except Exception:
            return "SENSITIVE"

    def _build_specs(self) -> None:
        seen: dict[str, ToolSpec] = {}

        def _add(name: str, desc: str, params: dict, source: str,
                 tool_dict: dict | None = None):
            if not name or name in seen:
                return
            ov = _overlay_lookup(name)
            perm = self._perm_for(name, tool_dict)
            try:
                timeout = float((tool_dict or {}).get(
                    "timeout_s", ov.get("timeout_s", DEFAULT_TIMEOUT_S)))
            except (TypeError, ValueError):
                timeout = DEFAULT_TIMEOUT_S
            spec = ToolSpec(
                name=name, description=desc or "",
                parameters=params if isinstance(params, dict) else
                {"type": "OBJECT", "properties": {}},
                permission=perm, risk=risk_for_permission(perm),
                timeout_s=timeout,
                verify=str((tool_dict or {}).get("verify",
                                                 ov.get("verify", ""))),
                rollback=str((tool_dict or {}).get("rollback",
                                                   ov.get("rollback", ""))),
                source=source,
            ).validated()
            seen[name] = spec

        if self._actions is not None:
            try:
                acts = getattr(self._actions, "_actions", {}) or {}
            except Exception:
                acts = {}
            for rec in acts.values():
                _add(getattr(rec, "name", ""), getattr(rec, "description", ""),
                     getattr(rec, "parameters", {}), "action")
        if self._plugins is not None:
            try:
                plugs = getattr(self._plugins, "_plugins", {}) or {}
            except Exception:
                plugs = {}
            for rec in plugs.values():
                _add(getattr(rec, "name", ""), getattr(rec, "description", ""),
                     getattr(rec, "parameters", {}), "plugin")
        for name, d in self._inline.items():
            _add(name, d.get("description", ""), d.get("parameters", {}),
                 "inline", d)
        self._specs = seen

    # -- queries ----------------------------------------------------------
    def specs(self) -> dict[str, ToolSpec]:
        return dict(self._specs)

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def declarations(self) -> list[dict]:
        return [{"name": s.name, "description": s.description,
                 "parameters": s.parameters} for s in self._specs.values()]

    # -- execution --------------------------------------------------------
    def execute(self, name: str, parameters: dict | None = None,
                ctx: dict | None = None) -> ToolResult:
        spec = self._specs.get(name)
        if spec is None:
            return ToolResult(ok=False, error=f"Unknown tool '{name}'.")
        if spec.permission == BLOCKED:
            try:
                from core.permissions import refuse_message
                msg = refuse_message(name)
            except Exception:
                msg = f"Tool '{name}' is blocked by policy."
            return ToolResult(ok=False, error=msg, blocked=True)
        timeout = spec.timeout_s
        fut = _EXECUTOR.submit(self._dispatch, name, parameters or {},
                               ctx or {}, spec.source)
        try:
            out = fut.result(timeout=timeout)
            return ToolResult(ok=True, output=str(out))
        except concurrent.futures.TimeoutError:
            fut.cancel()
            return ToolResult(ok=False, timed_out=True,
                              error=f"Tool '{name}' timed out after "
                                    f"{timeout:.0f}s.")
        except Exception as e:
            return ToolResult(ok=False,
                              error=f"Tool '{name}' failed: {e}"[:300])

    def _dispatch(self, name: str, parameters: dict, ctx: dict,
                  source: str) -> str:
        if source == "action" and self._actions is not None:
            return self._actions.run(name, parameters, ctx)
        if source == "plugin" and self._plugins is not None:
            return self._plugins.run(name, parameters,
                                     player=ctx.get("player"),
                                     session_memory=ctx.get("session_memory"))
        if source == "inline":
            return f"Inline tool '{name}' is dispatched by main.py."
        # fallback: try registries in order
        if self._actions is not None and self._actions.has(name):
            return self._actions.run(name, parameters, ctx)
        if self._plugins is not None and self._plugins.has(name):
            return self._plugins.run(name, parameters,
                                     player=ctx.get("player"),
                                     session_memory=ctx.get("session_memory"))
        raise KeyError(f"No handler for '{name}'.")


def build_default_registry(actions_dir=None, plugins_dir=None,
                           inline_decls: list[dict] | None = None,
                           logger=None):
    """Convenience: discover + wrap. Used by tests and future agent loop."""
    from pathlib import Path
    from core.action_loader import discover_actions
    from core.plugin_loader import discover_plugins
    log = logger or (lambda m: None)
    base = Path(__file__).resolve().parent.parent
    ar = discover_actions(actions_dir or (base / "actions"),
                          reserved_names=set(), logger=log)
    pr = discover_plugins(plugins_dir or (base / "plugins"),
                          core_tool_names=ar.names(), logger=log)
    return ToolRegistry(ar, pr, inline_decls), ar, pr
