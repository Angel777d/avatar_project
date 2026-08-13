import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Signal, Slot

from avatar_api import DataStorage
from avatar_api.components import StaticIdEC

from avatar_stats.components import DEFAULT_RANGE, MAX_ENTRIES, LogEntryEC, StopwatchEC

PAGE = Path(__file__).resolve().parent / "time.html"

EVENT_OPEN = "request.stats.open"
EVENT_START = "request.stats.start"
EVENT_STOP = "request.stats.stop"
EVENT_ADD = "request.stats.add"
EVENT_FORGET = "request.stats.forget"


def entries(data_storage: DataStorage) -> List:
	found = list(data_storage.get_collection(LogEntryEC))
	found.sort(key=lambda entity: entity.get_component(LogEntryEC).started, reverse=True)
	return found


def stopwatch(data_storage: DataStorage) -> Optional[StopwatchEC]:
	for entity in data_storage.get_collection(StopwatchEC):
		return entity.get_component(StopwatchEC)
	return None


def ranked(totals: Dict[str, float]) -> List[dict]:
	found = [{"name": name, "seconds": int(seconds)} for name, seconds in totals.items() if seconds]
	found.sort(key=lambda item: item["seconds"], reverse=True)
	return found


def build_snapshot(data_storage: DataStorage, days: int = DEFAULT_RANGE) -> dict:
	days = max(1, days)
	today = date.today()
	since = today - timedelta(days=days - 1)

	by_type: Dict[str, float] = defaultdict(float)
	by_label: Dict[str, float] = defaultdict(float)
	by_source: Dict[str, float] = defaultdict(float)
	by_tag: Dict[str, float] = defaultdict(float)
	by_day: Dict[str, float] = defaultdict(float)

	total = 0.0
	today_total = 0.0
	rows = []

	for entity in entries(data_storage):
		entry = entity.get_component(LogEntryEC)
		day = entry.started.date()
		if day == today:
			today_total += entry.duration
		if day < since:
			continue

		total += entry.duration
		by_type[entry.type or "unknown"] += entry.duration
		by_label[entry.label or entry.type or "unknown"] += entry.duration
		by_source[entry.source or "unknown"] += entry.duration
		by_day[day.isoformat()] += entry.duration
		for name in entry.tags:
			by_tag[name] += entry.duration

		if len(rows) < MAX_ENTRIES:
			rows.append({
				"id": entity.get_component(StaticIdEC).static_id,
				"day": day.isoformat(),
				"time": entry.started.strftime("%H:%M"),
				"seconds": int(entry.duration),
				"type": entry.type,
				"label": entry.label,
				"source": entry.source,
				"tags": entry.tags,
			})

	series = []
	for step in range(days):
		day = since + timedelta(days=step)
		series.append({"day": day.isoformat(), "seconds": int(by_day.get(day.isoformat(), 0.0))})

	running = stopwatch(data_storage)
	return {
		"days": days,
		"running": running is not None,
		"label": running.label if running is not None else "",
		"elapsed": int(running.elapsed()) if running is not None else 0,
		"total": int(total),
		"today": int(today_total),
		"series": series,
		"by_type": ranked(by_type),
		"by_label": ranked(by_label),
		"by_source": ranked(by_source),
		"by_tag": ranked(by_tag),
		"entries": rows,
	}


class StatsBridge(QObject):
	changed = Signal()

	def __init__(self, env):
		super().__init__()
		self.__env = env

	@Slot(int, result=str)
	def snapshot(self, days: int) -> str:
		return json.dumps(build_snapshot(self.__env.data_storage, days))

	@Slot(str)
	def start(self, label: str):
		self.__env.event_bus.dispatch(EVENT_START, label)

	@Slot()
	def stop(self):
		self.__env.event_bus.dispatch(EVENT_STOP)

	@Slot(str, int)
	def add(self, label: str, minutes: int):
		self.__env.event_bus.dispatch(EVENT_ADD, label, minutes)

	@Slot(str)
	def forget(self, entry_id: str):
		self.__env.event_bus.dispatch(EVENT_FORGET, entry_id)
