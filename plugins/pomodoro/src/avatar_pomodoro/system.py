from datetime import date, datetime, timedelta
from typing import Optional

from avatar_api import Env, System, events
from avatar_api.components import (
	DateEC,
	DurationEC,
	NoteEC,
	NotificationEC,
	StaticIdEC,
	TimerEC,
)
from avatar_api.menu import add_menu_item
from avatar_ui.window import HtmlWindow

from avatar_pomodoro.components import PomodoroSessionEC
from avatar_pomodoro.window import (
	ACTION_PHASE_CHANGED,
	EVENT_OPEN,
	EVENT_PAUSE,
	EVENT_RESET,
	EVENT_SKIP,
	EVENT_START,
	PAGE,
	PomodoroBridge,
)

MENU_ITEM = "Open pomodoro"
SOURCE = "pomodoro"
TIMER = "pomodoro"

PHASE_IDLE = "idle"
PHASE_WORK = "work"
PHASE_BREAK = "break"

WORK_S = 25 * 60
SHORT_BREAK_S = 5 * 60
LONG_BREAK_S = 15 * 60
LONG_BREAK_EVERY = 4

LABELS = {
	PHASE_IDLE: "Ready",
	PHASE_WORK: "Focus",
	PHASE_BREAK: "Break",
}


class PomodoroSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__bridge: Optional[PomodoroBridge] = None
		self.__window: Optional[HtmlWindow] = None
		self.__phase = PHASE_IDLE
		self.__total = float(WORK_S)
		self.__paused = float(WORK_S)
		self.__cycle = 0

	async def start(self):
		self.env.registry.register(PomodoroSessionEC, "pomodoro_session")

		add_menu_item(self.env.data_storage, MENU_ITEM, EVENT_OPEN)

		self.add_listener(EVENT_OPEN, self.__on_open)
		self.add_listener(EVENT_START, self.__on_start)
		self.add_listener(EVENT_PAUSE, self.__on_pause)
		self.add_listener(EVENT_RESET, self.__on_reset)
		self.add_listener(EVENT_SKIP, self.__on_skip)
		self.add_listener(events.ACTION_TIMER_COMPLETE, self.__on_timer_complete)

	async def stop(self):
		await super().stop()
		if self.__window:
			self.__window.close()
			self.__window = None
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
		}

	def __timer(self) -> Optional[TimerEC]:
		entity = self.env.data_storage.get_collection(TimerEC).find(TimerEC.make_hash(TIMER))
		return entity.get_component(TimerEC) if entity is not None else None

	def __done_today(self) -> int:
		today = date.today()
		return sum(
			1 for entity in self.env.data_storage.get_collection(PomodoroSessionEC)
			if entity.get_component(DateEC).value == today
		)

	def __changed(self):
		if self.__bridge:
			self.__bridge.changed.emit()

	def __open(self):
		if self.__window is None:
			self.__bridge = PomodoroBridge(self.env, self.snapshot)
			self.__window = HtmlWindow("Pomodoro", PAGE, {"pomodoro": self.__bridge}, size=(380, 380))
			self.add_task(self.__window.load())
		self.__window.show()
		self.__window.raise_()
		self.__window.activateWindow()

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
		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		entity.add_component(NoteEC("Pomodoro"))
		entity.add_component(DateEC(date.today()))
		entity.add_component(DurationEC(timedelta(seconds=WORK_S)))
		entity.add_component(PomodoroSessionEC(PHASE_WORK))

	async def __finish(self):
		if self.__phase == PHASE_WORK:
			self.__record()
			self.__cycle += 1
			long_break = self.__cycle % LONG_BREAK_EVERY == 0
			seconds = LONG_BREAK_S if long_break else SHORT_BREAK_S
			await self.__enter(PHASE_BREAK, seconds)
			self.__notify("Pomodoro done", f"Take a {int(seconds // 60)} minute break.")
		else:
			self.__phase = PHASE_IDLE
			self.__total = float(WORK_S)
			self.__paused = float(WORK_S)
			self.env.event_bus.dispatch(ACTION_PHASE_CHANGED, PHASE_IDLE)
			self.__changed()
			self.__notify("Break over", "Ready for the next one?")

	async def __on_timer_complete(self, name: str):
		if name != TIMER:
			return
		await self.__finish()

	async def __on_open(self):
		self.__open()

	async def __on_start(self):
		if self.__timer() is not None:
			return
		if self.__phase == PHASE_IDLE:
			await self.__enter(PHASE_WORK, WORK_S)
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
		self.__phase = PHASE_IDLE
		self.__total = float(WORK_S)
		self.__paused = float(WORK_S)
		self.__changed()

	async def __on_skip(self):
		if self.__phase == PHASE_IDLE:
			return
		await self.__cancel()
		await self.__finish()
