from typing import List, Optional

from avatar_api import Entity, Env, System, events
from datetime import date

from avatar_api.components import DateEC, NoteEC, StaticIdEC
from avatar_api.menu import add_menu_item

from avatar_kanban.components import DEFAULT_COLUMNS, KanbanColumnEC, KanbanTaskEC
from avatar_kanban.window import (
	EVENT_ADD,
	EVENT_COLUMN_MOVE,
	EVENT_COLUMN_RENAME,
	EVENT_DEADLINE,
	EVENT_DELETE,
	EVENT_MOVE,
	EVENT_OPEN,
	EVENT_RESET,
	PAGE,
	Board,
)

MENU_ITEM = "Open kanban"
PAGE_TITLE = "Kanban"

SEED = (
	("todo", "Pick the UI layer"),
	("todo", "Define plugin API"),
	("doing", "HTML window PoC"),
	("done", "Avatar PoC"),
)


class KanbanSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__board: Optional[Board] = None

	async def start(self):
		self.env.registry.register(KanbanTaskEC, "kanban_task")
		self.env.registry.register(KanbanColumnEC, "kanban_column")

		self.add_listener(events.ACTION_STORAGE_RESTORED, self.__on_restored)

		add_menu_item(self.env.data_storage, MENU_ITEM, EVENT_OPEN)

		self.add_listener(EVENT_OPEN, self.__on_open)
		self.add_listener(EVENT_MOVE, self.__on_move)
		self.add_listener(EVENT_ADD, self.__on_add)
		self.add_listener(EVENT_DELETE, self.__on_delete)
		self.add_listener(EVENT_DEADLINE, self.__on_deadline)
		self.add_listener(EVENT_RESET, self.__on_reset)
		self.add_listener(EVENT_COLUMN_MOVE, self.__on_column_move)
		self.add_listener(EVENT_COLUMN_RENAME, self.__on_column_rename)

		self.__board = Board(self.env)
		await self.env.event_bus.dispatch_async(
			events.REQUEST_PAGE_REGISTER, PAGE_TITLE, PAGE, {"board": self.__board})

	async def stop(self):
		await super().stop()
		self.__board = None

	async def __on_open(self):
		self.env.event_bus.dispatch(events.REQUEST_PAGE_SHOW, PAGE_TITLE)

	async def __on_restored(self, restored: int):
		self.__seed_columns()
		if not len(self.env.data_storage.get_collection(KanbanTaskEC)):
			self.__seed()

	def __seed_columns(self):
		if len(self.env.data_storage.get_collection(KanbanColumnEC)):
			return
		for position, (column_id, name) in enumerate(DEFAULT_COLUMNS):
			entity = self.env.data_storage.create_entity()
			entity.add_component(StaticIdEC(column_id))
			entity.add_component(KanbanColumnEC(name, position))

	def __columns(self) -> List[Entity]:
		entities = list(self.env.data_storage.get_collection(KanbanColumnEC))
		entities.sort(key=lambda entity: entity.get_component(KanbanColumnEC).position)
		return entities

	def __column_ids(self) -> List[str]:
		return [entity.get_component(StaticIdEC).static_id for entity in self.__columns()]

	def __column(self, column_id: str) -> Optional[Entity]:
		return next((entity for entity in self.__columns()
		             if entity.get_component(StaticIdEC).static_id == column_id), None)

	async def __on_column_move(self, column_id: str, position: int):
		moved = self.__column(column_id)
		if moved is None:
			return
		order = [entity for entity in self.__columns() if entity is not moved]
		order.insert(max(0, min(position, len(order))), moved)
		for index, entity in enumerate(order):
			entity.get_component(KanbanColumnEC).position = index
		self.__changed()

	async def __on_column_rename(self, column_id: str, name: str):
		name = name.strip()
		entity = self.__column(column_id)
		if not name or entity is None:
			return
		entity.get_component(KanbanColumnEC).name = name
		self.__changed()

	def __seed(self):
		for column_id, title in SEED:
			self.__create(column_id, title)

	def __create(self, column_id: str, title: str) -> Entity:
		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		entity.add_component(NoteEC(title))
		entity.add_component(KanbanTaskEC(column_id, self.__column_size(column_id)))
		return entity

	def __column_size(self, column_id: str) -> int:
		return len(self.__column_entities(column_id))

	def __column_entities(self, column_id: str, skip: Optional[Entity] = None) -> List[Entity]:
		items = [
			entity for entity in self.env.data_storage.get_collection(KanbanTaskEC)
			if entity.get_component(KanbanTaskEC).column == column_id and entity is not skip
		]
		items.sort(key=lambda entity: entity.get_component(KanbanTaskEC).position)
		return items

	def __find(self, card_id: str) -> Optional[Entity]:
		return self.env.data_storage.get_collection(StaticIdEC).find(StaticIdEC.make_hash(card_id))

	def __reindex(self, column_id: str, moved: Optional[Entity] = None, position: int = 0):
		items = self.__column_entities(column_id, moved)
		if moved is not None:
			items.insert(max(0, min(position, len(items))), moved)
		for index, entity in enumerate(items):
			entity.get_component(KanbanTaskEC).position = index

	def __changed(self):
		if self.__board:
			self.__board.changed.emit()

	def __announce(self):
		self.env.event_bus.dispatch(events.ACTION_STORAGE_CHANGED)

	async def __on_move(self, card_id: str, column_id: str, position: int):
		entity = self.__find(card_id)
		if entity is None or column_id not in self.__column_ids():
			return
		task = entity.get_component(KanbanTaskEC)
		source = task.column
		task.column = column_id
		self.__reindex(column_id, entity, position)
		if source != column_id:
			self.__reindex(source)
		self.__changed()

	async def __on_add(self, column_id: str, title: str):
		title = title.strip()
		if not title or column_id not in self.__column_ids():
			return
		self.__create(column_id, title)
		self.__changed()

	async def __on_delete(self, card_id: str):
		entity = self.__find(card_id)
		if entity is None:
			return
		column_id = entity.get_component(KanbanTaskEC).column
		dated = entity.has_component(DateEC)
		self.env.data_storage.remove_entity(entity)
		self.__reindex(column_id)
		self.__changed()
		if dated:
			self.__announce()

	async def __on_deadline(self, card_id: str, day: str):
		entity = self.__find(card_id)
		if entity is None or not entity.has_component(KanbanTaskEC):
			return

		if not day:
			if entity.has_component(DateEC):
				entity.remove_component(DateEC)
			self.__changed()
			self.__announce()
			return

		try:
			value = date.fromisoformat(day)
		except ValueError:
			return

		if entity.has_component(DateEC):
			entity.get_component(DateEC).value = value
		else:
			entity.add_component(DateEC(value))
		self.__changed()
		self.__announce()

	async def __on_reset(self):
		for entity in self.env.data_storage.get_collection(KanbanTaskEC).entities:
			self.env.data_storage.remove_entity(entity)
		self.__seed()
		self.__changed()
		self.__announce()
