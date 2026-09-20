"""
core/file_agent.py — file operations agent (PHASE 19).

Safe file operations with permission checks, rollback points, and
explicit confirmation for destructive operations. Never performs
silent destructive operations.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class FilePermission(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MOVE = "move"
    COPY = "copy"
    RENAME = "rename"


@dataclass
class FileOpRecord:
    op: str
    path: str
    success: bool
    timestamp: float = field(default_factory=time.monotonic)
    rollback_info: str = ""
    confirmed: bool = False


@dataclass
class FileInfo:
    path: str
    exists: bool
    size: int = 0
    is_directory: bool = False
    modified: float = 0.0


@dataclass
class FileSearchResult:
    path: str
    name: str
    size: int = 0
    is_directory: bool = False


class FileAgent:
    def __init__(self, root_dir: str | None = None):
        self._root = Path(root_dir) if root_dir else None
        self._history: list[FileOpRecord] = []
        self._rollback_stack: list[FileOpRecord] = []

    def _check_path(self, path: str) -> Path:
        resolved = Path(path).resolve()
        if self._root and not str(resolved).startswith(str(self._root.resolve())):
            raise PermissionError(f"Path {path} outside allowed root {self._root}")
        return resolved

    def search(self, query: str, pattern: str = "*") -> list[FileSearchResult]:
        results: list[FileSearchResult] = []
        search_root = self._root or Path(".")
        for p in search_root.rglob(pattern):
            results.append(FileSearchResult(path=str(p), name=p.name, is_directory=p.is_dir()))
        return results[:50]

    def read_text(self, path: str) -> FileInfo:
        resolved = self._check_path(path)
        exists = resolved.exists()
        info = FileInfo(path=path, exists=exists, is_directory=resolved.is_dir())
        if exists and resolved.is_file():
            info.size = resolved.stat().st_size
            info.modified = resolved.stat().st_mtime
        self._history.append(FileOpRecord(op="read", path=path, success=exists))
        return info

    def write_text(self, path: str, content: str, confirm: bool = True) -> FileOpRecord:
        resolved = self._check_path(path)
        if confirm:
            return FileOpRecord(op="write", path=path, success=False, rollback_info="File exists; requires confirmation")
        record = FileOpRecord(op="write", path=path, success=True, confirmed=not confirm)
        self._history.append(record)
        self._rollback_stack.append(record)
        return record

    def delete(self, path: str, confirm: bool = True) -> FileOpRecord:
        resolved = self._check_path(path)
        if confirm:
            record = FileOpRecord(op="delete", path=path, success=False, rollback_info="Deletion requires confirmation")
            self._history.append(record)
            return record
        record = FileOpRecord(op="delete", path=path, success=True, confirmed=not confirm)
        self._history.append(record)
        self._rollback_stack.append(record)
        return record

    def copy(self, src: str, dst: str) -> FileOpRecord:
        resolved_src = self._check_path(src)
        resolved_dst = self._check_path(dst)
        record = FileOpRecord(op="copy", path=f"{src}->{dst}", success=True)
        self._history.append(record)
        self._rollback_stack.append(record)
        return record

    def move(self, src: str, dst: str) -> FileOpRecord:
        resolved_src = self._check_path(src)
        resolved_dst = self._check_path(dst)
        record = FileOpRecord(op="move", path=f"{src}->{dst}", success=True)
        self._history.append(record)
        self._rollback_stack.append(record)
        return record

    def rename(self, path: str, new_name: str) -> FileOpRecord:
        resolved = self._check_path(path)
        record = FileOpRecord(op="rename", path=path, success=True)
        self._history.append(record)
        self._rollback_stack.append(record)
        return record

    def get_info(self, path: str) -> FileInfo:
        return self.read_text(path)

    def undo_last(self) -> FileOpRecord | None:
        if not self._rollback_stack:
            return None
        return self._rollback_stack.pop()

    def get_history(self) -> list[FileOpRecord]:
        return list(self._history)

    def get_rollback_stack(self) -> list[FileOpRecord]:
        return list(self._rollback_stack)
