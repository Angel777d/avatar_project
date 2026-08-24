import json
from datetime import date, datetime, timedelta
from typing import List, Optional

from avatar_api import Entity, Env, System, events
from avatar_api.components import NotificationEC, StaticIdEC, TimerEC
from avatar_api.menu import add_menu_item
from avatar_api.timelog import log_data, log_time, measure
from avatar_ui.components import RenderDirtyEC, TabEC, TabViewEC

from avatar_pomodoro.components import (
	DEFAULT_NAME,
	PomodoroChoiceEC,
	PomodoroLogEC,
	PomodoroSettingsEC,
)
from avatar_pomodoro.window import (
	ACTION_PHASE_CHANGED,
	CHANNEL,
	EVENT_OPEN,
	EVENT_PAUSE,
	EVENT_PRESET_DELETE,
	EVENT_PRESET_SAVE,
	EVENT_RESET,
	EVENT_SELECT,
	EVENT_SKIP,
	EVENT_START,
	METHODS,
	PAGE,
)

MENU_ITEM = "Open pomodoro"
PAGE_TITLE = "Pomodoro"
SOURCE = "pomodoro"
TIMER = "pomodoro"

PHASE_IDLE = "idle"
PHASE_WORK = "work"
PHASE_BREAK = "break"

MIN_SECONDS = 1
MAX_SECONDS = 24 * 60 * 60
MIN_LOGGED = 1.0

LABELS = {
	PHASE_IDLE: "Ready",
	PHASE_WORK: "Focus",
	PHASE_BREAK: "Break",
}


class PomodoroSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__entity: Optional[Entity] = None
		self.__chain: Optional[PomodoroSettingsEC] = None
		self.__phase = PHASE_IDLE
		self.__total = 0.0
		self.__paused = 0.0
		self.__cycle = 0
		self.__sequence = 0
		self.__segment: Optional[datetime] = None

	async def start(self):
		self.env.registry.register(PomodoroSettingsEC, "pomodoro_settings")
		self.env.registry.register(PomodoroChoiceEC, "pomodoro_choice")
		self.env.registry.register(PomodoroLogEC, "pomodoro_log")

		self.add_listener(events.ACTION_STORAGE_RESTORED, self.__on_restored)

		add_menu_item(self.env.data_storage, MENU_ITEM, EVENT_OPEN)

		self.add_listener(EVENT_OPEN, self.__on_open)
		self.add_listener(EVENT_START, self.__on_start)
		self.add_listener(EVENT_PAUSE, self.__on_pause)
		self.add_listener(EVENT_RESET, self.__on_reset)
		self.add_listener(EVENT_SKIP, self.__on_skip)
		self.add_listener(EVENT_SELECT, self.__on_select)
		self.add_listener(EVENT_PRESET_SAVE, self.__on_preset_save)
		self.add_listener(EVENT_PRESET_DELETE, self.__on_preset_delete)
		self.add_listener(events.ACTION_TIMER_COMPLETE, self.__on_timer_complete)
		self.add_listener(events.REQUEST_APP_CLOSE, self.__on_app_close)

		self.__register()

	async def stop(self):
		await super().stop()

	async def _update(self, delta_time: float):
		if self.__timer() is not None:
			self.__changed()

	def __register(self):
		self.__entity = self.env.data_storage.create_entity()
		self.__entity.add_component(TabEC(PAGE_TITLE))
		self.__entity.add_component(TabViewEC(PAGE, CHANNEL, json.dumps(self.snapshot()), METHODS))
		self.__mark_dirty()

	def __mark_dirty(self):
		if not self.__entity.has_component(RenderDirtyEC):
			self.__entity.add_component(RenderDirtyEC())

	def snapshot(self) -> dict:
		timer = self.__timer()
		remaining = timer.remaining() if timer is not None else self.__paused
		active = self.active()
		chosen = self.settings()
		return {
			"phase": self.__phase,
			"label": LABELS[self.__phase],
			"running": timer is not None,
			"remaining": int(remaining + 0.5),
			"total": int(self.__total),
			"done_today": self.__done_today(),
			"focus_today": int(self.log().focus(date.today())),
			"done_total": self.log().total,
			"streak": self.__cycle,
			"sequence": self.__sequence,
			"sequences": int(active.sequences),
			"preset": active.name,
			"next": chosen.name if self.__chain is not None else "",
			"selected": self.selected().get_component(StaticIdEC).static_id,
			"presets": [
				{
					"id": entity.get_component(StaticIdEC).static_id,
					"name": entity.get_component(PomodoroSettingsEC).name,
				}
				for entity in self.presets()
			],
			"settings": self.__settings_view(),
		}

	def presets(self) -> List[Entity]:
		found = list(self.env.data_storage.get_collection(PomodoroSettingsEC))
		found.sort(key=lambda entity: entity.get_component(PomodoroSettingsEC).name.lower())
		return found

	def __preset(self, preset_id: str) -> Optional[Entity]:
		entity = self.env.data_storage.get_collection(StaticIdEC).find(
			StaticIdEC.make_hash(preset_id))
		if entity is None or not entity.has_component(PomodoroSettingsEC):
			return None
		return entity

	def __choice(self) -> PomodoroChoiceEC:
		for entity in self.env.data_storage.get_collection(PomodoroChoiceEC):
			return entity.get_component(PomodoroChoiceEC)

		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		choice = PomodoroChoiceEC()
		entity.add_component(choice)
		return choice

	def __create_preset(self, name: str = DEFAULT_NAME) -> Entity:
		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		entity.add_component(PomodoroSettingsEC(name))
		return entity

	def selected(self) -> Entity:
		choice = self.__choice()
		entity = self.__preset(choice.preset) if choice.preset else None
		if entity is None:
			known = self.presets()
			entity = known[0] if known else self.__create_preset()
			choice.preset = entity.get_component(StaticIdEC).static_id
		return entity

	def settings(self) -> PomodoroSettingsEC:
		return self.selected().get_component(PomodoroSettingsEC)

	def active(self) -> PomodoroSettingsEC:
		return self.__chain if self.__chain is not None else self.settings()

	def __begin_chain(self) -> None:
		chosen = self.settings()
		self.__chain = PomodoroSettingsEC(
			chosen.name, chosen.work, chosen.short_break, chosen.long_break,
			chosen.long_break_every, chosen.sequences)

	def __settings_view(self) -> dict:
		settings = self.settings()
		return {
			"name": settings.name,
			"work": int(settings.work),
			"short_break": int(settings.short_break),
			"long_break": int(settings.long_break),
			"long_break_every": int(settings.long_break_every),
			"sequences": int(settings.sequences),
		}

	async def __on_restored(self, restored: int):
		if not self.presets():
			self.__create_preset()
		self.selected()
		self.__idle()
		self.__changed()

	def __idle(self):
		self.__phase = PHASE_IDLE
		self.__chain = None
		self.__segment = None
		self.__total = float(self.settings().work)
		self.__paused = self.__total

	def log(self) -> PomodoroLogEC:
		for entity in self.env.data_storage.get_collection(PomodoroLogEC):
			return entity.get_component(PomodoroLogEC)

		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		log = PomodoroLogEC()
		entity.add_component(log)
		return log

	def __timer(self) -> Optional[TimerEC]:
		entity = self.env.data_storage.get_collection(TimerEC).find(TimerEC.make_hash(TIMER))
		return entity.get_component(TimerEC) if entity is not None else None

	def __done_today(self) -> int:
		return self.log().count(date.today())

	def __changed(self):
		if self.__entity is None:
			return
		self.__entity.get_component(TabViewEC).snapshot = json.dumps(self.snapshot())
		self.__mark_dirty()

	async def __run(self, seconds: float):
		self.__segment = datetime.now()
		await self.env.event_bus.dispatch_async(
			events.REQUEST_TIMER_START, TIMER, datetime.now(), timedelta(seconds=seconds)
		)

	def __log_segment(self):
		started, self.__segment = self.__segment, None
		if started is None:
			return

		seconds = (datetime.now() - started).total_seconds()
		if seconds < MIN_LOGGED:
			return

		settings = self.active()
		if self.__phase == PHASE_WORK:
			measured = log_time(self.env.event_bus, started, seconds, SOURCE)
		else:
			measured = measure(started, seconds, SOURCE)

		log_data(self.env.event_bus, measured, SOURCE, settings.name,
		         data={"phase": self.__phase, "sequence": self.__sequence + 1})

	async def __cancel(self):
		await self.env.event_bus.dispatch_async(events.REQUEST_TIMER_CANCEL, TIMER)

	async def __enter(self, phase: str, seconds: float):
		self.__phase = phase
		self.__total = float(seconds)
		self.__paused = float(seconds)
		await self.__run(seconds)
		self.env.event_bus.dispatch(ACTION_PHASE_CHANGED, phase)
		self.__changed()

	def __notify(self, title: str, text: str):
		self.env.event_bus.dispatch(
			events.REQUEST_NOTIFICATION_SHOW,
			NotificationEC(title=title, text=text, source=SOURCE),
		)

	def __record(self):
		self.log().add(date.today(), float(self.active().work))

	async def __finish(self):
		self.__log_segment()
		if self.__phase == PHASE_WORK:
			self.__record()
			self.__cycle += 1
			settings = self.active()
			long_break = self.__cycle % max(1, settings.long_break_every) == 0
			seconds = settings.long_break if long_break else settings.short_break
			await self.__enter(PHASE_BREAK, seconds)
			self.__notify("Pomodoro done", f"Take a {int(seconds // 60)} minute break.")
		else:
			settings = self.active()
			self.__sequence += 1
			if self.__sequence < max(1, settings.sequences):
				await self.__enter(PHASE_WORK, settings.work)
				self.__notify("Break over", f"Starting {self.__sequence + 1} of {int(settings.sequences)}.")
				return
			self.__sequence = 0
			self.__idle()
			self.env.event_bus.dispatch(ACTION_PHASE_CHANGED, PHASE_IDLE)
			self.__changed()
			self.__notify("Set complete", f"{int(settings.sequences)} done in a row. Take a rest.")

	async def __on_timer_complete(self, name: str):
		if name != TIMER:
			return
		await self.__finish()

	async def __on_open(self):
		self.env.event_bus.dispatch(events.REQUEST_PAGE_SHOW, PAGE_TITLE)

	async def __on_app_close(self):
		self.__log_segment()

	async def __on_start(self):
		if self.__timer() is not None:
			return
		if self.__phase == PHASE_IDLE:
			self.__begin_chain()
			await self.__enter(PHASE_WORK, self.active().work)
			return
		await self.__run(self.__paused)
		self.__changed()

	async def __on_pause(self):
		timer = self.__timer()
		if timer is None:
			return
		self.__paused = timer.remaining()
		await self.__cancel()
		self.__log_segment()
		self.__changed()

	async def __on_reset(self):
		await self.__cancel()
		self.__log_segment()
		self.__cycle = 0
		self.__sequence = 0
		self.__idle()
		self.__changed()

	async def __on_select(self, preset_id: str):
		if self.__preset(preset_id) is None:
			return
		self.__choice().preset = preset_id
		self.__settle()

	async def __on_preset_save(self, preset_id: str, name: str, work: int, short_break: int,
	                           long_break: int, long_break_every: int, sequences: int):
		entity = self.__preset(preset_id)
		if entity is None:
			entity = self.__create_preset(name.strip() or DEFAULT_NAME)
			self.__choice().preset = entity.get_component(StaticIdEC).static_id

		settings = entity.get_component(PomodoroSettingsEC)
		settings.name = name.strip() or settings.name
		settings.work = _clamp(work, settings.work)
		settings.short_break = _clamp(short_break, settings.short_break)
		settings.long_break = _clamp(long_break, settings.long_break)
		settings.long_break_every = max(1, int(long_break_every)) if long_break_every else settings.long_break_every
		settings.sequences = max(1, int(sequences)) if sequences else settings.sequences
		self.__settle()

	async def __on_preset_delete(self, preset_id: str):
		entity = self.__preset(preset_id)
		if entity is None or len(self.presets()) <= 1:
			return
		self.env.data_storage.remove_entity(entity)
		if self.__choice().preset == preset_id:
			self.__choice().preset = ""
			self.selected()
		self.__settle()

	def __settle(self):
		if self.__phase == PHASE_IDLE and self.__timer() is None:
			self.__idle()
		self.__changed()

	async def __on_skip(self):
		if self.__phase == PHASE_IDLE:
			return
		await self.__cancel()
		await self.__finish()


def _clamp(value: float, fallback: float) -> float:
	if not value:
		return fallback
	return float(max(MIN_SECONDS, min(MAX_SECONDS, value)))
