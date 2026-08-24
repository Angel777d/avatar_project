from pathlib import Path
from typing import Dict, List, Tuple, Union

from angelovich.core.DataStorage import EntityComponent


class WindowEC(EntityComponent):
	"""A page hosted in a tabbed window. Not for the avatar - it isn't tabbed."""

	def __init__(self, title: str = "", window: str = ""):
		super().__init__()
		self.title: str = title
		self.window: str = window


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
