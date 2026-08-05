from typing import List, Optional

from avatar_api import Entity, Env, System
from avatar_api.components import DateEC, NoteEC, StaticIdEC
from avatar_api.menu import add_menu_item
from avatar_ui.window import HtmlWindow

from avatar_kanban.components import COLUMNS, KanbanTaskEC
from avatar_kanban.window import (
	EVENT_ADD,
	EVENT_DELETE,
	EVENT_MOVE,
	EVENT_OPEN,
	EVENT_RESET,
	PAGE,
	Board,
)

MENU_ITEM = "Open kanban"

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
		self.__window: Optional[HtmlWindow] = None

	async def start(self):
		self.__seed()

		add_menu_item(self.env.data_storage, MENU_ITEM, EVENT_OPEN)

		self.add_listener(EVENT_OPEN, self.__on_open)
		self.add_listener(EVENT_MOVE, self.__on_move)
		self.add_listener(EVENT_ADD, self.__on_add)
		self.add_listener(EVENT_DELETE, self.__on_delete)
		self.add_listener(EVENT_RESET, self.__on_reset)

	async def stop(self):
		await super().stop()
		if self.__window:
			self.__window.close()
			self.__window = None
		self.__board = None

	def __open(self):
		if self.__window is None:
			self.__board = Board(self.env)
			self.__window = HtmlWindow("Kanban", PAGE, {"board": self.__board})
			self.add_task(self.__window.load())
		self.__window.show()
		self.__window.raise_()
		self.__window.activateWindow()

	async def __on_open(self):
		self.__open()

	def __seed(self):
		for column_id, title in SEED:
			self.__create(column_id, title)

	def __create(self, column_id: str, title: str) -> Entity:
		entity = self.env.data_storage.create_entity()
		entity.add_component(StaticIdEC())
		entity.add_component(NoteEC(title))
		entity.add_component(DateEC())
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

	async def __on_move(self, card_id: str, column_id: str, position: int):
		entity = self.__find(card_id)
		if entity is None or column_id not in dict(COLUMNS):
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
		if not title or column_id not in dict(COLUMNS):
			return
		self.__create(column_id, title)
		self.__changed()

	async def __on_delete(self, card_id: str):
		entity = self.__find(card_id)
		if entity is None:
			return
		column_id = entity.get_component(KanbanTaskEC).column
		self.env.data_storage.remove_entity(entity)
		self.__reindex(column_id)
		self.__changed()

	async def __on_reset(self):
		for entity in self.env.data_storage.get_collection(KanbanTaskEC).entities:
			self.env.data_storage.remove_entity(entity)
		self.__seed()
		self.__changed()
