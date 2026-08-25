from pathlib import Path
from typing import Dict, Hashable, List, Tuple, Union

from angelovich.core.DataStorage import EntityComponent, EntityHashComponent

DEFAULT_WINDOW = ""


class WindowEC(EntityHashComponent):
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
	def __init__(self, title: str = "", window: str = DEFAULT_WINDOW):
		super().__init__()
		self.title: str = title
		self.window: str = window


class CurrentTabEC(EntityComponent):
	pass


class TabViewEC(EntityComponent):
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
	def __init__(self,
	             bubble: str = "",
	             timer_progress: float = -1.0,
	             menu: List[Tuple[int, str]] = None):
		super().__init__()
		self.bubble: str = bubble
		self.timer_progress: float = timer_progress
		self.menu: List[Tuple[int, str]] = list(menu or [])


class RenderDirtyEC(EntityComponent):
	pass
