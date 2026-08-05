# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Prototypes only, all under `experiments/` and run with `experiments/.venv/Scripts/python.exe` (PySide6 6.11, Python 3.14). No src tree, no tests, no git repo yet.

- [avatar_poc.py](experiments/avatar_poc.py) — the avatar shell: frameless translucent always-on-top window, procedural painting, ellipse mask so clicks outside the body pass through, drag, click bubble, idle phrases.
- [html_window_poc.py](experiments/html_window_poc.py) + [.html](experiments/html_window_poc.html) — the **window-management prototype**, and the UI answer: HTML/JS view with Python owning all state, bridged by QWebChannel. `BoardWindow` is the reference for how a plugin window gets created and wired.

UI direction settled by these two: native Qt painting for the avatar (needs per-pixel alpha and click-through), HTML in `QWebEngineView` for plugin windows.

`angelovich.core` (sibling repo `D:/Work/py_core`) supplies the plan's data storage and event bus — `DataStorage` (ECS-like) and `Dispatcher` (asyncio). It is editable-installed into `experiments/.venv`; import per-module (`from angelovich.core.Dispatcher import Dispatcher`), as `__init__.py` exports nothing.

`Dispatcher` needs a running asyncio loop. Use `PySide6.QtAsyncio` — `QtAsyncio.run(coro)` replaces `app.exec()` and makes Qt's loop *be* the asyncio loop. Verified: `dispatch()` works from plain Qt slots, handlers stay on the GUI thread across `await`, and it composes with `QWebEngineView`. Constraint: `QAsyncioEventLoop` implements timers/tasks/futures only — all networking and subprocess methods raise `NotImplementedError`, so no `aiohttp`, `asyncio.open_connection`, `websockets`, or `asyncio` subprocesses. Use `QNetworkAccessManager`, `QtWebSockets`, and `QProcess` instead.

`experiments/` is a throwaway sandbox for proofs of concept — everything in it is disposable and safe to delete wholesale. Keep exploratory scripts there, not in the project root.

## User rules (from rules.md)

- No comments in code unless genuinely necessary.
- No commits until the user explicitly says so.
- Keep documentation very compact. Put design work in its own files rather than expanding this one.

## Intended architecture (from PLAN.md)

Windows 11 always-on-top, transparent, animated on-screen avatar that acts as the entry point to all plugins. Layered so components update independently:

- **Supervisor** — Windows native app; launches and oversees the rest.
- **Python core** — data storage, event bus, window management.
- **UI** — layer to be chosen; Python supplies the data.
- **Plugins** — regular Python packages consuming the core API and UI API.

Planned plugins: default avatar (bubble popup on click, random phrase every 30s), double-click menu, calendar app (own window), kanban board (own window).

Core responsibilities now have a prototype each: storage and event bus from `angelovich.core`, window management from `html_window_poc.py`. Open: the supervisor, the plugin API shape, and bridging `Dispatcher`'s asyncio loop to Qt's.
