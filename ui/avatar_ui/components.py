from pathlib import Path
from typing import Dict, Hashable, List, Tuple, Union

from angelovich.core.DataStorage import EntityComponent, EntityHashComponent

DEFAULT_WINDOW = ""


class WindowEC(EntityHashComponent):
	"""A window, one entity each, keyed by name. Removing the entity closes it."""

	def __init__(self, name: str = DEFAULT_WINDOW):
		super().__init__()
		self.name: str = name

	@staticmethod
	def make_hash(name: str) -> Hashable:
		return name

	def __hash__(self):
		return hash(self.name)

	def __repr__(self):
		return f"WindowEC({self.name})"


class TabEC(EntityComponent):
	"""A page hosted as a tab: what it is called and which window it belongs to."""

	def __init__(self, title: str = "", window: str = DEFAULT_WINDOW):
		super().__init__()
		self.title: str = title
		self.window: str = window


class CurrentTabEC(EntityComponent):
	"""Marker: the current tab of its window. Moving it switches tab and raises the window.
	It is always removed and re-added, so asking for the tab already shown still raises."""


class TabViewEC(EntityComponent):
	"""Render-ready data for an html page: the owning plugin keeps this current."""

	def __init__(self,
	             path: Union[str, Path] = "",
	             channel: str = "",
	             snapshot: str = "{}",
	             methods: Dict[str, str] = None):
		super().__init__()
		self.path: str = str(path)
		self.channel: str = channel
		self.snapshot: str = snapshot
		self.methods: Dict[str, str] = dict(methods or {})


class AvatarViewEC(EntityComponent):
	"""Render-ready data for the floating avatar widget."""

	def __init__(self,
	             bubble: str = "",
	             timer_progress: float = -1.0,
	             menu: List[Tuple[int, str]] = None):
		super().__init__()
		self.bubble: str = bubble
		self.timer_progress: float = timer_progress
		self.menu: List[Tuple[int, str]] = list(menu or [])


class RenderDirtyEC(EntityComponent):
	"""Marker: this entity's view components changed. avatar_ui clears it once read."""
