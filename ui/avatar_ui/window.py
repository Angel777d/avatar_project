import asyncio
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

DEFAULT_SIZE = (940, 620)


def await_signal(signal) -> asyncio.Future:
	future = asyncio.get_running_loop().create_future()

	def handler(*args):
		signal.disconnect(handler)
		if not future.done():
			future.set_result(args[0] if len(args) == 1 else args)

	signal.connect(handler)
	return future


def eval_js(page, script: str) -> asyncio.Future:
	future = asyncio.get_running_loop().create_future()
	page.runJavaScript(script, lambda value: future.done() or future.set_result(value))
	return future


class HtmlWindow(QMainWindow):
	def __init__(self,
	             title: str,
	             page: Union[str, Path],
	             objects: Optional[Mapping[str, QObject]] = None,
	             size: Tuple[int, int] = DEFAULT_SIZE):
		super().__init__()
		self.setWindowTitle(title)
		self.resize(*size)

		self.__page = Path(page)
		self.view = QWebEngineView(self)
		self.channel = QWebChannel(self.view.page())
		for name, obj in (objects or {}).items():
			self.channel.registerObject(name, obj)
		self.view.page().setWebChannel(self.channel)
		self.setCentralWidget(self.view)

	async def load(self) -> Any:
		ready = await_signal(self.view.loadFinished)
		self.view.load(QUrl.fromLocalFile(str(self.__page)))
		return await ready

	def eval_js(self, script: str) -> asyncio.Future:
		return eval_js(self.view.page(), script)
