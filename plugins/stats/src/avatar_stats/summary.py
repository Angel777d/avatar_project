from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from avatar_api import DataStorage, Entity
from avatar_api.components import NoteEC, StaticIdEC
from avatar_api.timelog import CREATED, DONE, UNDONE

from avatar_stats.components import (
	DAY_BUCKETS,
	DEFAULT_RANGE,
	MAX_ROWS,
	SOURCE_POMODORO,
	STUCK_DAYS,
	ZOMBIE_DAYS,
	LogEntryEC,
	LogEventEC,
	StopwatchEC,
)

HOURS = 24
WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
SETTLED_DAYS = 7


def resolve(data_storage: DataStorage, ref: str, spoken: datetime) -> Optional[Entity]:
	if not ref:
		return None
	entity = data_storage.get_collection(StaticIdEC).find(StaticIdEC.make_hash(ref))
	if entity is None or not entity.has_component(NoteEC):
		return None
	return entity if entity.get_component(NoteEC).created <= spoken + timedelta(seconds=1) else None


def hour_slices(started: datetime, duration: float) -> List[Tuple[datetime, float]]:
	left = float(duration)
	cursor = started
	slices = []
	while left > 0:
		edge = (cursor + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
		taken = min(left, (edge - cursor).total_seconds())
		slices.append((cursor, taken))
		cursor = edge
		left -= taken
	return slices


def ranked(totals: Dict[str, float], keys: Optional[Dict[str, str]] = None) -> List[dict]:
	found = [
		{"name": name, "seconds": int(seconds), "ref": (keys or {}).get(name, "")}
		for name, seconds in totals.items() if seconds
	]
	found.sort(key=lambda item: item["seconds"], reverse=True)
	return found


def spoken_hour(hour: int) -> str:
	if hour == 0:
		return "midnight"
	if hour == 12:
		return "noon"
	return f"{hour % 12 or 12}{'am' if hour < 12 else 'pm'}"


class Window:
	def __init__(self, days: int = DEFAULT_RANGE, since: str = "", until: str = ""):
		self.until = _parse(until) or date.today()
		self.since = _parse(since) or self.until - timedelta(days=max(1, days) - 1)
		if self.since > self.until:
			self.since, self.until = self.until, self.since
		self.days = (self.until - self.since).days + 1
		self.weekly = self.days > DAY_BUCKETS

	def holds(self, moment: datetime) -> bool:
		return self.since <= moment.date() <= self.until

	def bucket(self, day: date) -> str:
		if not self.weekly:
			return day.isoformat()
		return (day - timedelta(days=day.weekday())).isoformat()

	def buckets(self) -> List[str]:
		keys = []
		cursor = self.since
		while cursor <= self.until:
			key = self.bucket(cursor)
			if not keys or keys[-1] != key:
				keys.append(key)
			cursor += timedelta(days=1)
		return keys

	def each_day(self) -> List[date]:
		return [self.since + timedelta(days=step) for step in range(self.days)]


def _parse(value: str) -> Optional[date]:
	try:
		return date.fromisoformat(value) if value else None
	except ValueError:
		return None


def build_snapshot(data_storage: DataStorage,
                   days: int = DEFAULT_RANGE,
                   since: str = "",
                   until: str = "") -> dict:
	window = Window(days, since, until)

	by_task: Dict[str, float] = defaultdict(float)
	task_refs: Dict[str, str] = {}
	by_tag: Dict[str, float] = defaultdict(float)
	by_type: Dict[str, float] = defaultdict(float)

	last_touch: Dict[str, datetime] = {}
	measured: Dict[str, Tuple[datetime, float, str]] = {}
	rows: List[dict] = []

	for entity in data_storage.get_collection(LogEntryEC):
		entry = entity.get_component(LogEntryEC)
		day = entry.started.date()

		if entry.ref:
			seen = last_touch.get(entry.ref)
			if seen is None or entry.started > seen:
				last_touch[entry.ref] = entry.started

		if not window.holds(entry.started):
			continue

		key = entry.span or entity.get_component(StaticIdEC).static_id
		known = measured.get(key)
		if known is None or entry.duration > known[1]:
			measured[key] = (min(entry.started, known[0]) if known else entry.started,
			                 max(entry.duration, known[1] if known else 0.0),
			                 entry.source or known[2] if known else entry.source)

		by_type[entry.type or "unknown"] += entry.duration
		if entry.ref:
			name = entry.label or entry.ref
			by_task[name] += entry.duration
			task_refs[name] = entry.ref
		for tag in entry.tags:
			by_tag[tag] += entry.duration

		rows.append({
			"id": entity.get_component(StaticIdEC).static_id,
			"kind": "span",
			"at": entry.started.isoformat(timespec="seconds"),
			"day": day.isoformat(),
			"time": entry.started.strftime("%H:%M"),
			"seconds": int(entry.duration),
			"type": entry.type,
			"label": entry.label,
			"source": entry.source,
			"tags": entry.tags,
		})

	tracked = 0.0
	by_source: Dict[str, float] = defaultdict(float)
	per_bucket: Dict[str, float] = defaultdict(float)
	rhythm = [[0.0] * HOURS for _ in range(7)]
	active: Dict[str, bool] = {}
	focused: Dict[str, bool] = {}
	finished: Dict[str, bool] = {}

	for started, duration, source in measured.values():
		day = started.date()
		tracked += duration
		by_source[source or "unknown"] += duration
		per_bucket[window.bucket(day)] += duration
		active[day.isoformat()] = True
		if source == SOURCE_POMODORO:
			focused[day.isoformat()] = True
		for at, seconds in hour_slices(started, duration):
			rhythm[int(at.strftime("%w"))][at.hour] += seconds

	created = 0
	done = 0
	undone = 0
	timing = {"early": 0, "on_time": 0, "late": 0, "none": 0}
	per_bucket_done: Dict[str, int] = defaultdict(int)

	born: Dict[str, datetime] = {}
	state: Dict[str, Tuple[datetime, str]] = {}
	titles: Dict[str, str] = {}

	for entity in data_storage.get_collection(LogEventEC):
		moment = entity.get_component(LogEventEC)
		day = moment.when.date()

		if moment.ref:
			titles.setdefault(moment.ref, moment.label)
			if moment.event == CREATED:
				first = born.get(moment.ref)
				if first is None or moment.when < first:
					born[moment.ref] = moment.when
			if moment.event in (DONE, UNDONE):
				known = state.get(moment.ref)
				if known is None or moment.when >= known[0]:
					state[moment.ref] = (moment.when, moment.event)

		if not window.holds(moment.when):
			continue

		if moment.event == CREATED:
			created += 1
		elif moment.event == DONE:
			done += 1
			finished[day.isoformat()] = True
			per_bucket_done[window.bucket(day)] += 1
			timing[_verdict(moment)] += 1
		elif moment.event == UNDONE:
			undone += 1

		rows.append({
			"id": entity.get_component(StaticIdEC).static_id,
			"kind": "moment",
			"at": moment.when.isoformat(timespec="seconds"),
			"day": day.isoformat(),
			"time": moment.when.strftime("%H:%M"),
			"seconds": 0,
			"type": moment.type,
			"label": moment.label,
			"source": moment.event,
			"tags": moment.tags,
		})

	rows.sort(key=lambda row: row["at"], reverse=True)
	settled = max(0, done - undone)

	zombie = []
	stuck = []
	now = datetime.now()
	for ref, first in born.items():
		if state.get(ref, (None, ""))[1] == DONE:
			continue
		entity = resolve(data_storage, ref, first)
		if entity is None:
			continue

		title = entity.get_component(NoteEC).title or titles.get(ref, "")
		touched = last_touch.get(ref)
		if touched is None:
			if (now - first).days >= ZOMBIE_DAYS:
				zombie.append({"ref": ref, "label": title, "days": (now - first).days})
		elif (now - touched).days >= STUCK_DAYS:
			stuck.append({"ref": ref, "label": title, "days": (now - touched).days})

	zombie.sort(key=lambda item: item["days"], reverse=True)
	stuck.sort(key=lambda item: item["days"], reverse=True)

	series = [
		{
			"key": key,
			"seconds": int(per_bucket.get(key, 0.0)),
			"done": per_bucket_done.get(key, 0),
		}
		for key in window.buckets()
	]

	streak = [
		{
			"day": day.isoformat(),
			"activity": bool(active.get(day.isoformat())),
			"focus": bool(focused.get(day.isoformat())),
			"completion": bool(finished.get(day.isoformat())),
		}
		for day in window.each_day()
	]

	worked = len(active)
	running = _stopwatch(data_storage)

	return {
		"range": {
			"days": window.days,
			"since": window.since.isoformat(),
			"until": window.until.isoformat(),
			"weekly": window.weekly,
		},
		"running": running is not None,
		"label": running.label if running is not None else "",
		"elapsed": int(running.elapsed()) if running is not None else 0,
		"totals": {
			"tracked": int(tracked),
			"per_day": int(tracked / window.days) if window.days else 0,
			"per_worked": int(tracked / worked) if worked else 0,
			"worked": worked,
			"created": created,
			"done": settled,
			"rate": int(round(100.0 * settled / created)) if created else 0,
		},
		"series": series,
		"rhythm": {
			"grid": [[int(cell) for cell in row] for row in rhythm],
			"peak": int(max((cell for row in rhythm for cell in row), default=0)),
			"insight": _insight(rhythm),
			"settling": worked < SETTLED_DAYS,
		},
		"by_task": ranked(by_task, task_refs),
		"by_tag": ranked(by_tag),
		"by_type": ranked(by_type),
		"by_source": ranked(by_source),
		"timing": timing,
		"zombie": zombie,
		"stuck": stuck,
		"streak": streak,
		"rows": rows[:MAX_ROWS],
	}


def _verdict(moment: LogEventEC) -> str:
	deadline = _parse(str(moment.data.get("deadline") or ""))
	if deadline is None:
		return "none"
	when = moment.when.date()
	if when < deadline:
		return "early"
	return "on_time" if when == deadline else "late"


def _insight(rhythm: List[List[float]]) -> str:
	peak = 0.0
	best = None
	for weekday, row in enumerate(rhythm):
		for hour, seconds in enumerate(row):
			if seconds > peak:
				peak, best = seconds, (weekday, hour)
	if best is None:
		return ""
	return f"Most tracked time happens on {WEEKDAYS[best[0]]}s around {spoken_hour(best[1])}."


def _stopwatch(data_storage: DataStorage) -> Optional[StopwatchEC]:
	for entity in data_storage.get_collection(StopwatchEC):
		return entity.get_component(StopwatchEC)
	return None
