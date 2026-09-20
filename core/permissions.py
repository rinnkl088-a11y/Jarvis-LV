"""
core/permissions.py — SAFE / SENSITIVE / DESTRUCTIVE / BLOCKED gate (PHASE 1).

Classifies only; enforcement lives in the caller (confirm.py banner for
DESTRUCTIVE, refuse for BLOCKED, undo stack for reversible SENSITIVE).
Model output is UNTRUSTED INPUT — never the security boundary.
"""
from __future__ import annotations

SAFE = "SAFE"
SENSITIVE = "SENSITIVE"
DESTRUCTIVE = "DESTRUCTIVE"
BLOCKED = "BLOCKED"

_DESTRUCTIVE_TOOLS = {
    "shutdown_jarvis",
    "restart",
    "shutdown",
    "toggle_wifi",
    "delete_file",
    "delete_folder",
    "send_message",
    "run_destructive_command",
}

_DESTRUCTIVE_PARAMS = {
    "computer_settings": {"restart", "shutdown"},
    "file_controller": {"delete", "move_to_trash"},
}

_BLOCKED_PATTERNS = (
    "password_store",
    "credential_manager",
    "disable_defender",
    "disable_security",
    "exfiltrate",
    "api_keys.json",
)


def classify(tool_name: str, parameters: dict | None = None) -> str:
    name = (tool_name or "").strip()
    params = parameters or {}
    blob = f"{name} {params}".lower()
    for pat in _BLOCKED_PATTERNS:
        if pat in blob:
            return BLOCKED
    if name in _DESTRUCTIVE_TOOLS:
        return DESTRUCTIVE
    for tool, triggers in _DESTRUCTIVE_PARAMS.items():
        if name == tool:
            try:
                vals = " ".join(str(v).lower() for v in params.values())
            except Exception:
                vals = ""
            if any(t in vals for t in triggers):
                return DESTRUCTIVE
    if name in {"open_app", "screen_process", "system_status", "web_search",
                "weather_report", "recall_memory", "undo"}:
        return SAFE
    return SENSITIVE


def requires_confirmation(tool_name: str, parameters: dict | None = None) -> bool:
    return classify(tool_name, parameters) == DESTRUCTIVE


def is_blocked(tool_name: str, parameters: dict | None = None) -> bool:
    return classify(tool_name, parameters) == BLOCKED


def refuse_message(tool_name: str) -> str:
    return (
        f"I cannot do '{tool_name}' automatically because it is blocked "
        f"by the permission policy. This protects credentials, security "
        f"settings, and secrets."
    )
