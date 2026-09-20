# JARVIS-X Architecture Audit

Repository: https://github.com/FatihMakes/Mark-LIV
Branch: `liv` (merged `main` = MARK LV)
Generated: JARVIS-X PHASES 1-12 incremental build

---

## A. Current Architecture

Single-process desktop app, `main.py:2280` + `ui.py:5438`.

- **Entry:** `main.py:main()` starts Qt UI thread + `asyncio.run(jarvis.run())` worker.
- **Live session:** `JarvisLive` opens one `asyncio.TaskGroup`: mic (16 kHz) → Gemini Live (`models/gemini-3.1-flash-live-preview`) → speaker (24 kHz).
- **Capabilities:** 16 discovered actions (`actions/*.py` TOOL dict) + 8 inline `TOOL_DECLARATIONS` + plugins (`plugins/*.py` PLUGIN dict) → `LiveConnectConfig function_declarations`.
- **System prompt:** `core/prompt.txt:160`, tokens filled live in `_build_config():952`.
- **State:** RAM session + `memory/long_term.json` + `config/api_keys.json`.
- **UI:** PyQt6 HUD, avatar software render (QPainter), waveform, log, settings, dashboard QR.
- **Undo/Confirm:** `core/undo.py:121`, `core/confirm.py:161`.

## B. Module Responsibilities

| Module | Lines | Responsibility |
|---|---|---|
| `main.py` | 2280 | Session, audio I/O, tool dispatch, monitors |
| `ui.py` | 5438 | PyQt6 HUD, avatar, quiz/review panels, settings |
| `core/action_loader.py` | 221 | `actions/*.py` TOOL discovery + validation |
| `core/plugin_loader.py` | 285 | `plugins/*.py` PLUGIN discovery, enable/disable |
| `core/prompt.txt` | 160 | Personality, `{tokens}` filled at startup |
| `core/confirm.py` | 161 | Irreversible gate (model can't forge) |
| `core/undo.py` | 121 | Shared undo stack (MAX_DEPTH 10) |
| `core/audio_devices.py` | 365 | Mic/speaker picker, measured by name |
| `core/viseme.py` | 238 | Transcript → mouth shapes (50/s) |
| `core/avatar.py` | 617 | Software holographic avatar render |
| `core/wake_word.py` | 190 | Local "Hey Jarvis" detector (opt-in) |

## C. Dependency Relationships

```
ui.py (Qt) ←→ main.py (JarvisLive)
  ├── core/action_loader.py ← actions/*.py
  ├── core/plugin_loader.py ← plugins/*.py
  ├── core/confirm.py ← actions (shutdown/restart/wifi)
  ├── core/undo.py ← actions (file/settings changes)
  ├── core/audio_devices.py ← main.py (mic/speaker probe)
  ├── memory/ ← main.py + ui.py
  └── dashboard/server.py ← main.py (FastAPI :8000)
```

## D. Existing Capabilities (verified)

Voice Live loop, 16 discovered actions, wake word (opt-in), push-to-talk (Win global), echo guard, viseme lip-sync + avatar, undo (10 deep), confirm banner, audio device picker, session resumption (RAM-only), morning briefing + proactive 2.0, background topic monitor, reminders, web search (Gemini → DDG), browser control (Playwright), file processor/controller, system monitor, YouTube/flight/weather/send_message/computer control, remote dashboard, theming, quiz/review UI panels.

## E. Missing Capabilities (JARVIS-X)

Agent loop (plan→verify→replan), task state machine, unified Tool Registry with permission/risk/timeout/verify/rollback, provider-agnostic AI router + fallback, event bus, structured traces, layered memory (short/episodic/semantic/preferences/procedural + semantic search), vision pipeline (capture→OCR/ground→structured observation, sampling cache), safe computer-use priority ladder, optimization engine (measure→plan→checkpoint→apply→benchmark→rollback), coding agent sandbox loop, central permission enforcement (READ_ONLY→BLOCKED), prompt-injection boundary, `.env` config system, `doctor.py`, tests directory, dashboard with live telemetry, logging/tracing, PC Doctor diagnostics, browser hardening, gaming agent.

## F. Technical Debt

- `main.py` ~2.3k + `ui.py` ~5.4k: God-files, UI/business/audio/session intermixed.
- Single Gemini provider hard-wired; model ladder strings scattered; 404/quota observed live (`gemini-2.5-flash` 404, flash-latest quota) with ad-hoc fallbacks.
- Tool schema minimal (name/desc/params/handler); no timeout, permission, verification, rollback fields.
- Memory = one JSON file, lexical search only; history/calendar JSON are local leftovers.
- Vision = on-demand single frame; no caching/sampling/OCR/grounding layer.
- Concurrency: Qt thread + asyncio loop + executor threads + wake thread + confirm worker threads; cancellation via reconnect signal only; no unified task cancellation.
- Config split (`api_keys.json` + env absent); no `.env` example (added).
- No tests directory (added).

## G. Security Risks

- `config/api_keys.json` plaintext; any local process/user can read; must never commit (`.gitignore` pattern fragility fixed).
- Model output = tool args: arbitrary shell/file/browser actions possible if malicious plugin installed; plugin loader imports arbitrary `.py` (crash-isolated but code runs at import).
- `computer_control` (pyautogui/pywinauto), `browser_control` (Playwright), `file_controller` delete/move — destructive without central permission gate.
- Dashboard TLS self-signed + bearer over LAN; firewall auto-open broadens surface.
- External content fed to model as data with no injection boundary (partial: prompt says "result is data" but no structural enforcement).
- Secrets in logs risk; OAuth tokens must stay ignored.

## H. Recommended Architecture (JARVIS-X)

```
UI (voice/text/HUD/tasks/permissions/history)
EVENT BUS (task/system/tool/error/plugin_loaded)
AGENT RUNTIME (planner → executor → verifier → replanner, cancellation)
TOOL REGISTRY (schema + permission + risk + timeout + verify + rollback)
BRAIN (intent → plan → tool select; provider router primary→fallback)
VISION (capture → OCR/ground → structured observation → cache)
COMPUTER / BROWSER / FILE / CODE / SYSTEM / GAME agents (all via registry)
OPTIMIZATION (collect→analyze→plan→confirm→checkpoint→apply→benchmark→rollback)
MEMORY (short / episodic / semantic / preferences / procedural, searchable)
SAFETY (READ_ONLY/SAFE/CONFIRM/PRIVILEGED/DESTRUCTIVE/BLOCKED, confirm UI)
OBSERVABILITY (structured task traces, metrics, error reports)
```

## I. Migration Plan (incremental, no rewrites)

1. **Keep `action_loader`/`plugin_loader` contracts;** extend TOOL/PLUGIN dicts with optional `permission, risk, timeout, verify, rollback` (default-safe, old files keep loading).
2. **Additive `core/` modules** (new files only): `event_bus`, `permissions`, `ai_router`, `task_center`, `history`, `vision`, `computer_use`, `system_agent`, `optimizer`, `coding_agent`, `browser_agent`, `memory2`, `gaming`, `autonomy`, `tool_schema`, `tool_metadata`, `tool_registry`, `agent`, `doctor`, `logging`.
3. **Introduce Agent Runtime** as wrapper around `_execute_tool`, not replacement: OBSERVE→PLAN→EXECUTE→VERIFY→RETRY with per-task trace; single-step tools unchanged.
4. **Vision:** separate `capture` from `analyze`; add OCR/grounding cache behind existing `screen_process`.
5. **Memory:** version JSON stores, add episodic log + semantic index alongside `long_term.json`.
6. **Config:** add `.env.example` + env overlay, keep `api_keys.json` fallback.
7. **Tests:** `tests/` per subsystem with mocks for destructive ops; never touch real env.
8. **Dashboard + Logging:** additive modules; wire into existing UI/events best-effort.

## J. Implementation Roadmap (completed phases)

- **Phase 1** (complete): event_bus, permissions, ai_router, task_center, history, doctor, .env.example, tests/test_phase1 — 11 tests.
- **Phase 2** (complete): tool_schema, tool_metadata, tool_registry — unified Tool Registry w/ enforced timeout; 5 tests.
- **Phase 3** (complete): agent.py — Agent Runtime loop (OBSERVE→PLAN→EXECUTE→VERIFY→RETRY→REPLAN), pause/resume/cancel/status; 5 tests.
- **Phase 4** (complete): vision.py, computer_use.py — capture/downsample/cache, act_and_verify native→a11y→DOM→visual ladder; 5 tests.
- **Phase 5** (complete): system_agent.py — SystemSnapshot diagnostics (CPU/RAM/GPU/disk/thermal/processes); 3 tests.
- **Phase 6** (complete): optimizer.py — COLLECT→ANALYZE→PLAN→CONFIRM→CHECKPOINT→APPLY→BENCHMARK→ROLLBACK; 6 tests.
- **Phase 7** (complete): coding_agent.py — ANALYZE→MODIFY→TEST→REPAIR with blocked commands; 5 tests.
- **Phase 8** (complete): browser_agent.py — observe_page + navigate_with_fallback + injection/secret redaction; 4 tests.
- **Phase 9** (complete): memory2.py — layered memory + search/forget/summarize + secret refusal; 2 tests.
- **Phase 10** (complete): gaming.py — Steam/Epic scan, launch (dry-run), perf ticks, cheat refusal; 5 tests.
- **Phase 11** (complete): autonomy.py — RollbackManager, ErrorRecovery, CircuitBreaker, TaskCheckpointManager; 5 tests.
- **Phase 12** (complete): ui.py version MARK LV, tests/test_phase12; 3 tests.
- **Phase 13+** (current): dashboard.py, logging.py, planner/PC doctor enhancements; in progress.

Each phase: implement → `py_compile` + `doctor` + plugin discovery + targeted mock tests → verify before next.

## K. First Implementation (completed)

Phase 1 implemented: new files only, existing behavior preserved, `doctor.py` + discovery output as gate. See commit history.

---

## Current State Summary (after PHASES 1-12)

- **55 tests pass** (`tests/test_phase1.py` … `test_phase12.py`), mocks/sandbox only, no destructive ops, no network.
- **24 tool specs** registered (16 actions + 8 inline), permission/risk/timeout enforced.
- **APP_VERSION = "MARK LV"** (changed from "MARK LIV" in `ui.py:62`).
- **New modules** (additive, 0 rewrites): `core/agent.py`, `core/vision.py`, `core/computer_use.py`, `core/system_agent.py`, `core/optimizer.py`, `core/coding_agent.py`, `core/browser_agent.py`, `core/memory2.py`, `core/gaming.py`, `core/autonomy.py`, `core/tool_schema.py`, `core/tool_metadata.py`, `core/tool_registry.py`, `core/ai_router.py`, `core/event_bus.py`, `core/history.py`, `core/permissions.py`, `core/task_center.py`, `doctor.py`, `config/.env.example`, `tests/test_phase*.py`.
- **`.gitignore` fixed** — trailing comments made secret patterns non-matching.
- **Plugins** (LV): `quiz_mode`, `calendar_local`, `email_inbox`, `home_assistant`, `printer_3d`, `roblox_assistant`.
- **Existing functionality preserved** — 16 actions, main.py/agent loop, avatar, wake word, undo, confirm, dashboard all untouched.

**Known limitations:** vision analysis fn injectable only (no vision model wired); optimizer preview-only (no real cleanup); browser no Playwright at module load; gaming read-only (no real Steam/Epic detected on this machine); no live model router call_fn wired; plugin permission hooks not yet wired into `main.py`.
