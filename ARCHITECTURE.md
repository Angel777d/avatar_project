# Architecture

## Packages

| package | is | depends on |
| --- | --- | --- |
| `angelovich.core` | ECS `DataStorage`, `Dispatcher`, `System`, plugin discovery (sibling repo `../py_core`) | — |
| `avatar.api` | components, event names, `Env`, `TypeRegistry` | `angelovich.core` |
| `avatar.core` | main loop, systems, plugin policy, storage, timers, the entry point (`python -m avatar_core`) | `avatar.api` |
| `avatar.ui` | `HtmlPage`, `TabbedWindow`, `TransparentWindow`, the window/tab components; also a plugin itself, contributing `UiSystem` | `avatar.api`, PySide6 |
| `plugins/*` | `avatar_default`, `avatar_kanban`, `avatar_calendar`, `avatar_pomodoro`, `avatar_stats`, `avatar_manager` | `avatar.api`, `avatar.ui` |

**Dependency rule: a plugin depends on the api and the ui, never on the core.** `avatar.api` re-exports everything a plugin needs, so `angelovich.core` is not a plugin dependency either. Core depends on api; api never on core.

## Plugin policy

- Discovered through the `avatar.plugins` entry-point group. Distribution name, import name and entry-point name are the same string — except `avatar.ui`, whose distribution name keeps the dot for consistency with the other core packages while its entry point and import name are `avatar_ui`.
- The module exposes `plugin`, an instance of a `Plugin` subclass.
- **A plugin has no lifecycle.** It is named by discovery, then asked once for the systems it contributes: `get_systems(env) -> [System]`. Everything with `start`/`update`/`stop`/`close` is a `System`.
- `get_purpose()` returns tags; the first plugin to claim a tag wins and later claimants are skipped — that is how only one notifier or one UI loads.
- Enabled by default **for now**; disabled by default in release. `plugin_policy.select_plugins` already takes both lists, only `PLUGINS_ENABLED_BY_DEFAULT` flips.
- Disable by entry-point name.

## Runtime

- Core is Qt-free: `avatar_core.main` is a bare `asyncio.run(application.run())`, nothing more. Qt exists nowhere in this process except inside `avatar.ui`'s own thread.
- **`avatar.ui`'s `UiSystem` owns the only `QApplication` in the process**, created on a dedicated thread it starts in its own `start()`, running its own `QtAsyncio` loop so `HtmlPage`'s async page-load code keeps working. No other system, and no plugin, may touch Qt.
- What crosses the thread boundary: a lock-guarded copy (`avatar_ui.sync.Guarded`) carries state from the asyncio thread to the Qt thread (window/page/avatar view components); `loop.call_soon_threadsafe` carries events the other way, from a Qt callback back onto the asyncio loop. Neither side ever touches the other's objects directly.
- `setQuitOnLastWindowClosed(False)` is required, or closing a plugin window kills the Qt thread and orphans the app.
- `QAsyncioEventLoop` has no networking or subprocess support — use `QNetworkAccessManager`, `QtWebSockets`, `QProcess`.
- Order: systems `start` → storage load → `action.storage.restored` → tick loop → storage save → systems `stop` → `close`.
- Systems never call each other: shared state through `DataStorage`, coordination through the event bus.

## Events

`request.*` asks for something, `action.*` announces that it happened. Core's own:

| event | meaning |
| --- | --- |
| `request.app.close` | unwind the application |
| `request.notification.show` | show this `NotificationEC` — the avatar queues and speaks them |
| `request.page.show` (title, window="") | open the window and select that tab |
| `request.timer.start` (name, started, duration) | run a named timer; starting an existing name replaces it |
| `request.timer.cancel` (name) | drop it silently |
| `action.timer.complete` (name) | its deadline passed and the entity is gone |
| `request.log.time` (measured) | a span of time passed, one dict: `span`, `started`, `duration`, `source`. Whoever can name what the span *was* answers with `action.log.data` |
| `action.log.data` (record) | that span, named: the dict above plus `type` — the naming plugin — `label`, `ref`, `tags`, `data`. `avatar_stats` files it, nobody else needs to care. `avatar_api.timelog` builds and dispatches both |
| `action.notification.shown` | one finished being displayed |
| `action.storage.restored` | entities are back; a plugin seeds defaults here if its collection is empty |
| `action.storage.changed` | shared data a plugin does not own has moved — anything displaying it refreshes. Announce it when touching a component another plugin reads, `DateEC` above all; a change to your own components does not need it |

A plugin's own events are its own business — `request.kanban.*`, `request.pomodoro.*` and so on live with the plugin.

## Launcher and release

`supervisor/` is a .NET 9 `WinExe` (`supervisor.exe`). It is the only thing a user runs, and installing is downloading one `.bat` — see [design/supervisor.md](design/supervisor.md) for the reasoning behind all of it.

- **The workspace is the directory the executable sits in**, and everything lives there: `config.json`, the private `uv`, the interpreter, the `.venv`, `data\avatar.db`, and `supervisor.log`. Uninstalling is deleting one folder.
- `supervisor/samples/install.bat` fetches `supervisor.exe` and `config.json` from `releases/latest/download`, writes `seed.json` if absent, and starts it. Both assets are published by the `supervisor` workflow.
- **Provisioning is delegated to `uv`.** The supervisor downloads no python and resolves no dependency; the only network code left fetches `uv` itself — one zip, one sha256, refused outright if it does not match. `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` keep uv inside the workspace.
- Layered fingerprints in `state.json` decide what to rebuild — uv, interpreter, venv, requirements — so a plugin change never re-downloads an interpreter. A phase is recorded as well as a hash, because an interrupted install leaves a venv that looks finished.
- A malformed config refuses to start rather than falling back to discovery.
- The child is assigned to a **job object**, so the app dies with the launcher however the launcher dies — otherwise a force-kill would orphan it and the next launch would give two avatars.
- Restarts the app on failure (3 by default in a rolling window), exits when it exits cleanly, single instance per workspace via a mutex, and logs everything including the child's output.
- The app and the supervisor talk through files in the workspace, one writer each: the app writes `plugins.json` and `request.json`, the supervisor answers in `reply.json`. That is what `avatar_manager` drives.

`setup.bat` builds the same environment without the launcher: finds python 3.13+ or downloads a pinned standalone one, then `pip install`s every package from the repository. `run.bat` starts an environment it already built. Both end at `avatar_core`, the installed entry module.

The GitHub workflows publish `supervisor.exe`, `config.json`, `install.bat` and a wheel per package on a `v*` tag.

## Windows

**Windows and tabs are entities, and their lifecycle is the event.** `ADDED`/`REMOVED` on a collection is the only change notification the storage offers — field changes are never announced — so anything the interface must react to is modelled as a component appearing or disappearing, never as a field to poll.

| entity | carries | meaning |
| --- | --- | --- |
| a window | `WindowEC(name)` | this window exists. **Removing the entity closes it**; there is no separate "visible" flag to disagree with reality |
| a page | `TabEC(title, window)` + `TabViewEC(...)` | a tab titled `title` in the window called `window`. Removing `TabEC` removes the tab |
| the current tab | `CurrentTabEC` | marker, one per window. **Moving it switches tab** and raises the window |

`WindowEC` is hash-keyed by name, so the window for a name is a `find()` rather than a scan. `TabViewEC` carries the html path, the webchannel object name, a JSON snapshot the plugin keeps current, and a method-name-to-event map. `RenderDirtyEC` on a page tells `UiSystem` the view components moved; it clears the marker once it has.

- `request.page.show` creates the window entity if it is missing and moves `CurrentTabEC` onto that page. The marker is always removed and re-added, so asking for the tab that is already up still fires `ADDED` and still raises the window — a plain "is shown" field would compare equal and do nothing.
- Closing a window with its X removes the window entity, which is what destroys the widget. The user's action and the plugin's action are the same operation.
- One window per **window name**, default `""`, and the name is the window's title: `avatar_stats` registers under `Statistics` and opens beside the main window rather than crowding it.
- A tab's widget is built once its window is open, and its web view loads the first time that tab is shown — registering costs nothing.
- Tabs appear in registration order, which follows plugin discovery order.
- **Minimum window size is 720x520** and the default is 960x640, so a page must stay usable at the minimum: fill the space or centre in it. Pomodoro centres, kanban and calendar fill.
- A page's `QObject` bridge is generic (`avatar_ui.bridge.Bridge`: `state()`, `invoke()`, `changed`) and lives entirely on the Qt thread; a plugin never constructs one. `avatar_ui/assets/bridge.js`, injected before any page script runs, is what lets page JS keep calling named methods (`board.move_card(...)`) against that generic object.

## Data

- Plugins share data as **components**, not tables. A plugin owning a concept owns its component class; a concept two plugins both speak is an api component.
- **`DateEC` means the calendar shows it.** It is the shared "this belongs on a day": a calendar note is filed under one, a kanban card's deadline is one. The calendar lists everything carrying a `DateEC` and a `NoteEC`, and only offers to delete the entities it owns. Adding, changing or dropping one is announced with `action.storage.changed`, or the calendar keeps showing the old month until something else redraws it. Anything that merely *records* when something happened must not use `DateEC` — keep a date of your own, or read `NoteEC.created`.
- `TypeRegistry` maps component classes to stable names; a rename orphans stored rows, so persisted types pass an explicit name. A field *added* later loads with its default; a rename or a type change still needs a migration.
- Entities carrying `StaticIdEC` persist to sqlite (WAL) at `data\avatar.db`, under the process's working directory — the supervisor workspace in a real install, the checkout root in dev mode. One table per component type, `c_<registered name>`, keyed on the static id — a row is one component, and `load` groups the rows back into entities. Entity ids are per-session; `StaticIdEC` is the identity that survives. **A static id is generated, never chosen** — a well-known name is a component of its own, `TagNameEC` or `KanbanColumnEC.role`, so an id a deletion freed is never handed to something else and an old reference cannot silently point at the wrong entity. A structural entity found missing is recreated with a fresh id, and whatever pointed at the old one is repaired instead: kanban rehomes orphaned cards to the backlog column.
- A migration is a step against that sqlite connection, registered by the plugin that owns the shape: `env.migrations.add(name, version, step)`. `core_schema` records how far each name has run, so a step runs once; a name with neither a version nor a table is stamped at the latest instead of replayed, so a fresh database skips history. Nothing is registered today — there are no installs to carry forward.
- A row whose json will not parse, or whose type nothing registered, is left where it is rather than swept away.
- Saving happens at shutdown only — a crash costs the session.
- The menu is data, split in two: `MenuItemEC` is what an entry is called, `ActionEC` is the event it dispatches. Core contributes `Close`, plugins contribute their own.
- **`ActionEC` is not menu-specific.** Any entity can carry one and be triggered with `trigger(event_bus, entity, *args)`; the avatar's menu is simply the first thing that does. `set_action` attaches or replaces one.
- Timers are data too: `TimerEC` is keyed on its name and carries the start and duration, so a UI reads the remaining time straight from the storage.
