from typing import List

from angelovich.core.DataStorage import DataStorage, Entity

from avatar_api.action import set_action
from avatar_api.components import MenuItemEC


def add_menu_item(data_storage: DataStorage, name: str, event: str) -> Entity:
	entity = data_storage.create_entity()
	entity.add_component(MenuItemEC(name))
	return set_action(entity, event)


def menu_items(data_storage: DataStorage) -> List[Entity]:
	return list(data_storage.get_collection(MenuItemEC))
