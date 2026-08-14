import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from avatar_stats.components import DEFAULT_RANGE
from avatar_stats.summary import build_snapshot

PAGE = Path(__file__).resolve().parent / "time.html"
WINDOW = "Statistics"

EVENT_OPEN = "request.stats.open"
EVENT_START = "request.stats.start"
EVENT_STOP = "request.stats.stop"
EVENT_ADD = "request.stats.add"
EVENT_FORGET = "request.stats.forget"
EVENT_EXPORT = "request.stats.export"


class StatsBridge(QObject):
	changed = Signal()

	def __init__(self, env):
		super().__init__()
		self.__env = env

	@Slot(int, str, str, result=str)
	def snapshot(self, days: int = DEFAULT_RANGE, since: str = "", until: str = "") -> str:
		return json.dumps(build_snapshot(self.__env.data_storage, days, since, until))

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

	@Slot(int, str, str)
	def export(self, days: int = DEFAULT_RANGE, since: str = "", until: str = ""):
		self.__env.event_bus.dispatch(EVENT_EXPORT, days, since, until)
