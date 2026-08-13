# Architecture

## Packages

| package | is | depends on |
| --- | --- | --- |
| `angelovich.core` | ECS `DataStorage`, `Dispatcher`, `System`, plugin discovery (sibling repo `../py_core`) | — |
| `avatar.api` | components, event names, `Env`, `TypeRegistry` | `angelovich.core` |
| `avatar.core` | main loop, systems, plugin policy, storage, timers | `avatar.api` |
| `avatar.host` | the Qt entry point: `QApplication`, `QtAsyncio`, `avatar_host` | `avatar.core`, PySide6 |
| `avatar.ui` | `HtmlPage`, `TabbedWindow`, `HtmlWindow`, `TransparentWindow` | PySide6 |
| `plugins/*` | `avatar_shell`, `avatar_default`, `avatar_kanban`, `avatar_calendar`, `avatar_pomodoro` | `avatar.api`, `avatar.ui` |

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
| `request.page.register` (title, path, objects, window="") | contribute a page; it becomes a tab in that window |
| `request.page.show` (title, window="") | open the window and select that tab |
| `request.timer.start` (name, started, duration) | run a named timer; starting an existing name replaces it |
| `request.timer.cancel` (name) | drop it silently |
| `action.timer.complete` (name) | its deadline passed and the entity is gone |
| `action.notification.shown` | one finished being displayed |
| `action.storage.restored` | entities are back; a plugin seeds defaults here if its collection is empty |
| `action.storage.changed` | shared data a plugin does not own has moved — anything displaying it refreshes. Announce it when touching a component another plugin reads, `DateEC` above all; a change to your own components does not need it |

A plugin's own events are its own business — `request.kanban.*`, `request.pomodoro.*` and so on live with the plugin.

## Launcher and release

`supervisor/` is a .NET 9 `WinExe` (`avatar.exe`). It is the only thing a user runs.

- **Development**: with no `bootstrap.json` beside it, it walks up from its own directory for `.venv\Scripts\pythonw.exe` and runs `experiments\host.py` from that root.
- **Release**: `bootstrap.json` (see `bootstrap.example.json`) makes it provision instead — download a pinned standalone CPython, check its sha256, unpack, build a venv, `pip install` the configured packages, then run the configured entry module. The runtime lives in `%LOCALAPPDATA%\avatar_project\runtime`.
- Provisioning is skipped when a state file matches a fingerprint of the url, checksum, index and package list; change any of them and the next launch re-provisions.
- A missing or wrong checksum refuses the download rather than running it. A malformed config refuses to start rather than falling back to discovery.
- The child is assigned to a **job object**, so the app dies with the launcher however the launcher dies — otherwise a force-kill would orphan it and the next launch would give two avatars.
- Restarts the app on failure (3 attempts by default), exits when the app exits cleanly, single instance via a global mutex, logs everything including the child's output to `%LOCALAPPDATA%\avatar_project\launcher.log`.
- Unpacking shells out to Windows' `tar.exe`; `System.Formats.Tar` mangles filenames in these archives.

`setup.bat` does the same provisioning without the launcher: finds python 3.13+ or downloads the pinned standalone one, then `pip install`s every package from the repository subdirectories. `run.bat` starts an environment it already built. Both end at `avatar_host`, the installed entry module — `experiments/host.py` only exists in a checkout.

Still missing for a real release: `avatar_project` is a private repository, so installing from it needs credentials, and the packages are not published anywhere.

## Windows

Plugins do not own windows. A plugin registers a page and asks for it by title; the `avatar_shell` plugin owns the windows and puts each page in a tab.

- One window per **window name**, default `""`. Pass a name to get a second window instead of another tab.
- A window is created on the first `request.page.show` for it, and a tab's web view is built and loaded the first time that tab is shown — registering costs nothing.
- Tabs appear in registration order, which follows plugin discovery order.
- **Minimum window size is 720x520** and the default is 960x640, so a page must stay usable at the minimum: fill the space or centre in it. Pomodoro centres, kanban and calendar fill.
- `avatar_shell` subscribes in its constructor rather than in `start()`, because plugins register their pages during `start()` and system start order follows discovery order.

## Data

- Plugins share data as **components**, not tables. A plugin owning a concept owns its component class; a concept two plugins both speak is an api component.
- **`DateEC` means the calendar shows it.** It is the shared "this belongs on a day": a calendar note is filed under one, a kanban card's deadline is one. The calendar lists everything carrying a `DateEC` and a `NoteEC`, and only offers to delete the entities it owns. Adding, changing or dropping one is announced with `action.storage.changed`, or the calendar keeps showing the old month until something else redraws it. Anything that merely *records* when something happened must not use `DateEC` — keep a date of your own, or read `NoteEC.created`.
- `TypeRegistry` maps component classes to stable names; a rename orphans stored rows, so persisted types pass an explicit name. A field *added* later loads with its default; a rename or a type change still needs a migration.
- Entities carrying `StaticIdEC` persist to sqlite (WAL) at `%LOCALAPPDATA%\avatar_project\avatar.db`. One table per component type, `c_<registered name>`, keyed on the static id — a row is one component, and `load` groups the rows back into entities. Entity ids are per-session; `StaticIdEC` is the identity that survives. **A static id is generated, never chosen** — a well-known name is a component of its own, `TagNameEC` or `KanbanColumnEC.key`, so an id a deletion freed is never handed to something else and an old reference cannot silently point at the wrong entity.
- A migration is a step against that sqlite connection, registered by the plugin that owns the shape: `env.migrations.add(name, version, step)`. `core_schema` records how far each name has run, so a step runs once; a name with neither a version nor a table is stamped at the latest instead of replayed, so a fresh database skips history. `kanban_column` v1 is the only one: it moves the columns' hand-made ids into `key`, mints generated ones and repoints the cards.
- A row whose json will not parse, or whose type nothing registered, is left where it is rather than swept away.
- Saving happens at shutdown only — a crash costs the session.
- The menu is data, split in two: `MenuItemEC` is what an entry is called, `ActionEC` is the event it dispatches. Core contributes `Close`, plugins contribute their own.
- **`ActionEC` is not menu-specific.** Any entity can carry one and be triggered with `trigger(event_bus, entity, *args)`; the avatar's menu is simply the first thing that does. `set_action` attaches or replaces one.
- Timers are data too: `TimerEC` is keyed on its name and carries the start and duration, so a UI reads the remaining time straight from the storage.
