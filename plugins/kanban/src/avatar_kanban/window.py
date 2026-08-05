import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from avatar_api import DataStorage
from avatar_api.components import NoteEC, StaticIdEC

from avatar_kanban.components import COLUMNS, KanbanTaskEC

PAGE = Path(__file__).resolve().parent / "board.html"

EVENT_OPEN = "request.kanban.open"
EVENT_MOVE = "request.kanban.move"
EVENT_ADD = "request.kanban.add"
EVENT_DELETE = "request.kanban.delete"
EVENT_RESET = "request.kanban.reset"


def build_snapshot(data_storage: DataStorage) -> dict:
	buckets = {column_id: [] for column_id, _ in COLUMNS}
	for entity in data_storage.get_collection(KanbanTaskEC):
		column = entity.get_component(KanbanTaskEC).column
		if column in buckets:
			buckets[column].append(entity)

	columns = []
	for column_id, name in COLUMNS:
		entities = sorted(buckets[column_id], key=lambda e: e.get_component(KanbanTaskEC).position)
		cards = []
		for entity in entities:
			note = entity.get_component(NoteEC)
			cards.append({
				"id": entity.get_component(StaticIdEC).static_id,
				"title": note.title,
				"created": note.created.strftime("%Y-%m-%d %H:%M"),
			})
		columns.append({"id": column_id, "name": name, "cards": cards})
	return {"columns": columns}


class Board(QObject):
	changed = Signal()

	def __init__(self, env):
		super().__init__()
		self.__env = env

	@Slot(result=str)
	def snapshot(self) -> str:
		return json.dumps(build_snapshot(self.__env.data_storage))

	@Slot(str, str, int)
	def move_card(self, card_id: str, column_id: str, position: int):
		self.__env.event_bus.dispatch(EVENT_MOVE, card_id, column_id, position)

	@Slot(str, str)
	def add_card(self, column_id: str, title: str):
		self.__env.event_bus.dispatch(EVENT_ADD, column_id, title)

	@Slot(str)
	def delete_card(self, card_id: str):
		self.__env.event_bus.dispatch(EVENT_DELETE, card_id)

	@Slot()
	def reset(self):
		self.__env.event_bus.dispatch(EVENT_RESET)
