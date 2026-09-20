"""Phase 18: browser_agent enhanced."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_import():
    from core.browser_agent import BrowserAgent, PageSnapshot, NavigationResult
    assert BrowserAgent is not None


def test_navigate():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    r = ba.navigate("https://example.com")
    assert r.success is True
    assert r.url == "https://example.com"


def test_navigate_injection_detected():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    r = ba.navigate("javascript:alert(1)")
    assert r.success is False


def test_navigate_with_fallback():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    r = ba.navigate_with_fallback("https://example.com", ["https://fallback.com"])
    assert r.success is True
    assert r.url == "https://example.com"


def test_observe_page():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    snap = ba.observe_page("https://example.com")
    assert snap.url == "https://example.com"
    assert snap.state == "idle"


def test_sanitize_input():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    safe = ba.sanitize_input("normal text")
    assert safe == "normal text"


def test_sanitize_injection():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    result = ba.sanitize_input("document.cookie")
    assert "[REDACTED" in result


def test_sanitize_secrets():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    result = ba.sanitize_input("password=secret123")
    assert "[REDACTED" in result


def test_click_element():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    r = ba.click_element("submit", "https://example.com")
    assert r.success is True


def test_type_into():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    r = ba.type_into("name", "John", "https://example.com")
    assert r.success is True


def test_get_page_state():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    snap = ba.get_page_state("https://example.com")
    assert snap.title == ""


def test_extract_links():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    links = ba.extract_links("https://example.com")
    assert len(links) == 3


def test_submit_form():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    r = ba.submit_form("login", "https://example.com")
    assert r.success is True


def test_download():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    r = ba.download("https://example.com/file")
    assert r.success is True


def test_injection_detected_in_element():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    r = ba.click_element("<script>alert(1)</script>", "https://example.com")
    assert r.success is False


def test_navigation_log():
    from core.browser_agent import BrowserAgent
    ba = BrowserAgent()
    ba.navigate("https://a.com")
    ba.navigate("https://b.com")
    log = ba.get_navigation_log()
    assert len(log) == 2
