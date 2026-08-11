import calendar
import json
from datetime import date
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, Slot

from avatar_api import DataStorage
from avatar_api.components import DateEC, NoteEC, StaticIdEC

from avatar_calendar.components import CalendarNoteEC

PAGE = Path(__file__).resolve().parent / "month.html"

EVENT_OPEN = "request.calendar.open"
EVENT_ADD = "request.calendar.add"
EVENT_DELETE = "request.calendar.delete"

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def notes_by_day(data_storage: DataStorage) -> dict:
	grouped = {}

	for entity in data_storage.get_collection(DateEC):
		if not entity.has_component(NoteEC):
			continue
		note = entity.get_component(NoteEC)
		mine = entity.has_component(CalendarNoteEC)
		grouped.setdefault(entity.get_component(DateEC).value.isoformat(), []).append({
			"id": entity.get_component(StaticIdEC).static_id,
			"title": note.title,
			"detail": note.created.strftime("%H:%M") if mine else "due",
			"kind": "note" if mine else "deadline",
		})

	for items in grouped.values():
		items.sort(key=lambda item: (item["kind"] != "note", item["title"]))
	return grouped


def shift_month(day: date, offset: int) -> date:
	index = day.year * 12 + day.month - 1 + offset
	year, month = divmod(index, 12)
	if not date.min.year <= year <= date.max.year:
		return day.replace(day=1)
	return date(year, month + 1, 1)


def build_snapshot(data_storage: DataStorage,
                   focus: Optional[date] = None,
                   today: Optional[date] = None) -> dict:
	today = today or date.today()
	focus = focus or today
	weeks: List[List[Optional[dict]]] = []
	for week in calendar.Calendar().monthdatescalendar(focus.year, focus.month):
		cells = []
		for day in week:
			if day.month != focus.month:
				cells.append(None)
			else:
				cells.append({"date": day.isoformat(), "day": day.day, "today": day == today})
		weeks.append(cells)

	return {
		"title": f"{calendar.month_name[focus.month]} {focus.year}",
		"weekdays": list(WEEKDAYS),
		"weeks": weeks,
		"today": today.isoformat(),
		"focus": focus.replace(day=1).isoformat(),
		"notes": notes_by_day(data_storage),
	}


class CalendarBridge(QObject):
	changed = Signal()

	def __init__(self, env):
		super().__init__()
		self.__env = env

	@Slot(result=str)
	def snapshot(self) -> str:
		return self.snapshot_at(0)

	@Slot(int, result=str)
	def snapshot_at(self, offset: int) -> str:
		focus = shift_month(date.today(), offset)
		return json.dumps(build_snapshot(self.__env.data_storage, focus))

	@Slot(str, str)
	def add_note(self, day: str, title: str):
		self.__env.event_bus.dispatch(EVENT_ADD, day, title)

	@Slot(str)
	def delete_note(self, note_id: str):
		self.__env.event_bus.dispatch(EVENT_DELETE, note_id)
