from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Tuple, Union

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
	             minimum: Tuple[int, int] = MIN_SIZE,
	             on_close: Optional[Callable[[], None]] = None):
		super().__init__()
		self.setWindowTitle(title or DEFAULT_TITLE)
		self.setMinimumSize(*minimum)
		self.resize(*size)

		self.tabs = QTabWidget(self)
		self.tabs.setDocumentMode(True)
		self.setCentralWidget(self.tabs)

		self.__pages: Dict[str, HtmlPage] = {}
		self.__on_close = on_close

	def closeEvent(self, event):
		# closing the window is the user removing its entity, not a widget hiding itself
		if self.__on_close is not None:
			self.__on_close()
		super().closeEvent(event)

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

	def remove_page(self, title: str) -> None:
		html = self.__pages.pop(title, None)
		if html is None:
			return
		index = self.tabs.indexOf(html)
		if index >= 0:
			self.tabs.removeTab(index)
		html.deleteLater()

	def select(self, title: str) -> Optional[HtmlPage]:
		html = self.__pages.get(title)
		if html is not None:
			self.tabs.setCurrentWidget(html)
		return html
