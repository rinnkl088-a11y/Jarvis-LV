"""Phase 19: file_agent."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_import():
    from core.file_agent import FileAgent, FilePermission, FileInfo, FileSearchResult, FileOpRecord
    assert FileAgent is not None
    assert FilePermission.READ.value == "read"


def test_search():
    from core.file_agent import FileAgent
    fa = FileAgent()
    results = fa.search("test")
    assert isinstance(results, list)


def test_read_text():
    from core.file_agent import FileAgent
    fa = FileAgent()
    info = fa.read_text("C:\\nonexistent.txt")
    assert info.exists is False


def test_write_text():
    from core.file_agent import FileAgent
    fa = FileAgent()
    record = fa.write_text("C:\\tmp\\test.txt", "hello", confirm=False)
    assert record.success is True


def test_write_text_requires_confirm():
    from core.file_agent import FileAgent
    fa = FileAgent()
    record = fa.write_text("C:\\tmp\\existing.txt", "data", confirm=True)
    assert record.success is False
    record = fa.write_text("C:\\tmp\\new.txt", "data", confirm=False)
    assert record.success is True


def test_delete():
    from core.file_agent import FileAgent
    fa = FileAgent()
    record = fa.delete("C:\\tmp\\file.txt", confirm=False)
    assert record.success is True


def test_delete_requires_confirm():
    from core.file_agent import FileAgent
    fa = FileAgent()
    record = fa.delete("C:\\tmp\\file.txt", confirm=True)
    assert record.success is False


def test_copy():
    from core.file_agent import FileAgent
    fa = FileAgent()
    record = fa.copy("C:\\a.txt", "C:\\b.txt")
    assert record.op == "copy"
    assert record.success is True


def test_move():
    from core.file_agent import FileAgent
    fa = FileAgent()
    record = fa.move("C:\\a.txt", "C:\\b.txt")
    assert record.op == "move"
    assert record.success is True


def test_rename():
    from core.file_agent import FileAgent
    fa = FileAgent()
    record = fa.rename("C:\\a.txt", "b.txt")
    assert record.op == "rename"
    assert record.success is True


def test_get_info():
    from core.file_agent import FileAgent, FileInfo
    fa = FileAgent()
    info = fa.get_info("C:\\tmp.txt")
    assert isinstance(info, FileInfo)


def test_undo():
    from core.file_agent import FileAgent
    fa = FileAgent()
    fa.write_text("C:\\tmp\\f.txt", "data", confirm=False)
    undo = fa.undo_last()
    assert undo is not None
    assert undo.op == "write"


def test_undo_empty():
    from core.file_agent import FileAgent
    fa = FileAgent()
    assert fa.undo_last() is None


def test_history():
    from core.file_agent import FileAgent
    fa = FileAgent()
    fa.read_text("C:\\tmp.txt")
    fa.write_text("C:\\tmp.txt", "hi", confirm=False)
    hist = fa.get_history()
    assert len(hist) == 2
    assert hist[0].op == "read"
    assert hist[1].op == "write"


def test_rollback_stack():
    from core.file_agent import FileAgent
    fa = FileAgent()
    fa.write_text("C:\\tmp\\a.txt", "data", confirm=False)
    fa.copy("C:\\tmp\\a.txt", "C:\\tmp\\b.txt")
    stack = fa.get_rollback_stack()
    assert len(stack) == 2
    assert stack[0].op == "write"
    assert stack[1].op == "copy"


def test_permission_error():
    from core.file_agent import FileAgent
    fa = FileAgent(root_dir="C:\\allowed")
    with pytest.raises(PermissionError):
        fa.read_text("C:\\outside.txt")
