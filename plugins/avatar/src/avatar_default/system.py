import asyncio
import random
import time
from collections import deque
from typing import Deque, Optional

from avatar_api import Environment, System, events
from avatar_api.components import NotificationEC

from avatar_default.widget import EVENT_CLICKED, EVENT_MOVED, EVENT_QUIT, AvatarWidget

SOURCE = "avatar"
SOURCE_CLICK = "avatar.click"

FRAME_S = 1 / 30
BUBBLE_S = 4.5
IDLE_S = 30.0

PHRASES = [
	"Still here.",
	"Anything to do?",
	"I like this corner.",
	"Just floating around.",
	"Nice desktop you have.",
	"Poke me if you need me.",
]


class AvatarSystem(System):
	def __init__(self, env: Environment):
		super().__init__(env)
		self.__widget: Optional[AvatarWidget] = None
		self.__queue: Deque[NotificationEC] = deque()
		self.__pending = asyncio.Event()
		self.__skip = asyncio.Event()
		self.__showing = False
		self.__last_shown = time.monotonic()

	async def start(self):
		self.__widget = AvatarWidget(self.env.event_bus)
		self.__widget.show()

		self.add_listener(events.REQUEST_NOTIFICATION_SHOW, self.__on_notification)
		self.add_listener(EVENT_CLICKED, self.__on_clicked)
		self.add_listener(EVENT_MOVED, self.__on_moved)
		self.add_listener(EVENT_QUIT, self.__on_quit)

		self.add_task(self.__animate())
		self.add_task(self.__speak())
		self.add_task(self.__idle())

	async def stop(self):
		await super().stop()
		if self.__widget:
			self.__widget.close()
			self.__widget = None

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

	async def __on_quit(self):
		close_event = getattr(self.env, "close_event", None)
		if close_event:
			close_event.set()

	async def __animate(self):
		while True:
			if self.__widget:
				self.__widget.advance(FRAME_S)
			await asyncio.sleep(FRAME_S)

	async def __speak(self):
		while True:
			if not self.__queue:
				self.__pending.clear()
				await self.__pending.wait()
				continue

			notification = self.__queue.popleft()
			self.__skip.clear()
			self.__showing = True
			self.__widget.set_bubble(notification.text or notification.title)

			try:
				await asyncio.wait_for(self.__skip.wait(), BUBBLE_S)
			except TimeoutError:
				pass

			self.__widget.set_bubble("")
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
