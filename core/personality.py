"""Concise, transparent response formatting."""
from __future__ import annotations


def report(success: bool, message: str, *, details: str = "") -> str:
    if success:
        return f"Completed: {message}" + (f"\n{details}" if details else "")
    return f"I couldn't complete that: {message}" + (f"\n{details}" if details else "")


def clarification(question: str) -> str:
    return question.strip().rstrip("?") + "?"
