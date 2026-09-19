"""
core/permissions.py — SAFE / SENSITIVE / DESTRUCTIVE / BLOCKED gate.

Model must never silently bypass user permission. This module only
classifies; enforcement lives in the caller (confirm.py banner for
DESTRUCTIVE, refuse for BLOCKED, undo stack for reversible SENSITIVE).
"""
from __future__ import annotations

SAFE = "SAFE"
SENSITIVE = "SENSITIVE"
DESTRUCTIVE = "DESTRUCTIVE"
BLOCKED = "BLOCKED"

# Tools that always need the on-screen CONFIRM banner (irreversible).
_DESTRUCTIVE_TOOLS = {
    "shutdown_jarvis",  # ends session; still gated for explicitness
    "restart",
    "shutdown",
    "toggle_wifi",
    "delete_file",
    "delete_folder",
    "send_message",
    "run_destructive_command",
}

# Parameter-level destructive signals (action name -> trigger values).
_DESTRUCTIVE_PARAMS = {
    "computer_settings": {"restart", "shutdown"},
    "file_controller": {"delete", "move_to_trash"},
}

# Never allowed automatically, even with confirmation.
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
            # Reading the key file itself is blocked; the running app reads
            # it internally, the model must never be handed the contents.
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
    # Reversible state changes and reads that touch the user.
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
