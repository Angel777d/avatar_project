import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

PAGE = Path(__file__).resolve().parent / "manager.html"

EVENT_OPEN = "request.manager.open"
EVENT_TOGGLE = "request.manager.toggle"
EVENT_APPLY = "request.manager.apply"
EVENT_REVERT = "request.manager.revert"
EVENT_REFRESH = "request.manager.refresh"
EVENT_REGISTRY_ADD = "request.manager.registry.add"
EVENT_REGISTRY_REMOVE = "request.manager.registry.remove"


class Manager(QObject):
	changed = Signal()

	def __init__(self, system):
		super().__init__()
		self.__system = system

	@Slot(result=str)
	def snapshot(self) -> str:
		return json.dumps(self.__system.snapshot())

	@Slot(str, bool)
	def toggle(self, name: str, wanted: bool):
		self.__system.env.event_bus.dispatch(EVENT_TOGGLE, name, wanted)

	@Slot()
	def apply(self):
		self.__system.env.event_bus.dispatch(EVENT_APPLY)

	@Slot()
	def revert(self):
		self.__system.env.event_bus.dispatch(EVENT_REVERT)

	@Slot()
	def refresh(self):
		self.__system.env.event_bus.dispatch(EVENT_REFRESH)

	@Slot(str, str)
	def add_registry(self, name: str, location: str):
		self.__system.env.event_bus.dispatch(EVENT_REGISTRY_ADD, name, location)

	@Slot(str)
	def remove_registry(self, name: str):
		self.__system.env.event_bus.dispatch(EVENT_REGISTRY_REMOVE, name)
