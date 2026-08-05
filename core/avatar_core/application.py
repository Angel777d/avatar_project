import asyncio
import logging
import time
from typing import Collection, Iterable, List

from angelovich.core.Plugin import Plugin, discover_plugins
from angelovich.core.System import System

from avatar_api.env import Env
from avatar_core.plugin_policy import PLUGINS_ENABLED_BY_DEFAULT, select_plugins

logger = logging.getLogger(__name__)

PLUGIN_GROUP = "avatar.plugins"
TICK_TIME = 1.0


class Application:
	def __init__(self,
	             env: Env,
	             systems: Iterable[System] = (),
	             enabled_plugins: Collection[str] = (),
	             disabled_plugins: Collection[str] = (),
	             enabled_by_default: bool = PLUGINS_ENABLED_BY_DEFAULT,
	             tick_time: float = TICK_TIME):
		self.env = env
		self.__tick_time = tick_time
		self.systems: List[System] = list(systems)
		self.plugins: List[Plugin] = select_plugins(
			discover_plugins(PLUGIN_GROUP, disabled_plugins),
			enabled_plugins,
			disabled_plugins,
			enabled_by_default,
		)

		for plugin in self.plugins:
			try:
				self.systems.extend(plugin.get_systems(env))
			except Exception as ex:
				logger.error("plugin %s failed to contribute systems: %s", plugin.name, ex, exc_info=True)

	def shutdown(self) -> None:
		if self.env.close_event:
			self.env.close_event.set()

	async def run(self) -> None:
		env = self.env
		if env.close_event is None:
			env.close_event = asyncio.Event()
		close_event = env.close_event

		logger.info("application start: %d systems from %d plugins", len(self.systems), len(self.plugins))

		for system in self.systems:
			await system.start()

		last_time = time.monotonic()
		while not close_event.is_set():
			current_time = time.monotonic()
			delta_time = current_time - last_time
			last_time = current_time

			for system in self.systems:
				try:
					await system.update(delta_time)
				except Exception as ex:
					logger.error("%s update failed: %s", system, ex, exc_info=True)

			await asyncio.sleep(self.__tick_time)

		logger.info("application stop")

		for system in self.systems:
			try:
				await system.stop()
			except Exception as ex:
				logger.error("%s stop failed: %s", system, ex, exc_info=True)

		self.close()

		logger.info("application closed")

	def close(self) -> None:
		for system in self.systems:
			try:
				system.close()
			except Exception as ex:
				logger.error("%s close failed: %s", system, ex, exc_info=True)
