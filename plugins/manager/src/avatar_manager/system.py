import asyncio
import json
import logging
from typing import Dict, List, Optional, Set

from avatar_api import Entity, Env, System, events
from avatar_api.menu import add_menu_item
from avatar_ui.components import RenderDirtyEC, TabEC, TabViewEC

from avatar_manager import registries
from avatar_manager.window import (
	CHANNEL,
	EVENT_APPLY,
	EVENT_OPEN,
	EVENT_REFRESH,
	EVENT_REGISTRY_ADD,
	EVENT_REGISTRY_REMOVE,
	EVENT_REVERT,
	EVENT_TOGGLE,
	METHODS,
	PAGE,
)

logger = logging.getLogger(__name__)

MENU_ITEM = "Open plugins"
PAGE_TITLE = "Plugins"


class ManagerSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__entity: Optional[Entity] = None
		self.__catalogue: List[dict] = []
		self.__sources: List[dict] = []
		self.__installed: List[str] = []
		self.__wanted: Set[str] = set()
		self.__touched = False
		self.__status: Dict = {"available": False, "busy": False, "step": "", "applied": [],
		                       "deferred": [], "failed": [], "restart": False, "error": ""}
		self.__loading = False

		self.add_listener(EVENT_OPEN, self.__on_open)
		self.add_listener(EVENT_TOGGLE, self.__on_toggle)
		self.add_listener(EVENT_APPLY, self.__on_apply)
		self.add_listener(EVENT_REVERT, self.__on_revert)
		self.add_listener(EVENT_REFRESH, self.__on_refresh)
		self.add_listener(EVENT_REGISTRY_ADD, self.__on_registry_add)
		self.add_listener(EVENT_REGISTRY_REMOVE, self.__on_registry_remove)
		self.add_listener(events.ACTION_PLUGINS_CHANGED, self.__on_plugins_changed)

	async def start(self):
		add_menu_item(self.env.data_storage, MENU_ITEM, EVENT_OPEN)

		self.__register()

		self.__reload(False)

	async def stop(self):
		await super().stop()

	def __register(self):
		self.__entity = self.env.data_storage.create_entity()
		self.__entity.add_component(TabEC(PAGE_TITLE))
		self.__entity.add_component(TabViewEC(PAGE, CHANNEL, json.dumps(self.snapshot()), METHODS))
		self.__mark_dirty()

	def __mark_dirty(self):
		if not self.__entity.has_component(RenderDirtyEC):
			self.__entity.add_component(RenderDirtyEC())

	def snapshot(self) -> dict:
		installed = set(self.__installed)
		plugins = []
		for entry in self.__catalogue:
			plugins.append({
				**entry,
				"installed": entry["requirement"] in installed,
				"wanted": entry["name"] in self.__wanted,
			})

		known = {entry["requirement"] for entry in self.__catalogue}
		for requirement in self.__installed:
			if requirement in known:
				continue
			plugins.append({
				"name": requirement,
				"title": requirement.split("@")[0].split("=")[0].strip(),
				"summary": "Installed, but no registry offers it any more.",
				"version": "",
				"requirement": requirement,
				"homepage": "",
				"restartNeeded": False,
				"registry": "",
				"installed": True,
				"wanted": requirement in self.__wanted,
				"orphan": True,
			})

		return {
			"plugins": plugins,
			"registries": self.__sources,
			"status": self.__status,
			"dirty": self.__touched,
			"loading": self.__loading,
		}

	def __reload(self, refresh: bool) -> None:
		if self.__loading:
			return
		self.__loading = True
		self.__announce()
		self.add_task(self.__load(refresh))

	async def __load(self, refresh: bool) -> None:
		try:
			catalogue, sources = await asyncio.to_thread(
				registries.catalogue, self.env.workspace, refresh)
			self.__catalogue = catalogue
			self.__sources = sources
		except Exception as ex:
			logger.error("could not read the registries: %s", ex, exc_info=True)
			self.__status = {**self.__status, "error": f"{ex}"}
		finally:
			self.__loading = False

		if not self.__touched:
			self.__reset_wanted()
		self.__announce()

	def __reset_wanted(self) -> None:
		installed = set(self.__installed)
		self.__wanted = {entry["name"] for entry in self.__catalogue if entry["requirement"] in installed}
		known = {entry["requirement"] for entry in self.__catalogue}
		self.__wanted |= {requirement for requirement in self.__installed if requirement not in known}
		self.__touched = False

	def __announce(self) -> None:
		if self.__entity is None:
			return
		self.__entity.get_component(TabViewEC).snapshot = json.dumps(self.snapshot())
		self.__mark_dirty()

	async def __on_open(self):
		self.env.event_bus.dispatch(events.REQUEST_PAGE_SHOW, PAGE_TITLE)

	async def __on_plugins_changed(self, state: dict):
		self.__installed = list(state.get("requirements", []))
		self.__status = {key: value for key, value in state.items() if key != "requirements"}
		if not self.__touched:
			self.__reset_wanted()
		self.__announce()

	async def __on_toggle(self, name: str, wanted: bool):
		if wanted:
			self.__wanted.add(name)
		else:
			self.__wanted.discard(name)
		self.__touched = True
		self.__announce()

	async def __on_revert(self):
		self.__reset_wanted()
		self.__announce()

	async def __on_refresh(self):
		self.__reload(True)

	async def __on_apply(self, action: str = ""):
		requirements = []
		for entry in self.__catalogue:
			if entry["name"] in self.__wanted:
				requirements.append(entry["requirement"])

		known = {entry["name"] for entry in self.__catalogue}
		for requirement in self.__installed:
			if requirement not in known and requirement in self.__wanted:
				requirements.append(requirement)

		self.__touched = False
		self.__announce()
		await self.env.event_bus.dispatch_async(events.REQUEST_PLUGINS_APPLY, requirements, action)

	async def __on_registry_add(self, name: str, location: str):
		name = name.strip()
		location = location.strip()
		if not name or not location or name == registries.BUILTIN_NAME:
			return

		entries = registries.read_registries(self.env.workspace)
		if any(entry["name"] == name for entry in entries):
			return

		remote = location.startswith("http://") or location.startswith("https://")
		entries.append({"name": name, "url": location} if remote else {"name": name, "path": location})
		registries.write_registries(self.env.workspace, entries)
		logger.info("added registry %s", name)
		self.__reload(True)

	async def __on_registry_remove(self, name: str):
		entries = [entry for entry in registries.read_registries(self.env.workspace)
		           if entry["name"] != name]
		registries.write_registries(self.env.workspace, entries)
		logger.info("removed registry %s", name)
		self.__reload(False)
