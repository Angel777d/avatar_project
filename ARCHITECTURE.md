# Architecture

## Packages

| package | is | depends on |
| --- | --- | --- |
| `angelovich.core` | ECS `DataStorage`, `Dispatcher`, `System`, plugin discovery (sibling repo `../py_core`) | — |
| `avatar.api` | components, event names, `Env`, `TypeRegistry` | `angelovich.core` |
| `avatar.core` | main loop, systems, plugin policy, storage, timers, the entry point (`python -m avatar_core`) | `avatar.api` |
| `avatar.ui` | `HtmlPage`, `TabbedWindow`, `TransparentWindow`, the window and tab components; also a plugin, contributing `UiSystem` | `avatar.api`, PySide6 |
| `plugins/*` | `avatar_default`, `avatar_kanban`, `avatar_calendar`, `avatar_pomodoro`, `avatar_stats`, `avatar_manager` | `avatar.api`, `avatar.ui` |

**Dependency rule: a plugin depends on the api and the ui, never on the core.** `avatar.api` re-exports everything a plugin needs, so `angelovich.core` is not a plugin dependency either. Core depends on api; api never on core.

## Plugin policy

- Discovered through the `avatar.plugins` entry-point group. Distribution name, import name and entry-point name are the same string; `avatar.ui` is the exception, discovered as `avatar_ui`.
- The module exposes `plugin`, an instance of a `Plugin` subclass.
- **A plugin has no lifecycle.** It is named by discovery, then asked once for the systems it contributes: `get_systems(env) -> [System]`. Everything with `start`/`update`/`stop`/`close` is a `System`.
- `get_purpose()` returns tags; the first plugin to claim a tag wins and later claimants are skipped. That is how only one avatar and one interface load — `avatar_default` claims `avatar` and `notify`, `avatar_ui` claims `shell`.
- Plugins are enabled by default (`PLUGINS_ENABLED_BY_DEFAULT`) and disabled by entry-point name.

## Runtime

- Core is Qt-free: `avatar_core.main` is a bare `asyncio.run(application.run())`.
- **`avatar.ui`'s `UiSystem` owns the process's only `QApplication`**, on a dedicated thread it starts in `start()`, running its own `QtAsyncio` loop so `HtmlPage`'s async page load keeps working. No other system and no plugin may touch Qt, from either thread.
- State crosses to the Qt thread as a lock-guarded plain copy (`avatar_ui.sync.Guarded`, `avatar_ui.render`); events cross back with `call_soon_threadsafe`. Neither side touches the other's objects.
- `setQuitOnLastWindowClosed(False)`, or closing the last window ends the Qt thread and leaves the app running blind.
- Order: systems `start` → storage load → `action.storage.restored` → tick loop → storage save → systems `stop` → `close`. Pages therefore register before their data exists, and must refresh on `action.storage.restored`.
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
| `request.log.time` (measured) | a span passed — `span`, `started`, `duration`, `source`. Whoever can name what it *was* answers with `action.log.data` |
| `action.log.data` (record) | that span, named: plus `type`, `label`, `ref`, `tags`, `data`. `avatar_stats` files it. `avatar_api.timelog` builds and dispatches both |
| `action.notification.shown` | one finished being displayed |
| `action.storage.restored` | entities are back; seed defaults and refresh pages here |
| `action.storage.changed` | shared data a plugin does not own has moved — anything displaying it refreshes. Announce it when touching a component another plugin reads, `DateEC` above all; your own components do not need it |

A plugin's own events are its own business — `request.kanban.*`, `request.pomodoro.*` and so on live with the plugin.

## Windows

**Windows and tabs are entities, and their lifecycle is the event.** `ADDED`/`REMOVED` on a collection is the only change notification the storage offers — field changes are never announced — so anything the interface reacts to is a component appearing or disappearing, never a field to poll. `REMOVED` carries the entity id, not the entity, which by then has been stripped of its components.

| entity | carries | meaning |
| --- | --- | --- |
| a window | `WindowEC(name)` | this window exists. **Removing the entity closes it**; no separate "visible" flag can disagree with the screen |
| a page | `TabEC(title, window)` + `TabViewEC(...)` | a tab in that window. Removing `TabEC` removes the tab |
| the current tab | `CurrentTabEC` | marker, one per window. **Moving it switches tab** and raises the window |

`WindowEC` is hash-keyed by name. `TabViewEC` carries the html path, the webchannel object name, a JSON snapshot the plugin keeps current, and a method-name-to-event map. `RenderDirtyEC` on a page tells `UiSystem` its view components moved; `UiSystem` clears it once read.

- `request.page.show` creates the window entity if missing and moves `CurrentTabEC`. The marker is always removed and re-added, so asking for the tab already up still fires `ADDED` and still raises — an "is shown" field would compare equal and do nothing.
- Closing a window with its X removes the window entity, which is what destroys the widget: the user's action and a plugin's are one operation.
- One window per **window name**, default `""`, and the name is its title: `avatar_stats` registers under `Statistics` and opens beside the main window.
- A tab's widget is built once its window is open, and loads the first time it is shown — registering costs nothing. Tabs appear in registration order, which follows discovery order.
- **Minimum window size is 720x520**, default 960x640, so a page must stay usable at the minimum: fill the space or centre in it.
- The page's `QObject` bridge is generic (`avatar_ui.bridge.Bridge`: `state()`, `invoke()`, `changed`) and lives on the Qt thread; a plugin never constructs one. `avatar_ui/assets/bridge.js`, injected before any page script, lets page JS keep calling named methods against it.
- **A page reads what was pushed.** A zero-argument call is answered from the cached snapshot; arguments only ask the app to change something, and never return a value. An unchanged snapshot is not pushed again, so anything waiting on `changed` for an identical answer waits forever.

## Data

- Plugins share data as **components**, not tables. A plugin owning a concept owns its component class; a concept two plugins speak is an api component.
- **`DateEC` means the calendar shows it.** The shared "this belongs on a day": a calendar note is filed under one, a kanban card's deadline is one. The calendar lists everything carrying a `DateEC` and a `NoteEC`, and only offers to delete what it owns. Adding, changing or dropping one is announced with `action.storage.changed`. Anything that merely *records* when something happened must not use `DateEC` — keep a date of your own, or read `NoteEC.created`.
- `TypeRegistry` maps component classes to stable names; a rename orphans stored rows, so persisted types pass an explicit name. A field *added* later loads with its default; a rename or type change needs a migration.
- Entities carrying `StaticIdEC` persist to sqlite (WAL) at `data\avatar.db`, under the working directory — the supervisor workspace installed, the checkout root in development. One table per component type, `c_<registered name>`, keyed on the static id: a row is one component, and `load` groups rows back into entities.
- Entity ids are per-session; `StaticIdEC` is the identity that survives. **A static id is generated, never chosen** — a well-known name is a component of its own, `TagNameEC` or `KanbanColumnEC.role` — so an id a deletion freed is never handed to something else. A structural entity found missing is recreated with a fresh id and whatever pointed at the old one is repaired: kanban rehomes orphaned cards to the backlog.
- A migration is a step against that sqlite connection, registered by the plugin owning the shape: `env.migrations.add(name, version, step)`. `core_schema` records how far each name has run, so a step runs once; a name with neither a version nor a table is stamped at the latest rather than replayed, so a fresh database skips history. Nothing is registered today.
- A row whose json will not parse, or whose type nothing registered, is left where it is rather than swept away.
- Saving happens at shutdown only — a crash costs the session.
- The menu is data, split in two: `MenuItemEC` is what an entry is called, `ActionEC` is the event it dispatches. Core contributes `Close`.
- **`ActionEC` is not menu-specific.** Any entity can carry one and be triggered with `trigger(event_bus, entity, *args)`; the menu is simply the first thing that does. `set_action` attaches or replaces one.
- Timers are data too: `TimerEC` is keyed on its name and carries start and duration, so a UI reads the remaining time straight from storage.

## Launcher and release

`supervisor/` is a .NET 9 `WinExe` (`supervisor.exe`), the only thing a user runs. [design/supervisor.md](design/supervisor.md) has the reasoning.

- **The workspace is the directory the executable sits in**: `config.json`, the private `uv`, the interpreter, the `.venv`, `data\avatar.db`, `supervisor.log`. Uninstalling is deleting one folder.
- `supervisor/samples/install.bat` fetches `supervisor.exe` and `config.json` from `releases/latest/download`, writes `seed.json` if absent, and starts it.
- **Provisioning is delegated to `uv`.** The supervisor downloads no python and resolves no dependency; the only network code left fetches `uv` itself — one zip, one sha256, refused outright on a mismatch. `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` keep it inside the workspace.
- Layered fingerprints in `state.json` decide what to rebuild — uv, interpreter, venv, requirements — so a plugin change never re-downloads an interpreter. A phase is recorded alongside each hash, because an interrupted install leaves a venv that looks finished.
- A malformed config refuses to start rather than falling back to discovery.
- The child is assigned to a **job object**, so the app dies with the launcher however the launcher dies; otherwise a force-kill orphans it and the next launch gives two avatars.
- Restarts on failure (3 in a rolling window by default), exits when the app exits cleanly, one instance per workspace via a mutex, and logs the child's output.
- App and supervisor talk through files in the workspace, one writer each: the app writes `plugins.json` and `request.json`, the supervisor answers in `reply.json`. That is what `avatar_manager` drives.

`setup.bat` builds the same environment without the launcher, then `run.bat` starts it; both end at `avatar_core`. The GitHub workflows publish `supervisor.exe`, `config.json`, `install.bat` and a wheel per package on a `v*` tag.
