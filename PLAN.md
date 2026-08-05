# avatar_project — Implementation Plan

**Target platform:** Windows 11
**Goal:** An always-on-top, transparent, animated on-screen character, split into independently updatable components. Entry point to all plugins.
Plugins planned:
1. deafault avatar + simple behavior: show buble popup on click (hello) and random phrases every 30 sec.
2. open menu on duble click
2. calendar app (own window)
3. kanban board app (own window)

1. final Architecture:

- Superviser: windows native app.
- python core: data storage, event bus, windows management
- UI: sugest one. create UI with python as data provider.
- plugins use core API and UI API
- plugins are regular python packages

2. steps
- proof of concept: one file python script to show avatar on screen — done (experiments/)
- review and fill gaps — done (DESIGN_STORAGE.md, ITERATION_1.md)

3. iteration 1 (scope: ITERATION_1.md)
- core: move System/TimeSystem + plugin discovery from yap_torrent, generalise off Env
- core: main loop, system management, plugin enable/disable (startup-only)
- core: sqlite storage, named storages
- core: type registry + component serialisation, persistent id
- api package: note, tag, date, duration, notification components + event names
- ui package: open_window, extracted from the kanban PoC
- kanban plugin: cards become entities, drop .board.json
- calendar plugin: pick date, add note, list notes for a date
- avatar plugin: notification queue, click and idle phrases onto the same pipeline