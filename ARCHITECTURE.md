# Architecture

## Packages

| package | is | depends on |
| --- | --- | --- |
| `angelovich.core` | ECS `DataStorage`, `Dispatcher`, `System`, plugin discovery (sibling repo `../py_core`) | — |
| `avatar.api` | components, event names, `Env`, `TypeRegistry` | `angelovich.core` |
| `avatar.core` | main loop, systems, plugin policy, storage, timers | `avatar.api` |
| `avatar.ui` | `HtmlWindow`, `TransparentWindow` | PySide6 |
| `plugins/*` | `avatar_default`, `avatar_kanban`, `avatar_calendar`, `avatar_pomodoro` | `avatar.api`, `avatar.ui` |

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
- Systems never call each other: shared state through `DataStorage`, coordination through the event bus.

## Events

`request.*` asks for something, `action.*` announces that it happened. Core's own:

| event | meaning |
| --- | --- |
| `request.app.close` | unwind the application |
| `request.notification.show` | show this `NotificationEC` — the avatar queues and speaks them |
| `request.timer.start` (name, started, duration) | run a named timer; starting an existing name replaces it |
| `request.timer.cancel` (name) | drop it silently |
| `action.timer.complete` (name) | its deadline passed and the entity is gone |
| `action.notification.shown` | one finished being displayed |
| `action.storage.restored` | entities are back; a plugin seeds defaults here if its collection is empty |

A plugin's own events are its own business — `request.kanban.*`, `request.pomodoro.*` and so on live with the plugin.

## Launcher and release

`supervisor/` is a .NET 9 `WinExe` (`avatar.exe`). It is the only thing a user runs.

- **Development**: with no `bootstrap.json` beside it, it walks up from its own directory for `.venv\Scripts\pythonw.exe` and runs `experiments\host.py` from that root.
- **Release**: `bootstrap.json` (see `bootstrap.example.json`) makes it provision instead — download a pinned standalone CPython, check its sha256, unpack, build a venv, `pip install` the configured packages, then run the configured entry module. The runtime lives in `%LOCALAPPDATA%vatar_project
untime`.
- Provisioning is skipped when a state file matches a fingerprint of the url, checksum, index and package list; change any of them and the next launch re-provisions.
- A missing or wrong checksum refuses the download rather than running it. A malformed config refuses to start rather than falling back to discovery.
- The child is assigned to a **job object**, so the app dies with the launcher however the launcher dies — otherwise a force-kill would orphan it and the next launch would give two avatars.
- Restarts the app on failure (3 attempts by default), exits when the app exits cleanly, single instance via a global mutex, logs everything including the child's output to `%LOCALAPPDATA%vatar_project\launcher.log`.
- Unpacking shells out to Windows' `tar.exe`; `System.Formats.Tar` mangles filenames in these archives.

Still missing for a real release: the packages are not published anywhere, and `avatar_host` — the entry module that replaces `experiments/host.py` — does not exist yet.

## Data

- Plugins share data as **components**, not tables. A plugin owning a concept owns its component class.
- `TypeRegistry` maps component classes to stable names; a rename orphans stored rows, so persisted types pass an explicit name. A field *added* later loads with its default; a rename or a type change still needs a migration.
- Entities carrying `StaticIdEC` persist to sqlite (WAL) at `%LOCALAPPDATA%\avatar_project\avatar.db`, one row per entity. Entity ids are per-session; `StaticIdEC` is the identity that survives.
- A component whose type nothing registered is kept as stored and written back beside the live ones, so running with a plugin disabled neither drops its data nor discards edits to the rest.
- Saving happens at shutdown only — a crash costs the session.
- The menu is data: `MenuItemEC` carries a name and the event to dispatch. Core contributes `Close`, plugins contribute their own.
- Timers are data too: `TimerEC` is keyed on its name and carries the start and duration, so a UI reads the remaining time straight from the storage.
