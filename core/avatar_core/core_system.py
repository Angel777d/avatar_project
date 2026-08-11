from avatar_api import Env, System, events
from avatar_api.components import (
	ColorEC,
	DateEC,
	DurationEC,
	NoteEC,
	NotificationEC,
	StaticIdEC,
	TagEC,
	TagNameEC,
)
from avatar_api.menu import add_menu_item

CLOSE_ITEM = "Close"

STORED_TYPES = (
	StaticIdEC, NoteEC, TagEC, TagNameEC, ColorEC, DateEC, DurationEC, NotificationEC)


class CoreSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)

	async def start(self):
		self.env.registry.register_all(STORED_TYPES)
		add_menu_item(self.env.data_storage, CLOSE_ITEM, events.REQUEST_APP_CLOSE)
		self.add_listener(events.REQUEST_APP_CLOSE, self.__on_close)

	async def __on_close(self):
		if self.env.close_event:
			self.env.close_event.set()
