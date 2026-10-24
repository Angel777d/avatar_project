from typing import Optional

from avatar_api import Entity, Env, System
from avatar_api.components import PRIORITY_LOW, CurrentNotificationLevelEC, NotificationLevelEC


class NotificationLevelSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__entity: Optional[Entity] = None

	async def start(self):
		self.__entity = self.env.data_storage.create_entity()
		self.__entity.add_component(CurrentNotificationLevelEC(self.__highest()))

		levels = self.env.data_storage.get_collection(NotificationLevelEC)
		levels.add_listener(levels.EVENT_ADDED, self.__on_added, scope=self)
		levels.add_listener(levels.EVENT_REMOVED, self.__on_removed, scope=self)

	async def stop(self):
		await super().stop()
		self.env.data_storage.get_collection(NotificationLevelEC).remove_all_listeners(self)
		entity, self.__entity = self.__entity, None
		if entity is not None:
			self.env.data_storage.remove_entity(entity)

	def __highest(self) -> int:
		return max(
			(entity.get_component(NotificationLevelEC).level
			 for entity in self.env.data_storage.get_collection(NotificationLevelEC)),
			default=PRIORITY_LOW,
		)

	def __refresh(self):
		if self.__entity is None:
			return
		level = self.__highest()
		if self.__entity.get_component(CurrentNotificationLevelEC).level == level:
			return
		self.__entity.remove_component(CurrentNotificationLevelEC)
		self.__entity.add_component(CurrentNotificationLevelEC(level))

	async def __on_added(self, entity: Entity, component: NotificationLevelEC):
		self.__refresh()

	async def __on_removed(self, entity_id: int):
		self.__refresh()
