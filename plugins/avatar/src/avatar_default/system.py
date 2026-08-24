import asyncio
import random
import time
from collections import deque
from typing import Deque, Optional

from avatar_api import Entity, Env, System, events
from avatar_api.components import MenuItemEC, NotificationEC, TimerEC
from avatar_api.menu import menu_items

from avatar_ui.avatar_widget import EVENT_CLICKED, EVENT_MOVED
from avatar_ui.components import AvatarViewEC, RenderDirtyEC

SOURCE = "avatar"
SOURCE_CLICK = "avatar.click"

BUBBLE_S = 4.5
IDLE_S = 30.0
TIMER_POLL_S = 0.1

PHRASES = [
	"Still here.",
	"Anything to do?",
	"I like this corner.",
	"Just floating around.",
	"Nice desktop you have.",
	"Poke me if you need me.",
]


class AvatarSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__entity: Optional[Entity] = None
		self.__queue: Deque[NotificationEC] = deque()
		self.__pending = asyncio.Event()
		self.__skip = asyncio.Event()
		self.__showing = False
		self.__last_shown = time.monotonic()
		self.__had_timer = False

	async def start(self):
		self.__entity = self.env.data_storage.create_entity()
		self.__entity.add_component(AvatarViewEC())
		self.__mark_dirty()

		self.add_listener(events.REQUEST_NOTIFICATION_SHOW, self.__on_notification)
		self.add_listener(EVENT_CLICKED, self.__on_clicked)
		self.add_listener(EVENT_MOVED, self.__on_moved)
		self.add_listener(events.ACTION_STORAGE_RESTORED, self.__on_restored)
		self.add_listener(events.ACTION_PLUGINS_CHANGED, self.__on_plugins_changed)

		self.add_task(self.__speak())
		self.add_task(self.__idle())
		self.add_task(self.__watch_timer())

	def __mark_dirty(self):
		if not self.__entity.has_component(RenderDirtyEC):
			self.__entity.add_component(RenderDirtyEC())

	def __view(self) -> AvatarViewEC:
		return self.__entity.get_component(AvatarViewEC)

	def __set_bubble(self, text: str):
		self.__view().bubble = text
		self.__mark_dirty()

	def __set_timer_progress(self, value: float):
		self.__view().timer_progress = value
		self.__mark_dirty()

	def __refresh_menu(self):
		self.__view().menu = [
			(entity.entity_id, entity.get_component(MenuItemEC).name)
			for entity in menu_items(self.env.data_storage)
		]
		self.__mark_dirty()

	async def __on_restored(self, restored: int):
		self.__refresh_menu()

	async def __on_plugins_changed(self, state: dict):
		self.__refresh_menu()

	async def __on_notification(self, notification: NotificationEC):
		if notification.source == SOURCE_CLICK:
			self.__queue.appendleft(notification)
			self.__skip.set()
		else:
			self.__queue.append(notification)
		self.__pending.set()

	async def __on_clicked(self):
		self.env.event_bus.dispatch(
			events.REQUEST_NOTIFICATION_SHOW,
			NotificationEC(text="Hello!", source=SOURCE_CLICK),
		)

	async def __on_moved(self, position):
		pass

	async def __speak(self):
		while True:
			if not self.__queue:
				self.__pending.clear()
				await self.__pending.wait()
				continue

			notification = self.__queue.popleft()
			self.__skip.clear()
			self.__showing = True
			self.__set_bubble(notification.text or notification.title)

			try:
				await asyncio.wait_for(self.__skip.wait(), BUBBLE_S)
			except TimeoutError:
				pass

			self.__set_bubble("")
			self.__showing = False
			self.__last_shown = time.monotonic()
			self.env.event_bus.dispatch(events.ACTION_NOTIFICATION_SHOWN, notification)

	async def __idle(self):
		while True:
			await asyncio.sleep(1)
			if self.__queue or self.__showing:
				continue
			if time.monotonic() - self.__last_shown < IDLE_S:
				continue
			self.env.event_bus.dispatch(
				events.REQUEST_NOTIFICATION_SHOW,
				NotificationEC(text=random.choice(PHRASES), source=SOURCE),
			)

	async def __watch_timer(self):
		while True:
			await asyncio.sleep(TIMER_POLL_S)
			timer = self.__running_timer()
			if timer is not None:
				self.__had_timer = True
				self.__set_timer_progress(self.__timer_progress())
			elif self.__had_timer:
				self.__had_timer = False
				self.__set_timer_progress(-1.0)

	def __running_timer(self) -> Optional[Entity]:
		for entity in self.env.data_storage.get_collection(TimerEC):
			return entity
		return None

	def __timer_progress(self) -> float:
		timers = [
			entity.get_component(TimerEC)
			for entity in self.env.data_storage.get_collection(TimerEC)
		]
		if not timers:
			return -1.0
		timer = min(timers, key=lambda item: item.deadline())
		span = timer.duration.total_seconds()
		if span <= 0:
			return 0.0
		return max(0.0, min(1.0, timer.remaining() / span))
