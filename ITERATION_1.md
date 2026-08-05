# Iteration 1

## Packages

1. **`angelovich.core`** — finish it. Move `System`/`TimeSystem` and the plugin base + entry-point discovery in from yap_torrent, generalised (context contract instead of yap's `Env`, entry-point group as a parameter, disabled names as a plain iterable).
2. **Core API** — the shared vocabulary: component structs and event names. Plugins depend on this, not on core internals.
3. **Plugins** — avatar (placeholder), calendar, kanban.

## Core holds

- Main loop
- Plugin observer (discovery)
- Plugin management — enable / disable
- Persistent storage access (see [DESIGN_STORAGE.md](DESIGN_STORAGE.md))
- System management
- **Type registry** — plugin classes registered by name so whole components serialise to and from storage

## Core API structs

| Component | Carries |
| --- | --- |
| Static id | the persistent id; the thing `entity_id` cannot be |
| Note | title, text, created, updated |
| Tag | — |
| Date | — |
| Duration | — |
| Notification | consumed by the avatar, or by a plugin that raises a Windows toast instead |

## Plugins

**Avatar** — the current PoC, plus a notification queue: catch the notification event, queue it, show one at a time. Click replies and idle phrases move onto that same pipeline rather than driving the bubble directly.

**Calendar** — select a date, add a note to it, read back the notes for a date.

**Kanban** — the current PoC, re-backed: every task is a `DataStorage` entity carrying static id + note + kanban-task + date components, persisted in the core database. `.board.json` goes away.

## Out of scope

Supervisor (native Windows app), double-click menu plugin.

## Open

- **Window/UI API.** Calendar and kanban each need their own window; nothing in the list above owns window creation. `BoardWindow` in the PoC is the prototype — it needs a home.
- **Where the API package lives.** Note/date/kanban/notification are avatar-domain, not generic ECS — putting them in `py_core` would make a reusable package carry this app's vocabulary.
- **Notification lifetime.** A persisted component (survives restart, needs a "shown" marker so it is not re-shown, and a rule for which presenter claims it) or a transient event (simpler, lost on crash).
- **Enable/disable timing.** Startup-only (config list, as yap does it) or live — live means stopping a running plugin and tearing down its windows, listeners and components mid-run.
- **Registry naming.** Registered names must be stable strings, not `__qualname__`, or a refactor orphans stored rows. Decide what load does when a component's class is missing because its plugin is gone: skip and keep the rows, or drop them.
