import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from avatar_api import DataStorage
from avatar_api.components import DateEC, NoteEC, StaticIdEC
from avatar_api.tags import catalogue, tags_of

from avatar_kanban.components import KanbanColumnEC, KanbanTaskEC

PAGE = Path(__file__).resolve().parent / "board.html"

EVENT_OPEN = "request.kanban.open"
EVENT_MOVE = "request.kanban.move"
EVENT_ADD = "request.kanban.add"
EVENT_DELETE = "request.kanban.delete"
EVENT_DEADLINE = "request.kanban.deadline"
EVENT_EDIT = "request.kanban.edit"
EVENT_COLUMN_MOVE = "request.kanban.column.move"
EVENT_COLUMN_RENAME = "request.kanban.column.rename"
EVENT_COLUMN_PROGRESS = "request.kanban.column.progress"
EVENT_RESET = "request.kanban.reset"
EVENT_CLEAR = "request.kanban.clear"


def ordered_columns(data_storage: DataStorage) -> list:
	entities = list(data_storage.get_collection(KanbanColumnEC))
	entities.sort(key=lambda entity: entity.get_component(KanbanColumnEC).position)
	return entities


def build_snapshot(data_storage: DataStorage) -> dict:
	order = [
		(entity.get_component(StaticIdEC).static_id, entity.get_component(KanbanColumnEC))
		for entity in ordered_columns(data_storage)
	]

	buckets = {column_id: [] for column_id, _ in order}
	for entity in data_storage.get_collection(KanbanTaskEC):
		column = entity.get_component(KanbanTaskEC).column
		if column in buckets:
			buckets[column].append(entity)

	columns = []
	for column_id, column in order:
		entities = sorted(buckets[column_id], key=lambda e: e.get_component(KanbanTaskEC).position)
		cards = []
		for entity in entities:
			note = entity.get_component(NoteEC)
			deadline = entity.get_component(DateEC).value if entity.has_component(DateEC) else None
			cards.append({
				"id": entity.get_component(StaticIdEC).static_id,
				"title": note.title,
				"text": note.text,
				"tags": tags_of(data_storage, entity),
				"created": note.created.strftime("%Y-%m-%d %H:%M"),
				"deadline": deadline.isoformat() if deadline else "",
			})
		columns.append({
			"id": column_id,
			"name": column.name,
			"role": column.role,
			"cards": cards,
		})
	return {"columns": columns, "tags": catalogue(data_storage)}


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

	@Slot(str, str)
	def set_deadline(self, card_id: str, day: str):
		self.__env.event_bus.dispatch(EVENT_DEADLINE, card_id, day)

	@Slot(str, str, str, str)
	def edit_card(self, card_id: str, title: str, text: str, tags: str):
		self.__env.event_bus.dispatch(EVENT_EDIT, card_id, title, text, tags)

	@Slot(str)
	def delete_card(self, card_id: str):
		self.__env.event_bus.dispatch(EVENT_DELETE, card_id)

	@Slot(str, int)
	def move_column(self, column_id: str, position: int):
		self.__env.event_bus.dispatch(EVENT_COLUMN_MOVE, column_id, position)

	@Slot(str, str)
	def rename_column(self, column_id: str, name: str):
		self.__env.event_bus.dispatch(EVENT_COLUMN_RENAME, column_id, name)

	@Slot(str)
	def mark_progress(self, column_id: str):
		self.__env.event_bus.dispatch(EVENT_COLUMN_PROGRESS, column_id)

	@Slot()
	def reset(self):
		self.__env.event_bus.dispatch(EVENT_RESET)

	@Slot()
	def clear(self):
		self.__env.event_bus.dispatch(EVENT_CLEAR)
