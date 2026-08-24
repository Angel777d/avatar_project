from pathlib import Path
from typing import Dict

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
EVENT_COLUMN_ADD = "request.kanban.column.add"
EVENT_COLUMN_DELETE = "request.kanban.column.delete"
EVENT_COLUMN_MOVE = "request.kanban.column.move"
EVENT_COLUMN_RENAME = "request.kanban.column.rename"
EVENT_RESET = "request.kanban.reset"
EVENT_CLEAR = "request.kanban.clear"

CHANNEL = "board"
METHODS: Dict[str, str] = {
	"move_card": EVENT_MOVE,
	"add_card": EVENT_ADD,
	"set_deadline": EVENT_DEADLINE,
	"edit_card": EVENT_EDIT,
	"delete_card": EVENT_DELETE,
	"move_column": EVENT_COLUMN_MOVE,
	"rename_column": EVENT_COLUMN_RENAME,
	"add_column": EVENT_COLUMN_ADD,
	"delete_column": EVENT_COLUMN_DELETE,
	"reset": EVENT_RESET,
	"clear": EVENT_CLEAR,
}


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
