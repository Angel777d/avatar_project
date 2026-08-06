from datetime import datetime, timedelta
from typing import Optional

from avatar_api import Entity, Env, System, events
from avatar_api.components import TimerEC


class TimerSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)

	async def start(self):
		self.add_listener(events.REQUEST_TIMER_START, self.__on_start)
		self.add_listener(events.REQUEST_TIMER_CANCEL, self.__on_cancel)

	async def _update(self, delta_time: float):
		now = datetime.now()
		for entity in self.env.data_storage.get_collection(TimerEC).entities:
			timer = entity.get_component(TimerEC)
			if timer.deadline() > now:
				continue
			name = timer.name
			self.env.data_storage.remove_entity(entity)
			await self.env.event_bus.dispatch_async(events.ACTION_TIMER_COMPLETE, name)

	def __find(self, name: str) -> Optional[Entity]:
		return self.env.data_storage.get_collection(TimerEC).find(TimerEC.make_hash(name))

	def __remove(self, name: str) -> bool:
		entity = self.__find(name)
		if entity is None:
			return False
		self.env.data_storage.remove_entity(entity)
		return True

	async def __on_start(self, name: str, started: datetime, duration: timedelta):
		if not name:
			return
		self.__remove(name)
		entity = self.env.data_storage.create_entity()
		entity.add_component(TimerEC(name, started, duration))

	async def __on_cancel(self, name: str):
		self.__remove(name)
