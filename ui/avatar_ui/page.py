import asyncio
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

ASSETS = Path(__file__).resolve().parent / "assets"
THEME = ASSETS / "theme.css"
BRIDGE = ASSETS / "bridge.js"
SHARED = (ASSETS / "editor.css", ASSETS / "editor.js")


def style_script(path: Path, name: str) -> QWebEngineScript:
	"""The theme has to exist before the page's own style element is parsed, or it wins ties it should lose."""
	# The document is empty at DocumentCreation — head arrives later, but still before
	# the page's own style element, which is what keeps the theme first in the cascade.
	source = (
		"(() => {"
		f"const css = {json.dumps(path.read_text(encoding='utf-8'))};"
		"const put = () => { if (!document.head) return false;"
		"const style = document.createElement('style'); style.textContent = css;"
		"document.head.insertBefore(style, document.head.firstChild); return true; };"
		"if (put()) return;"
		"const watch = new MutationObserver(() => { if (put()) watch.disconnect(); });"
		"watch.observe(document, { childList: true, subtree: true }); })()"
	)
	script = QWebEngineScript()
	script.setName(name)
	script.setSourceCode(source)
	script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
	script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
	script.setRunsOnSubFrames(False)
	return script


def raw_script(path: Path, name: str) -> QWebEngineScript:
	"""The page's own script constructs QWebChannel during load, so the shim
	that intercepts it has to be there before a single line of page JS runs."""
	script = QWebEngineScript()
	script.setName(name)
	script.setSourceCode(path.read_text(encoding="utf-8"))
	script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
	script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
	script.setRunsOnSubFrames(False)
	return script


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


class HtmlPage(QWidget):
	def __init__(self,
	             page: Union[str, Path],
	             objects: Optional[Mapping[str, QObject]] = None,
	             parent: Optional[QWidget] = None,
	             assets: Sequence[Path] = SHARED):
		super().__init__(parent)
		self.__path = Path(page)
		self.__objects = dict(objects or {})
		self.__assets = tuple(assets)
		self.__loaded = False
		self.__loading: Optional[asyncio.Future] = None

		self.view: Optional[QWebEngineView] = None
		self.channel: Optional[QWebChannel] = None

		self.__layout = QVBoxLayout(self)
		self.__layout.setContentsMargins(0, 0, 0, 0)

	@property
	def loaded(self) -> bool:
		return self.__loaded

	def build(self) -> QWebEngineView:
		if self.view is None:
			self.view = QWebEngineView(self)
			self.view.page().scripts().insert(style_script(THEME, "avatar.theme"))
			self.view.page().scripts().insert(raw_script(BRIDGE, "avatar.bridge"))
			self.channel = QWebChannel(self.view.page())
			for name, obj in self.__objects.items():
				self.channel.registerObject(name, obj)
			self.view.page().setWebChannel(self.channel)
			self.__layout.addWidget(self.view)
		return self.view

	async def load(self) -> Any:
		if self.__loaded:
			return True
		if self.__loading is None:
			self.__loading = asyncio.ensure_future(self.__load())
		return await self.__loading

	async def __load(self) -> Any:
		view = self.build()
		ready = await_signal(view.loadFinished)
		view.load(QUrl.fromLocalFile(str(self.__path)))
		self.__loaded = await ready
		if self.__loaded:
			await self.__inject()
		return self.__loaded

	async def __inject(self) -> None:
		for path in self.__assets:
			source = path.read_text(encoding="utf-8")
			if path.suffix == ".css":
				source = (
					"(() => { const style = document.createElement('style');"
					f"style.textContent = {json.dumps(source)};"
					"document.head.appendChild(style); })()"
				)
			await eval_js(self.build().page(), source)

	def eval_js(self, script: str) -> asyncio.Future:
		return eval_js(self.build().page(), script)
