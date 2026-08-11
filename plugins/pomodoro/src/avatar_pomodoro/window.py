import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

PAGE = Path(__file__).resolve().parent / "timer.html"

EVENT_OPEN = "request.pomodoro.open"
EVENT_START = "request.pomodoro.start"
EVENT_PAUSE = "request.pomodoro.pause"
EVENT_RESET = "request.pomodoro.reset"
EVENT_SKIP = "request.pomodoro.skip"
EVENT_SELECT = "request.pomodoro.select"
EVENT_PRESET_SAVE = "request.pomodoro.preset.save"
EVENT_PRESET_DELETE = "request.pomodoro.preset.delete"

ACTION_PHASE_CHANGED = "action.pomodoro.phase"


class PomodoroBridge(QObject):
	changed = Signal()

	def __init__(self, env, snapshot):
		super().__init__()
		self.__env = env
		self.__snapshot = snapshot

	@Slot(result=str)
	def snapshot(self) -> str:
		return json.dumps(self.__snapshot())

	@Slot()
	def start(self):
		self.__env.event_bus.dispatch(EVENT_START)

	@Slot()
	def pause(self):
		self.__env.event_bus.dispatch(EVENT_PAUSE)

	@Slot()
	def reset(self):
		self.__env.event_bus.dispatch(EVENT_RESET)

	@Slot()
	def skip(self):
		self.__env.event_bus.dispatch(EVENT_SKIP)

	@Slot(str)
	def select_preset(self, preset_id: str):
		self.__env.event_bus.dispatch(EVENT_SELECT, preset_id)

	@Slot(str)
	def delete_preset(self, preset_id: str):
		self.__env.event_bus.dispatch(EVENT_PRESET_DELETE, preset_id)

	@Slot(str, str, int, int, int, int, int)
	def save_preset(self, preset_id: str, name: str, work: int, short_break: int,
	                long_break: int, long_break_every: int, sequences: int):
		self.__env.event_bus.dispatch(
			EVENT_PRESET_SAVE, preset_id, name, work, short_break,
			long_break, long_break_every, sequences)
