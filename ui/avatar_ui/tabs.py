from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple, Union

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMainWindow, QTabWidget

from avatar_ui.page import HtmlPage

DEFAULT_TITLE = "Avatar"
DEFAULT_SIZE = (960, 640)
MIN_SIZE = (720, 520)


class TabbedWindow(QMainWindow):
	def __init__(self,
	             title: str = DEFAULT_TITLE,
	             size: Tuple[int, int] = DEFAULT_SIZE,
	             minimum: Tuple[int, int] = MIN_SIZE):
		super().__init__()
		self.setWindowTitle(title or DEFAULT_TITLE)
		self.setMinimumSize(*minimum)
		self.resize(*size)

		self.tabs = QTabWidget(self)
		self.tabs.setDocumentMode(True)
		self.setCentralWidget(self.tabs)

		self.__pages: Dict[str, HtmlPage] = {}

	@property
	def titles(self) -> List[str]:
		return [self.tabs.tabText(index) for index in range(self.tabs.count())]

	def page(self, title: str) -> Optional[HtmlPage]:
		return self.__pages.get(title)

	def add_page(self,
	             title: str,
	             page: Union[str, Path],
	             objects: Optional[Mapping[str, QObject]] = None) -> HtmlPage:
		existing = self.__pages.get(title)
		if existing is not None:
			return existing
		html = HtmlPage(page, objects, self)
		self.__pages[title] = html
		self.tabs.addTab(html, title)
		return html

	def select(self, title: str) -> Optional[HtmlPage]:
		html = self.__pages.get(title)
		if html is not None:
			self.tabs.setCurrentWidget(html)
		return html

	@property
	def current(self) -> str:
		return self.tabs.tabText(self.tabs.currentIndex())
