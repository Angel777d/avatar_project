# Statistics views — design

What the `Time` tab shows, and what each view needs to exist. The data model it reads is [time_statistics.md](time_statistics.md).

## What the log cannot answer

Every view about *duration* is already computable: the log is a stream of spans with a type, a label, a ref and tags. Every view about a task's **life** — created, finished, late, abandoned — is not, because the log only records time and `avatar_stats` may not import `avatar_kanban` to ask.

So the log gains a second kind of entry, symmetric with the first: `action.log.data` is a **span**, `action.log.event` is a **moment**.

```
action.log.event  {when, type, event, label, ref, tags, data}
```

`event` is the verb — `created`, `done`, `undone` — and `type` is the plugin saying it, exactly as in a span. Kanban dispatches `created` when a card is added, `done` when one enters the column with `ROLE_DONE`, `undone` when it leaves; `data` carries the deadline it had at that moment. Nothing else has to speak it, and stats stores it without knowing what a card is.

That addition is in — the table below is what it unlocks, and the views themselves are what is left.

| view | needs | status |
| --- | --- | --- |
| totals, averages, per-day series | spans | now |
| by task, by tag, by plugin, by source | spans | now |
| work rhythm heatmap, the insight line | spans | now |
| activity streak, focus streak | spans | now |
| the raw log, export | spans | now |
| created / completed / completion rate | events | now |
| completion streak | events | now |
| completion timing against a deadline | events + `data.deadline` | now |
| zombie and stuck tasks | events + spans | now |

## The page

**Its own window.** `avatar_stats` registers under the window name `Statistics`, so the dashboard opens beside the board instead of as a fifth tab competing with it for 280px columns. One scrolling page inside it, not tabs — at the 720 minimum a tab bar costs more than it saves. Sections in this order, each a card in a `repeat(auto-fit, minmax(280px, 1fr))` grid so three cards on a wide window become one column at the minimum.

**Toolbar** — range `7 days · 30 days · 1 year · custom`, and export. The range drives every view on the page; `custom` reveals two date inputs.

**Totals** — tracked, average per day, created, completed, completion rate. Average per day has a toggle: *calendar days in range* or *days you actually worked*, because with three tracked days out of thirty those numbers differ by ten times and only one of them is the honest answer to "how much do I work".

**Rhythm** — a 7 × 24 heatmap, weekday across, hour down, cell shaded by tracked seconds against the busiest cell. A span crossing an hour boundary is split across the cells it covers, or a 50 minute pomodoro started at 16:50 lies about the evening. Above it, one sentence: *most focused time happens on Thursdays around 5pm*, with the caveat *(based on limited data)* until the log holds tracked time on seven distinct days.

**Where it goes** — by task (bar list, longest first, label snapshot), by tag, by plugin and source. Every bar is a share of the largest, not of the total, so a long tail stays readable.

**Tasks** — completion timing (early · on time · late, against the deadline the card carried when it was finished), zombie tasks (created 14+ days ago, never tracked, never finished) and stuck tasks (tracked once, nothing for 7+ days, not finished). Counts, each clickable to a list.

**Streak** — three modes over the same row of days: *completion* (a `done` event), *activity* (any span), *focus* (a span from the pomodoro). One square per day in the range, capped at 30 squares.

**Log** — what is there today: newest first, one row deletable.

### Rules for every card

- **Bucket by range.** 7 and 30 days are per day; a year is per week. Never draw 365 bars.
- **Empty states say what would fill them** — *no tasks with tracked time yet*, not *no data*. Half of these cards are empty on day one and that is the normal state of a fresh install.
- Dark palette as everywhere else. The heatmap is one accent with five alpha steps, so a colour-blind reader still reads intensity.
- A number nobody can act on is not worth a card. Anything that stays zero for a month should be cut rather than explained.

## Export

A `@Slot` writing the spans of the selected range as csv beside the database — `%LOCALAPPDATA%\avatar_project\time-<from>-<to>.csv`, one row per record, then `request.notification.show` with the path so the avatar says where it went. No file dialog: `QAsyncioEventLoop` runs the loop and a modal native dialog inside it is a hang waiting to happen.

## Implementation

| step | change |
| --- | --- |
| 1 | **done** — `avatar_stats/summary.py` holds the aggregation, `export.py` the csv, `time.html` the dashboard, and the page lives in the `Statistics` window |
| 2 | **done** — `action.log.event` in `avatar_api.events`, `log_event()` beside `log_time`/`log_data`, `LogEventEC` registered `log_event` in stats |
| 3 | **done** — kanban dispatches `created` / `done` / `undone` with the deadline in `data` |

Steps 2 and 3 went first, so the log is already collecting what the task views need: by the time they are drawn there is history to draw. Step 1 is the whole page and stands alone.

**Time totals group by `span`, everything else counts records.** One session is logged once per view — kanban and pomodoro both describe it — so summing records doubles the day. Tracked time, the average, the per-bucket bars, the rhythm and the streak all fold records back to their span first, taking the longest duration for the span since the calendar's copy is clipped to its meeting. *By plugin* stays per record, because that is the question. *By task* counts only records carrying a `ref`, or the pomodoro's own preset name outranks every real task.

`build_snapshot` returns one dict for the whole page; the page asks once per range change and once per `changed`. Aggregation walks the log twice — once for spans, once for events — and nothing else, so a year of records is still a single pass over a few thousand rows.
