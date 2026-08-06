# avatar_project

Always-on-top transparent character on the Windows desktop, and the entry point to its plugins.

## Packages

| package | is | depends on |
| --- | --- | --- |
| `angelovich.core` | ECS `DataStorage`, `Dispatcher`, `System`, plugin discovery (sibling repo `../py_core`) | — |
| `avatar.api` | components, event names, `Env`, `TypeRegistry` | `angelovich.core` |
| `avatar.core` | main loop, systems, plugin policy, storage | `avatar.api` |
| `avatar.ui` | `HtmlWindow`, `TransparentWindow` | PySide6 |
| `plugins/*` | avatar, kanban, calendar | `avatar.api`, `avatar.ui` |

**Dependency rule: a plugin depends on the api and the ui, never on the core.** `avatar.api` re-exports everything a plugin needs, so `angelovich.core` is not a plugin dependency either. Core depends on api; api never on core.

## Plugin policy

- Discovered through the `avatar.plugins` entry-point group. Distribution name, import name and entry-point name are the same string.
- The module exposes `plugin`, an instance of a `Plugin` subclass.
- **A plugin has no lifecycle.** It is named by discovery, then asked once for the systems it contributes: `get_systems(env) -> [System]`. Everything with `start`/`update`/`stop`/`close` is a `System`.
- `get_purpose()` returns tags; the first plugin to claim a tag wins and later claimants are skipped — that is how only one notifier or one UI loads.
- Enabled by default **for now**; disabled by default in release. `plugin_policy.select_plugins` already takes both lists, only `PLUGINS_ENABLED_BY_DEFAULT` flips.
- Disable by entry-point name.

## Runtime

- Core is Qt-free. A host creates the `QApplication`, then `QtAsyncio.run(app.run())` — one loop, Qt's, driving asyncio.
- `setQuitOnLastWindowClosed(False)` is required, or closing a plugin window kills the app mid-`await` and skips the save.
- `QAsyncioEventLoop` has no networking or subprocess support — use `QNetworkAccessManager`, `QtWebSockets`, `QProcess`.
- Order: systems `start` → storage load → `action.storage.restored` → tick loop → storage save → systems `stop` → `close`.
- Systems never call each other: shared state through `DataStorage`, coordination through the event bus. `request.*` asks, `action.*` announces.

## Data

- Plugins share data as **components**, not tables. A plugin owning a concept owns its component class.
- `TypeRegistry` maps component classes to stable names; a rename orphans stored rows, so persisted types pass an explicit name.
- Entities carrying `StaticIdEC` persist to sqlite (WAL) at `%LOCALAPPDATA%\avatar_project\avatar.db`, one row per entity. Entity ids are per-session; `StaticIdEC` is the identity that survives.
- A component whose type nothing registered is kept as stored and written back beside the live ones, so running with a plugin disabled neither drops its data nor discards edits to the rest.
- Saving happens at shutdown only — a crash costs the session.
- The menu is data: `MenuItemEC` carries a name and the event to dispatch. Core contributes `Close`, plugins contribute their own.

## Run

```
.venv\Scripts\python.exe experiments\host.py
```

`experiments/host.py` is scaffolding until `supervisor/` exists. Packages install editable: `pip install -e ../py_core -e api -e ui -e core -e plugins/avatar -e plugins/kanban -e plugins/calendar`.
