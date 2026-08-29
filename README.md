# avatar_project

Always-on-top transparent character on the Windows desktop, and the entry point to its plugins.
Right-click the avatar for the menu; everything else opens from there.

## Install

Download and run [install.bat](install.bat).

Or working from a checkout instead:

```
python -m pip install -e ../py_core -e api -e ui -e core -e plugins/avatar -e plugins/kanban -e plugins/calendar -e plugins/pomodoro -e plugins/stats -e plugins/manager
.venv\Scripts\pythonw.exe -m avatar_core
```

Packages, the plugin contract and the data model are in [ARCHITECTURE.md](ARCHITECTURE.md).

## Plugins

- **avatar** — the character itself: speaks in bubbles, fills silence with idle phrases, draws a ring for whatever timer is running, and carries the menu every other plugin contributes to.
- **kanban** — a board with drag and drop and an optional deadline per card. Columns can be added, renamed and removed, except the three the board is built on; the cards in the in-progress one are what tracked time is logged against.
- **calendar** — the current month, notes on a day, and the deadlines other plugins set.
- **pomodoro** — focus and break timer with its own durations, a count of what ran in a row, and sets that chain one after another.
- **manager** — the plugin catalogue: what is installed, what the registries offer, and applying a new set through the supervisor.
- **stats** — where the time went, in a window of its own: a stopwatch, whatever the other plugins report, a week-by-hour rhythm, totals by task, tag, plugin and source, what was finished early or late, and a csv export.
