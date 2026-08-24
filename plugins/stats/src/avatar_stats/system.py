import json
from datetime import datetime, timedelta
from typing import Optional

from avatar_api import Entity, Env, System, events
from avatar_api.components import NotificationEC, StaticIdEC
from avatar_api.menu import add_menu_item
from avatar_api.timelog import (
	DATA,
	DURATION,
	EVENT,
	LABEL,
	REF,
	SOURCE,
	SPAN,
	STARTED,
	TAGS,
	TYPE,
	WHEN,
	log_data,
	log_time,
	new_span,
)
from avatar_ui.components import RenderDirtyEC, TabEC, TabViewEC

from avatar_stats.components import DEFAULT_RANGE, LogEntryEC, LogEventEC, StopwatchEC
from avatar_stats.export import write_csv
from avatar_stats.summary import build_snapshot
from avatar_stats.window import (
	CHANNEL,
	EVENT_ADD,
	EVENT_EXPORT,
	EVENT_FORGET,
	EVENT_OPEN,
	EVENT_RANGE,
	EVENT_START,
	EVENT_STOP,
	METHODS,
	PAGE,
	WINDOW,
)

MENU_ITEM = "Open statistics"
PAGE_TITLE = "Time"

TYPE_NAME = "stats"
SOURCE_MANUAL = "manual"
UNKNOWN = "unknown"

MIN_SECONDS = 1
MAX_MINUTES = 24 * 60


class StatsSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__entity: Optional[Entity] = None
		self.__days: int = DEFAULT_RANGE
		self.__since: str = ""
		self.__until: str = ""

	async def start(self):
		self.env.registry.register(LogEntryEC, "log_entry")
		self.env.registry.register(LogEventEC, "log_event")

		add_menu_item(self.env.data_storage, MENU_ITEM, EVENT_OPEN)

		self.add_listener(EVENT_OPEN, self.__on_open)
		self.add_listener(EVENT_START, self.__on_start)
		self.add_listener(EVENT_STOP, self.__on_stop)
		self.add_listener(EVENT_ADD, self.__on_add)
		self.add_listener(EVENT_FORGET, self.__on_forget)
		self.add_listener(EVENT_EXPORT, self.__on_export)
		self.add_listener(EVENT_RANGE, self.__on_range)
		self.add_listener(events.ACTION_STORAGE_RESTORED, self.__on_restored)
		self.add_listener(events.ACTION_LOG_DATA, self.__on_data)
		self.add_listener(events.ACTION_LOG_EVENT, self.__on_event)
		self.add_listener(events.REQUEST_APP_CLOSE, self.__on_app_close)

		self.__register()

	async def stop(self):
		await super().stop()

	async def _update(self, delta_time: float):
		if self.__running() is not None:
			self.__changed()

	def __register(self):
		self.__entity = self.env.data_storage.create_entity()
		self.__entity.add_component(TabEC(PAGE_TITLE, WINDOW))
		self.__entity.add_component(TabViewEC(PAGE, CHANNEL, self.__snapshot(), METHODS))
		self.__mark_dirty()

	def __snapshot(self) -> str:
		return json.dumps(build_snapshot(self.env.data_storage, self.__days, self.__since, self.__until))

	def __mark_dirty(self):
		if not self.__entity.has_component(RenderDirtyEC):
			self.__entity.add_component(RenderDirtyEC())

	def __changed(self):
		if self.__entity is None:
			return
		self.__entity.get_component(TabViewEC).snapshot = self.__snapshot()
		self.__mark_dirty()

	async def __on_restored(self, restored: int):
		self.__changed()

	async def __on_range(self, days: int = DEFAULT_RANGE, since: str = "", until: str = ""):
		self.__days, self.__since, self.__until = days, since, until
		self.__changed()

	def __running(self) -> Optional[Entity]:
		for entity in self.env.data_storage.get_collection(StopwatchEC):
			return entity
		return None

	def __announce(self, started: datetime, seconds: float, label: str, span: str = ""):
		measured = log_time(self.env.event_bus, started, seconds, SOURCE_MANUAL, span)
		log_data(self.env.event_bus, measured, TYPE_NAME, label)

	def __close(self):
		entity = self.__running()
		if entity is None:
			return

		watch = entity.get_component(StopwatchEC)
		started, seconds, label, span = watch.started, watch.elapsed(), watch.label, watch.span
		self.env.data_storage.remove_entity(entity)
		if seconds >= MIN_SECONDS:
			self.__announce(started, seconds, label, span)
		self.__changed()

	async def __on_open(self):
		self.env.event_bus.dispatch(events.REQUEST_PAGE_SHOW, PAGE_TITLE, WINDOW)

	async def __on_export(self, days: int, since: str, until: str):
		path, written = write_csv(self.env.data_storage, days, since, until)
		self.env.event_bus.dispatch(
			events.REQUEST_NOTIFICATION_SHOW,
			NotificationEC(
				title="Time exported",
				text=f"{written} rows written to {path}" if written else "nothing to export",
				source=TYPE_NAME,
			),
		)

	async def __on_start(self, label: str = ""):
		self.__close()
		entity = self.env.data_storage.create_entity()
		entity.add_component(StopwatchEC(label.strip(), datetime.now(), new_span()))
		self.__changed()

	async def __on_stop(self):
		self.__close()

	async def __on_app_close(self):
		self.__close()

	async def __on_add(self, label: str, minutes: int):
		minutes = max(1, min(int(minutes), MAX_MINUTES)) if minutes else 0
		if not minutes:
			return
		seconds = float(minutes * 60)
		self.__announce(datetime.now() - timedelta(seconds=seconds), seconds, label.strip())
		self.__changed()

	async def __on_forget(self, entry_id: str):
		entity = self.env.data_storage.get_collection(StaticIdEC).find(
			StaticIdEC.make_hash(entry_id))
		if entity is None or not (entity.has_component(LogEntryEC)
		                          or entity.has_component(LogEventEC)):
			return
		self.env.data_storage.remove_entity(entity)
		self.__changed()

	async def __on_event(self, moment: dict):
		verb = str(moment.get(EVENT) or "").strip()
		if not verb:
			return

		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		entity.add_component(LogEventEC(
			when=moment.get(WHEN) or datetime.now(),
			type=moment.get(TYPE) or UNKNOWN,
			event=verb,
			label=moment.get(LABEL, ""),
			ref=moment.get(REF, ""),
			tags=moment.get(TAGS) or (),
			data=moment.get(DATA) or {},
		))
		self.__changed()

	async def __on_data(self, record: dict):
		duration = float(record.get(DURATION) or 0.0)
		if duration <= 0:
			return

		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		entity.add_component(LogEntryEC(
			span=record.get(SPAN, ""),
			started=record.get(STARTED) or datetime.now(),
			duration=duration,
			type=record.get(TYPE) or record.get(SOURCE) or UNKNOWN,
			label=record.get(LABEL, ""),
			ref=record.get(REF, ""),
			source=record.get(SOURCE, ""),
			tags=record.get(TAGS) or (),
			data=record.get(DATA) or {},
		))
		self.__changed()
