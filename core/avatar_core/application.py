import asyncio
import importlib
import logging
import sys
import time
from importlib import metadata
from typing import Any, Collection, Dict, Iterable, List, Optional, Tuple

from angelovich.core.Plugin import Plugin, discover_plugins
from angelovich.core.System import System

from avatar_api import events
from avatar_api.env import Env
from avatar_core.core_system import CoreSystem
from avatar_core.storage import Storage
from avatar_core.supervisor import SupervisorSystem
from avatar_core.timer_system import TimerSystem
from avatar_core.plugin_policy import PLUGINS_ENABLED_BY_DEFAULT, select_plugins

logger = logging.getLogger(__name__)

PLUGIN_GROUP = "avatar.plugins"
TICK_TIME = 1.0
SAVE_TIME = 300.0

MANDATORY = frozenset({"avatar_ui"})


def owned_by(component_type, name: str) -> bool:
	module = getattr(component_type, "__module__", "")
	return module == name or module.startswith(f"{name}.")


def load_plugin(name: str) -> Optional[Plugin]:
	"""A package installed after this process started is invisible until the caches go."""
	importlib.invalidate_caches()
	for entry in metadata.entry_points(group=PLUGIN_GROUP):
		if entry.name != name:
			continue
		try:
			module = entry.load()
		except Exception as ex:
			logger.error("plugin module %s import error: %s", name, ex)
			return None
		plugin = getattr(module, "plugin", None)
		if not isinstance(plugin, Plugin):
			logger.error("plugin module %s has no plugin attribute", name)
			return None
		plugin.set_name(name)
		return plugin
	return None


def drop_modules(name: str) -> None:
	"""The whole subtree, or the package reimports around submodules that never reloaded and
	the new code quietly runs the old one."""
	for module in [m for m in sys.modules if m == name or m.startswith(f"{name}.")]:
		del sys.modules[module]
	importlib.invalidate_caches()


class Application:
	def __init__(self,
	             env: Env,
	             systems: Iterable[System] = (),
	             enabled_plugins: Collection[str] = (),
	             disabled_plugins: Collection[str] = (),
	             enabled_by_default: bool = PLUGINS_ENABLED_BY_DEFAULT,
	             tick_time: float = TICK_TIME,
	             storage: Optional[Storage] = None):
		self.env = env
		self.__tick_time = tick_time
		self.storage = storage if storage is not None else Storage()
		self.systems: List[System] = [CoreSystem(env), SupervisorSystem(env), TimerSystem(env)] + list(systems)
		self.plugins: List[Plugin] = select_plugins(
			discover_plugins(PLUGIN_GROUP, disabled_plugins),
			enabled_plugins,
			disabled_plugins,
			enabled_by_default,
		)
		self.__owned: Dict[str, List[System]] = {}
		self.__busy = False

		for plugin in self.plugins:
			self.__adopt(plugin)

	def __adopt(self, plugin: Plugin) -> List[System]:
		try:
			owned = list(plugin.get_systems(self.env))
		except Exception as ex:
			logger.error("plugin %s failed to contribute systems: %s", plugin.name, ex, exc_info=True)
			return []
		self.__owned[plugin.name] = owned
		self.systems.extend(owned)
		return owned

	def shutdown(self) -> None:
		if self.env.close_event:
			self.env.close_event.set()

	async def run(self) -> None:
		env = self.env
		if env.close_event is None:
			env.close_event = asyncio.Event()
		close_event = env.close_event

		logger.info("application start: %d systems from %d plugins", len(self.systems), len(self.plugins))

		env.event_bus.add_listener(events.REQUEST_PLUGINS_RELOAD, self.__on_reload, scope=self)

		for system in self.systems:
			await system.start()

		await self.storage.open()
		restored = await self.storage.load(env)
		logger.info("restored %d entities", restored)
		await env.event_bus.dispatch_async(events.ACTION_STORAGE_RESTORED, restored)

		last_time = time.monotonic()
		last_save = last_time
		while not close_event.is_set():
			current_time = time.monotonic()
			delta_time = current_time - last_time
			last_time = current_time

			if current_time - last_save >= SAVE_TIME and not self.__busy:
				last_save = current_time
				try:
					logger.info("saved %d entities", await self.storage.save(env))
				except Exception as ex:
					logger.error("periodic save failed: %s", ex, exc_info=True)

			for system in list(self.systems):
				try:
					await system.update(delta_time)
				except Exception as ex:
					logger.error("%s update failed: %s", system, ex, exc_info=True)

			await asyncio.sleep(self.__tick_time)

		logger.info("application stop")

		saved = await self.storage.save(env)
		await self.storage.close()
		logger.info("saved %d entities", saved)

		for system in self.systems:
			try:
				await system.stop()
			except Exception as ex:
				logger.error("%s stop failed: %s", system, ex, exc_info=True)

		self.close()

		logger.info("application closed")

	async def __on_reload(self, installed: List[str], removed: List[str]) -> None:
		for name in removed:
			await self.unload_plugin(name)
		for name in installed:
			await self.reload_plugin(name)

	async def reload_plugin(self, name: str) -> bool:
		"""Swap a plugin for whatever is on disk now. Its data goes through the database, which
		is the only thing that survives its classes being replaced."""
		if name in MANDATORY:
			logger.error("%s is mandatory and is only replaced by restarting", name)
			return False

		self.__busy = True
		try:
			if name in self.__owned:
				await self.storage.save(self.env)
			await self.unload_plugin(name, saved=True)

			plugin = load_plugin(name)
			if plugin is None:
				logger.error("plugin %s is not installed", name)
				return False

			self.plugins = [p for p in self.plugins if p.name != name] + [plugin]
			for system in self.__adopt(plugin):
				try:
					await system.start()
				except Exception as ex:
					logger.error("%s start failed: %s", system, ex, exc_info=True)

			restored = await self.storage.load(self.env)
		finally:
			self.__busy = False

		await self.env.event_bus.dispatch_async(events.ACTION_STORAGE_RESTORED, restored)
		logger.info("plugin %s is loaded", name)
		return True

	async def unload_plugin(self, name: str, saved: bool = False) -> bool:
		"""Its systems take their entities with them, its types are forgotten and its modules go,
		so nothing is left holding a class that is about to be replaced."""
		if name in MANDATORY:
			logger.error("%s is mandatory and is not unloaded", name)
			return False

		if not saved:
			self.__busy = True
			try:
				await self.storage.save(self.env)
			finally:
				self.__busy = False

		for system in self.__owned.pop(name, []):
			try:
				await system.stop()
			except Exception as ex:
				logger.error("%s stop failed: %s", system, ex, exc_info=True)
			try:
				system.close()
			except Exception as ex:
				logger.error("%s close failed: %s", system, ex, exc_info=True)
			if system in self.systems:
				self.systems.remove(system)

		self.plugins = [p for p in self.plugins if p.name != name]
		for component_type in [t for t in self.env.registry.types if owned_by(t, name)]:
			self.env.registry.forget(component_type)
		drop_modules(name)
		logger.info("plugin %s is unloaded", name)
		return True

	def close(self) -> None:
		for system in self.systems:
			try:
				system.close()
			except Exception as ex:
				logger.error("%s close failed: %s", system, ex, exc_info=True)
