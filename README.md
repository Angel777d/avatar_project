# avatar_project

Always-on-top transparent character on the Windows desktop, and the entry point to its plugins.
Right-click the avatar for the menu; everything else opens from there.

## Plugins

- **avatar** — the character itself: speaks in bubbles, fills silence with idle phrases, draws a ring for whatever timer is running, and carries the menu every other plugin contributes to.
- **kanban** — a board of columns with drag and drop.
- **calendar** — the current month, notes on a day.
- **pomodoro** — focus and break timer with its own durations, a count of what ran in a row, and sets that chain one after another.

## Run

```
.venv\Scripts\python.exe experiments\host.py
```

`experiments/host.py` is scaffolding until `supervisor/` exists. Packages install editable:

```
pip install -e ../py_core -e api -e ui -e core -e plugins/avatar -e plugins/kanban -e plugins/calendar -e plugins/pomodoro
```

Packages, the plugin contract and the data model are in [ARCHITECTURE.md](ARCHITECTURE.md).
