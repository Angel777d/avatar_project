from typing import List

from angelovich.core.DataStorage import DataStorage, Entity

from avatar_api.components import MenuItemEC


def add_menu_item(data_storage: DataStorage, name: str, event: str) -> Entity:
	entity = data_storage.create_entity()
	entity.add_component(MenuItemEC(name, event))
	return entity


def menu_items(data_storage: DataStorage) -> List[MenuItemEC]:
	return [entity.get_component(MenuItemEC) for entity in data_storage.get_collection(MenuItemEC)]
