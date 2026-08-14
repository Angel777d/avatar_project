# Time log — design

Two events. `request.log.time` says *a span of time passed*; `action.log.data` says *what that span was*. A plugin that measures time dispatches the first, a plugin that can name what was worked on answers with the second, and `avatar_stats` only listens, stores and draws.

Nothing knows about anything else: pomodoro never hears of kanban, stats never imports either.

## The events

Both names live in `avatar_api.events` — the only api change. No new api components, no core change, no migration.

| event | dispatched by | payload |
| --- | --- | --- |
| `request.log.time` | whatever measured the span: a pomodoro work segment, the manual stopwatch | `{span, started, duration, source}` |
| `action.log.data` | whatever can name it: kanban when a card is current, calendar when an event covers the span, pomodoro for its own runs | the record below |

One **dict** per dispatch rather than positional arguments, so a field added later cannot break an existing listener.

**A source also records itself.** Pomodoro dispatches `request.log.time` *and* its own `action.log.data` (`type: "pomodoro"`), so a run is counted even when no card was current. The stopwatch does the same. Answering a `request.log.time` is optional; ignoring it costs the answerer nothing.

A source may also record something it will not offer for attribution: a pomodoro **break** announces only `action.log.data`, because the day's break time is worth knowing and no card was ever worked on during it. Anything under a second is dropped.

## The record

| field | is | |
| --- | --- | --- |
| `span` | id of the measured span, minted by the source and copied into every record derived from it | suggested |
| `started` | datetime the span began | |
| `duration` | seconds, float | |
| `type` | who is speaking — the plugin name: `kanban`, `calendar`, `pomodoro` | |
| `label` | what it was called then: card title, event title, preset name | |
| `ref` | `static_id` of the entity it was about, empty if none | suggested |
| `source` | what produced the span: `pomodoro`, `manual` | suggested |
| `tags` | tag names copied at record time | suggested |
| `data` | anything else the plugin wants, json blob: column, phase, sequence… | |

`label` and `tags` are snapshots: clearing the board must not erase last month's numbers. `ref` is the live pointer for a drill-down while the entity still exists — the pair covers both.

`span` is what makes the fan-out safe to read. Records of one span are the same time seen from different sides, so a per-type total is honest, a sum across types is not, and grouping by span gives back wall clock.

### A ref can go stale

A static id is unique among the entities that are *alive* — `HashCollection` refuses a second one — but nothing reserves an id a deletion freed. A `uuid4` is never handed out twice; an id a plugin chose itself is, so a record could point at an entity that is not the one it was written about.

- **A static id is generated, never chosen.** Identity by name is a component, the way `TagNameEC` does it — see the kanban change below. With that, nothing in the app can resurrect an id.
- **Stats still never follows a bare `ref`.** It resolves only when the entity now at that id carries a `NoteEC` whose `created` is not newer than the record's `started`. A recreated entity has a younger stamp, so the link reads as *gone* rather than as the wrong card. No extra field: `NoteEC` is api, and anything worth logging is a document with a title. It is two lines, and it holds even if a plugin later reintroduces a hand-made id.
- A stale ref costs nothing else: `label`, `tags` and `data` already hold everything the page shows, and `ref` only decides whether a row can be clicked through.

`source` separates *how* it was measured from *what* it was, which is the one question the record could not otherwise answer: how much of my kanban time came from pomodoros rather than the stopwatch.

## Flow

```
stopwatch stop / pomodoro work segment ends
	→ request.log.time {span, started, duration, source}
		→ kanban: a card is current  → action.log.data {…, type: "kanban",   label: card title,  ref: card id}
		→ calendar: an event covers it → action.log.data {…, type: "calendar", label: event title, ref: note id}
	→ action.log.data {…, type: "pomodoro", label: preset, data: {phase, sequence}}
			→ avatar_stats: one row each
```

## Storage

Plugin `plugins/stats` → distribution / import / entry-point `avatar_stats`, page `time.html`, menu item `Open time`, page title `Time`.

```python
class LogEntryEC(EntityComponent):
	def __init__(self, span: str = "", started: Optional[datetime] = None, duration: float = 0.0,
	             type: str = "", label: str = "", ref: str = "", source: str = "",
	             tags: Optional[List[str]] = None, data: Optional[dict] = None):
```

One entity per record, `StaticIdEC` plus `LogEntryEC`, registered `log_entry` — the rows are keyed on the static id, so a history cannot live in one accumulating component. Everything dispatched is stored, unfiltered; the log is a record of what was said, and reconciling it is the reader's job. No rollup; if a repaint ever feels the row count, a per-day totals component is the answer.

The manual stopwatch is the stats plugin's own: `StopwatchEC(label, started, span)`, one at a time, on an entity carrying no `StaticIdEC` — nothing registered, nothing saved, so a crash cannot resurrect a stopwatch that has been running since Tuesday. Closing it dispatches `request.log.time` with `source: "manual"` and its own `action.log.data` with `type: "stats"`.

It closes on `request.app.close`, not in `stop()`: the application saves *before* it stops the systems, so an entry written in `stop()` is born after the only save and dies with the process. An app killed outright still loses the open span, like everything else unsaved.

## What each plugin adds

| plugin | change |
| --- | --- |
| `avatar.api` | two event names |
| `avatar_pomodoro` | report the segment that just ended — a phase completing, a pause, a reset, `request.app.close` — `duration` measured rather than planned, so a paused gap and a skip cannot count as focus. `__record` still adds `settings.work` to `PomodoroLogEC`, which counts pomodoros rather than seconds, and stays as it is |
| `avatar_kanban` | **every card in the `in_progress` column** claims the span — one record each, same span id, `data.shared` saying how many split it. Moving a card in and out of that column is the whole gesture; how many sit there at once is the user's business. See the column rules below |
| `avatar_calendar` | a `request.log.time` listener answering with the dated note whose `begin`/`end` overlap the span the most, **clipped to the overlap** — a 20 minute span reaching 5 minutes into a meeting is 5 minutes of that meeting. The record keeps the span id, so the clipped view and the full one stay tied; a note without both times is not an event and never answers |
| `plugins/stats` | new — stopwatch, log, page. `pip install -e plugins/stats` or discovery never sees it |

## Kanban columns

A role *is* the identity of a structural column, so there is no separate id to keep and nothing to migrate.

- **Exactly one column per role** — `backlog`, `in_progress`, `done` — and a role never moves. A second claimant found in the database loses it.
- **A role column is never removed, and comes back if it goes missing**, with a fresh generated id. The board is seeded whole only when it is empty; a plain column like *Do next* is seeded once and stays deleted if it is deleted.
- **A card pointing at a column that no longer exists goes to the backlog**, so a vanished column cannot take its cards with it. That is what makes the recreated id harmless: nothing keeps a reference to the old one.
- The page marks the `in_progress` column and says so in its tooltip; nothing on the board sets or moves a role.

## Page

Tab `Time`, filling the window.

- today: total, split by type, a list by label.
- last 7 days: a bar per day.
- by tag, and by source, over a chosen range.
- the raw log, newest first, one row deletable.

## Overlap

Several cards sitting in the in-progress column all claim the same span, so a kanban total counts that span once per card. Nothing is split: dividing by three would invent a precision nobody measured, and the record carries `shared` so a reader can divide, group by `span`, or show the cards as the alternatives they are.

Two sources running at once are two spans, and a plugin answering both logs the overlap twice inside its own type. That is left alone. Nothing clips on write and nothing is refused: every span carries its own id and its own interval, so a reader that cares can spot the collision — sort a day's records by `started`, and any interval reaching past the next one's start is an overlap — and the page decides whether to show the raw sum or the merged one. Clipping at write time would throw away the only evidence that it happened.
