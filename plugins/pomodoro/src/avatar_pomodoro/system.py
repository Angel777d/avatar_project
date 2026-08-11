from datetime import date, datetime, timedelta
from typing import Optional

from avatar_api import Env, System, events
from avatar_api.components import NotificationEC, StaticIdEC, TimerEC
from avatar_api.menu import add_menu_item

from avatar_pomodoro.components import PomodoroLogEC, PomodoroSettingsEC
from avatar_pomodoro.window import (
	ACTION_PHASE_CHANGED,
	EVENT_OPEN,
	EVENT_PAUSE,
	EVENT_RESET,
	EVENT_SETTINGS,
	EVENT_SKIP,
	EVENT_START,
	PAGE,
	PomodoroBridge,
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

LABELS = {
	PHASE_IDLE: "Ready",
	PHASE_WORK: "Focus",
	PHASE_BREAK: "Break",
}


class PomodoroSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__bridge: Optional[PomodoroBridge] = None
		self.__phase = PHASE_IDLE
		self.__total = 0.0
		self.__paused = 0.0
		self.__cycle = 0
		self.__sequence = 0

	async def start(self):
		self.env.registry.register(PomodoroSettingsEC, "pomodoro_settings")
		self.env.registry.register(PomodoroLogEC, "pomodoro_log")

		self.add_listener(events.ACTION_STORAGE_RESTORED, self.__on_restored)

		add_menu_item(self.env.data_storage, MENU_ITEM, EVENT_OPEN)

		self.add_listener(EVENT_OPEN, self.__on_open)
		self.add_listener(EVENT_START, self.__on_start)
		self.add_listener(EVENT_PAUSE, self.__on_pause)
		self.add_listener(EVENT_RESET, self.__on_reset)
		self.add_listener(EVENT_SKIP, self.__on_skip)
		self.add_listener(EVENT_SETTINGS, self.__on_settings)
		self.add_listener(events.ACTION_TIMER_COMPLETE, self.__on_timer_complete)

		self.__bridge = PomodoroBridge(self.env, self.snapshot)
		await self.env.event_bus.dispatch_async(
			events.REQUEST_PAGE_REGISTER, PAGE_TITLE, PAGE, {"pomodoro": self.__bridge})

	async def stop(self):
		await super().stop()
		self.__bridge = None

	async def _update(self, delta_time: float):
		if self.__timer() is not None:
			self.__changed()

	def snapshot(self) -> dict:
		timer = self.__timer()
		remaining = timer.remaining() if timer is not None else self.__paused
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
			"sequences": int(self.settings().sequences),
			"settings": self.__settings_view(),
		}

	def settings(self) -> PomodoroSettingsEC:
		collection = self.env.data_storage.get_collection(PomodoroSettingsEC)
		for entity in collection:
			return entity.get_component(PomodoroSettingsEC)

		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		settings = PomodoroSettingsEC()
		entity.add_component(settings)
		return settings

	def __settings_view(self) -> dict:
		settings = self.settings()
		return {
			"work": int(settings.work),
			"short_break": int(settings.short_break),
			"long_break": int(settings.long_break),
			"long_break_every": int(settings.long_break_every),
			"sequences": int(settings.sequences),
		}

	async def __on_restored(self, restored: int):
		self.__idle()

	def __idle(self):
		self.__phase = PHASE_IDLE
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
		if self.__bridge:
			self.__bridge.changed.emit()

	async def __run(self, seconds: float):
		await self.env.event_bus.dispatch_async(
			events.REQUEST_TIMER_START, TIMER, datetime.now(), timedelta(seconds=seconds)
		)

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
		self.log().add(date.today(), float(self.settings().work))

	async def __finish(self):
		if self.__phase == PHASE_WORK:
			self.__record()
			self.__cycle += 1
			settings = self.settings()
			long_break = self.__cycle % max(1, settings.long_break_every) == 0
			seconds = settings.long_break if long_break else settings.short_break
			await self.__enter(PHASE_BREAK, seconds)
			self.__notify("Pomodoro done", f"Take a {int(seconds // 60)} minute break.")
		else:
			settings = self.settings()
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

	async def __on_start(self):
		if self.__timer() is not None:
			return
		if self.__phase == PHASE_IDLE:
			await self.__enter(PHASE_WORK, self.settings().work)
			return
		await self.__run(self.__paused)
		self.__changed()

	async def __on_pause(self):
		timer = self.__timer()
		if timer is None:
			return
		self.__paused = timer.remaining()
		await self.__cancel()
		self.__changed()

	async def __on_reset(self):
		await self.__cancel()
		self.__cycle = 0
		self.__sequence = 0
		self.__idle()
		self.__changed()

	async def __on_settings(self, work: int, short_break: int, long_break: int,
	                        long_break_every: int, sequences: int):
		settings = self.settings()
		settings.work = _clamp(work, settings.work)
		settings.short_break = _clamp(short_break, settings.short_break)
		settings.long_break = _clamp(long_break, settings.long_break)
		settings.long_break_every = max(1, int(long_break_every)) if long_break_every else settings.long_break_every
		settings.sequences = max(1, int(sequences)) if sequences else settings.sequences
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
