# Storage design

## Shape

Two layers, deliberately not the same thing:

- **Runtime sharing** — `DataStorage` (ECS) plus `Dispatcher`. This is how plugins see each other's data.
- **Persistence** — SQLite, private to each plugin.

The shared contract between plugins is a **component class**, not a schema. A plugin needing calendar data depends on the calendar package for its component types and reads them from the live `DataStorage`.

## Storages

A **storage** is a named persistence namespace:

```python
store = await core.storage()           # default: the plugin's name
archive = await core.storage("archive")
```

Names are literal and flat. A plugin gets a default storage named after it, and may create any number of others. Picking names that don't collide is the plugin's problem.

Backing: one SQLite file, one table prefix per storage. Creating a storage costs a prefix, not a file — which is what makes any number of them free.

## Decisions

- **SQLite**, WAL, one file: `%LOCALAPPDATA%\avatar_project\avatar.db`.
- **At load the DB is truth; at runtime `DataStorage` is truth.** Plugins rehydrate on start and write through on change.
- Stdlib `sqlite3` in `asyncio.to_thread`. No async driver.
- JSON column queried by `json_extract` is the default shape; promote to real columns and expression indexes when a query needs it.
- Schema version is per storage.

## Rules that follow

**Entity ids are session-local.** `DataStorage.create_entity` mints `uuid4().int` per run and never persists it. Anything surviving a restart needs its own stable id, stored as a column, and rehydration resolves entities through it. Never store a raw `entity_id`.

**`DataStorage` has no change notification for component fields** — `_Collection` dispatches only `ADDED` and `REMOVED`. Persistence is therefore driven by bus events, not by watching the ECS: dispatch an intent, the handler mutates and writes through, as the kanban PoC already does.

**Each plugin persists only the components it owns.** Two plugins may decorate the same entity; each writes its own rows.

**Backup needs a WAL checkpoint first** — copying `.db` without `-wal` loses recent writes.

## Open

- History / append-only not adopted — mutable rows. Revisit before the calendar plugin if undo or sync is wanted.
- Residency: everything loaded at start, or on demand. Fine to defer while data is small.
