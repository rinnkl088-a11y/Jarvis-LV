"""
Quiz mode plugin — drives the existing HUD quiz panel (ui.show_quiz).

No network, no new deps. Generates choice/gap questions locally
from the given topic, or renders caller-supplied questions.
Grading lives here so ui.py stays dumb.
"""
from difflib import SequenceMatcher

PLUGIN = {
    "name": "quiz_mode",
    "description": (
        "Interactive quiz — JARVIS writes questions, you answer on screen. "
        "Use when the user says quiz me, test me, practice, exam questions "
        "on a topic. Shows the HUD quiz panel."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "topic": {"type": "STRING", "description": "Quiz topic, e.g. Luau basics"},
            "count": {"type": "STRING", "description": "Number of questions 3-8 (default 5)"},
        },
        "required": ["topic"],
    },
}

_BANK = {
    "luau": [
        {"question": "Which keyword declares a local variable in Luau?",
         "choices": ["local", "var", "let", "dim"], "answer": "local"},
        {"question": "RemoteEvent :FireServer() runs on which side?",
         "choices": ["client -> server", "server -> client",
                     "server -> server", "client -> client"],
         "answer": "client -> server"},
        {"question": "Complete: game:GetService('___') for player management.",
         "answer": "Players"},
    ],
    "default": [
        {"question": "What does CPU stand for?",
         "choices": ["Central Processing Unit", "Computer Personal Unit",
                     "Central Program Utility", "Core Processing Utility"],
         "answer": "Central Processing Unit"},
        {"question": "Complete the phrase: practice makes ___.",
         "answer": "perfect"},
        {"question": "Which is a version control system?",
         "choices": ["git", "jpg", "mp3", "pdf"], "answer": "git"},
    ],
}


def _pick(topic: str, count: int):
    key = "luau" if "lua" in topic.lower() or "roblox" in topic.lower() else "default"
    pool = _BANK[key]
    out = []
    i = 0
    while len(out) < count:
        out.append(dict(pool[i % len(pool)]))
        i += 1
    return out


def _grade(question: dict, given: str) -> tuple[bool, str]:
    want = str(question.get("answer", "")).strip()
    got = (given or "").strip()
    if not want:
        return True, "Noted."
    if got.lower() == want.lower():
        return True, "Correct."
    ratio = SequenceMatcher(None, got.lower(), want.lower()).ratio()
    if ratio >= 0.8:
        return True, f"Close enough — accepted ({want})."
    return False, f"Answer: {want}."


def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    topic = str(params.get("topic", "general")).strip()[:60] or "general"
    try:
        count = max(3, min(8, int(str(params.get("count", "5")))))
    except (TypeError, ValueError):
        count = 5
    questions = _pick(topic, count)
    if player is None:
        return f"Quiz ready on '{topic}' ({count} questions) but UI is unavailable."
    try:
        show = getattr(player, "show_quiz", None)
        if callable(show):
            show(topic, questions, _grade)
        else:
            return "Quiz UI is not available in this build."
    except Exception as e:
        return f"quiz_mode failed: {e}"
    try:
        player.write_log(f"JARVIS: Quiz on '{topic}' — {count} questions on screen.")
    except Exception:
        pass
    return f"Quiz on '{topic}' is on screen — {count} questions. Answer there at your pace."
