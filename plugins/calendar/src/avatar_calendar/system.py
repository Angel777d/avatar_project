from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple

from avatar_api import Entity, Env, System, events
from avatar_api.components import DateEC, NoteEC, StaticIdEC
from avatar_api.menu import add_menu_item
from avatar_api.tags import apply_tags, names_from, tags_of
from avatar_api.timelog import DURATION, SOURCE, SPAN, STARTED, log_data, measure

from avatar_calendar.components import CalendarNoteEC
from avatar_calendar.window import (
	EVENT_ADD,
	EVENT_DELETE,
	EVENT_EDIT,
	EVENT_OPEN,
	PAGE,
	CalendarBridge,
)

MENU_ITEM = "Open calendar"
PAGE_TITLE = "Calendar"
TYPE_NAME = "calendar"
MIN_LOGGED = 1.0


def parse_time(value: str) -> Optional[time]:
	if not value:
		return None
	try:
		return time.fromisoformat(value)
	except ValueError:
		return None


class CalendarSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__bridge: Optional[CalendarBridge] = None

	async def start(self):
		self.env.registry.register(CalendarNoteEC, "calendar_note")

		add_menu_item(self.env.data_storage, MENU_ITEM, EVENT_OPEN)

		self.add_listener(EVENT_OPEN, self.__on_open)
		self.add_listener(EVENT_ADD, self.__on_add)
		self.add_listener(EVENT_DELETE, self.__on_delete)
		self.add_listener(EVENT_EDIT, self.__on_edit)
		self.add_listener(events.ACTION_STORAGE_CHANGED, self.__on_storage_changed)
		self.add_listener(events.REQUEST_LOG_TIME, self.__on_log_time)

		self.__bridge = CalendarBridge(self.env)
		await self.env.event_bus.dispatch_async(
			events.REQUEST_PAGE_REGISTER, PAGE_TITLE, PAGE, {"calendar": self.__bridge})

	async def stop(self):
		await super().stop()
		self.__bridge = None

	def __changed(self):
		if self.__bridge:
			self.__bridge.changed.emit()

	def __find(self, note_id: str) -> Optional[Entity]:
		entity = self.env.data_storage.get_collection(StaticIdEC).find(StaticIdEC.make_hash(note_id))
		if entity is None or not entity.has_component(CalendarNoteEC):
			return None
		return entity

	async def __on_storage_changed(self):
		self.__changed()

	def __overlap(self, entity: Entity, begins: datetime, ends: datetime) -> Tuple[float, datetime]:
		entry = entity.get_component(CalendarNoteEC)
		if entry.begin is None or entry.end is None:
			return 0.0, begins

		day = entity.get_component(DateEC).value
		opens = datetime.combine(day, entry.begin)
		closes = datetime.combine(day, entry.end)
		start = max(opens, begins)
		stop = min(closes, ends)
		return max(0.0, (stop - start).total_seconds()), start

	async def __on_log_time(self, measured: dict):
		begins = measured.get(STARTED)
		seconds = float(measured.get(DURATION) or 0.0)
		if begins is None or seconds <= 0:
			return

		ends = begins + timedelta(seconds=seconds)
		best: Optional[Entity] = None
		shared = MIN_LOGGED
		start = begins

		for entity in self.env.data_storage.get_collection(CalendarNoteEC):
			if not entity.has_component(DateEC) or not entity.has_component(NoteEC):
				continue
			found, opened = self.__overlap(entity, begins, ends)
			if found >= shared:
				best, shared, start = entity, found, opened

		if best is None:
			return

		log_data(
			self.env.event_bus,
			measure(start, shared, measured.get(SOURCE, ""), measured.get(SPAN, "")),
			TYPE_NAME,
			best.get_component(NoteEC).title,
			ref=best.get_component(StaticIdEC).static_id,
			tags=[tag["name"] for tag in tags_of(self.env.data_storage, best)],
		)

	async def __on_open(self):
		self.env.event_bus.dispatch(events.REQUEST_PAGE_SHOW, PAGE_TITLE)

	async def __on_add(self, day: str, title: str):
		title = title.strip()
		if not title:
			return
		try:
			value = date.fromisoformat(day)
		except ValueError:
			return

		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		entity.add_component(NoteEC(title))
		entity.add_component(DateEC(value))
		entity.add_component(CalendarNoteEC())
		self.__changed()

	async def __on_edit(self, note_id: str, title: str, text: str,
	                    begin: str, end: str, tags: str = ""):
		entity = self.__find(note_id)
		if entity is None:
			return
		title = title.strip()
		if not title:
			return

		apply_tags(self.env.data_storage, entity, names_from(tags))
		note = entity.get_component(NoteEC)
		note.title = title
		note.text = text
		note.touch()

		entry = entity.get_component(CalendarNoteEC)
		entry.begin = parse_time(begin)
		entry.end = parse_time(end)
		if entry.begin and entry.end and entry.end < entry.begin:
			entry.begin, entry.end = entry.end, entry.begin

		self.__changed()

	async def __on_delete(self, note_id: str):
		entity = self.__find(note_id)
		if entity is None:
			return
		self.env.data_storage.remove_entity(entity)
		self.__changed()
