# avatar_project

Always-on-top transparent character on the Windows desktop, and the entry point to its plugins.
Right-click the avatar for the menu; everything else opens from there.

## Plugins

- **avatar** — the character itself: speaks in bubbles, fills silence with idle phrases, draws a ring for whatever timer is running, and carries the menu every other plugin contributes to.
- **shell** — the tabbed window every other plugin's page appears in.
- **kanban** — a board of columns with drag and drop, and an optional deadline per card.
- **calendar** — the current month, notes on a day, and the deadlines other plugins set.
- **pomodoro** — focus and break timer with its own durations, a count of what ran in a row, and sets that chain one after another.

## Run

```
setup.bat        build the environment and install everything from github
run.bat          start it
```

`setup.bat --run` does both. It finds python 3.13+ or downloads one, so a machine needs nothing installed beyond git.

Working from a checkout instead:

```
python -m pip install -e ../py_core -e api -e ui -e core -e host -e plugins/shell -e plugins/avatar -e plugins/kanban -e plugins/calendar -e plugins/pomodoro
.venv\Scripts\pythonw.exe -m avatar_host
```

Packages, the plugin contract and the data model are in [ARCHITECTURE.md](ARCHITECTURE.md).
