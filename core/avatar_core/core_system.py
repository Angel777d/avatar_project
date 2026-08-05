from avatar_api import Env, System, events
from avatar_api.menu import add_menu_item

CLOSE_ITEM = "Close"


class CoreSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)

	async def start(self):
		add_menu_item(self.env.data_storage, CLOSE_ITEM, events.REQUEST_APP_CLOSE)
		self.add_listener(events.REQUEST_APP_CLOSE, self.__on_close)

	async def __on_close(self):
		if self.env.close_event:
			self.env.close_event.set()
