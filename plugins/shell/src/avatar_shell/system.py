from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple, Union

from PySide6.QtCore import QObject

from avatar_api import Env, System, events
from avatar_ui.page import HtmlPage
from avatar_ui.tabs import TabbedWindow

DEFAULT_WINDOW = ""

Spec = Tuple[Union[str, Path], Dict[str, QObject]]


class ShellSystem(System):
	def __init__(self, env: Env):
		super().__init__(env)
		self.__windows: Dict[str, TabbedWindow] = {}
		self.__specs: Dict[str, List[Tuple[str, Spec]]] = {}

		self.add_listener(events.REQUEST_PAGE_REGISTER, self.__on_register)
		self.add_listener(events.REQUEST_PAGE_SHOW, self.__on_show)

	async def stop(self):
		await super().stop()
		for window in self.__windows.values():
			window.close()
		self.__windows.clear()

	def window(self, name: str = DEFAULT_WINDOW) -> Optional[TabbedWindow]:
		return self.__windows.get(name)

	def page(self, title: str, window: str = DEFAULT_WINDOW) -> Optional[HtmlPage]:
		target = self.__windows.get(window)
		return target.page(title) if target is not None else None

	def registered(self, window: str = DEFAULT_WINDOW) -> List[str]:
		return [title for title, _ in self.__specs.get(window, ())]

	async def __on_register(self,
	                        title: str,
	                        page: Union[str, Path],
	                        objects: Optional[Mapping[str, QObject]] = None,
	                        window: str = DEFAULT_WINDOW):
		if not title:
			return
		pages = self.__specs.setdefault(window, [])
		if any(known == title for known, _ in pages):
			return
		pages.append((title, (page, dict(objects or {}))))

		opened = self.__windows.get(window)
		if opened is not None:
			opened.add_page(title, page, objects)

	def __on_tab_changed(self, window: TabbedWindow, index: int):
		html = window.tabs.widget(index)
		if isinstance(html, HtmlPage) and not html.loaded:
			self.add_task(html.load())

	async def __on_show(self, title: str, window: str = DEFAULT_WINDOW):
		pages = self.__specs.get(window, [])
		if not any(known == title for known, _ in pages):
			return

		target = self.__windows.get(window)
		if target is None:
			target = TabbedWindow(window)
			self.__windows[window] = target
			for known, (page, objects) in pages:
				target.add_page(known, page, objects)
			target.tabs.currentChanged.connect(
				lambda index, opened=target: self.__on_tab_changed(opened, index))

		html = target.select(title)
		target.show()
		target.raise_()
		target.activateWindow()

		if html is not None and not html.loaded:
			self.add_task(html.load())
