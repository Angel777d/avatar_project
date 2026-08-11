from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMainWindow

from avatar_ui.page import HtmlPage, await_signal, eval_js

DEFAULT_SIZE = (940, 620)


class HtmlWindow(QMainWindow):
	def __init__(self,
	             title: str,
	             page: Union[str, Path],
	             objects: Optional[Mapping[str, QObject]] = None,
	             size: Tuple[int, int] = DEFAULT_SIZE):
		super().__init__()
		self.setWindowTitle(title)
		self.resize(*size)

		self.page = HtmlPage(page, objects, self)
		self.setCentralWidget(self.page)

	@property
	def view(self):
		return self.page.build()

	async def load(self) -> Any:
		return await self.page.load()

	def eval_js(self, script: str):
		return self.page.eval_js(script)
