import asyncio
import json
import queue
import threading
from typing import Any, Dict, Optional, Tuple

from PySide6.QtWidgets import QApplication
import PySide6.QtAsyncio as QtAsyncio

from avatar_api import Entity, Env, System, events
from avatar_api.action import trigger

from avatar_ui.avatar_widget import AvatarWidget
from avatar_ui.bridge import Bridge
from avatar_ui.components import AvatarViewEC, RenderDirtyEC, TabViewEC, WindowEC
from avatar_ui.page import HtmlPage
from avatar_ui.sync import Guarded
from avatar_ui.tabs import TabbedWindow

DEFAULT_WINDOW = ""
POLL_S = 1 / 30

PageState = Dict[str, Any]


class UiSystem(System):
	"""Everything Qt lives on one dedicated thread with its own loop. The asyncio thread
	that runs every other System never touches a widget - it only writes guarded copies
	and posts events, both of which are safe to cross a thread boundary."""

	def __init__(self, env: Env):
		super().__init__(env)
		self.__loop: Optional[asyncio.AbstractEventLoop] = None
		self.__thread: Optional[threading.Thread] = None
		self.__app: Optional[QApplication] = None
		self.__ready = threading.Event()

		self.__pages: Guarded[Dict[int, PageState]] = Guarded({})
		self.__avatar: Guarded[Optional[dict]] = Guarded(None)
		self.__commands: "queue.SimpleQueue[Tuple]" = queue.SimpleQueue()

		# built on the Qt thread only - never touched from the asyncio side
		self.__windows: Dict[str, TabbedWindow] = {}
		self.__built: Dict[int, Tuple[Bridge, HtmlPage]] = {}
		self.__avatar_widget: Optional[AvatarWidget] = None

		self.add_listener(events.REQUEST_PAGE_SHOW, self.__on_show)

	async def start(self):
		self.__loop = asyncio.get_running_loop()
		self.__thread = threading.Thread(target=self.__run_qt, name="avatar-ui", daemon=True)
		self.__thread.start()
		await asyncio.get_running_loop().run_in_executor(None, self.__ready.wait)
		self.add_task(self.__poll_dirty())

	async def stop(self):
		await super().stop()
		if self.__app is not None:
			self.__app.quit()
		if self.__thread is not None:
			self.__thread.join(timeout=5.0)

	# --- asyncio side: scans the storage, never touches a widget ---

	async def __poll_dirty(self):
		while True:
			self.__scan_dirty()
			await asyncio.sleep(POLL_S)

	def __scan_dirty(self):
		for entity in list(self.env.data_storage.get_collection(RenderDirtyEC)):
			if entity.has_component(WindowEC) and entity.has_component(TabViewEC):
				self.__sync_page(entity)
			if entity.has_component(AvatarViewEC):
				self.__sync_avatar(entity)
			entity.remove_component(RenderDirtyEC)

	def __sync_page(self, entity: Entity) -> None:
		window = entity.get_component(WindowEC)
		view = entity.get_component(TabViewEC)
		pages = dict(self.__pages.get())
		pages[entity.entity_id] = {
			"title": window.title,
			"window": window.window,
			"path": view.path,
			"channel": view.channel,
			"snapshot": view.snapshot,
			"methods": dict(view.methods),
		}
		self.__pages.set(pages)

	def __sync_avatar(self, entity: Entity) -> None:
		view = entity.get_component(AvatarViewEC)
		self.__avatar.set({
			"bubble": view.bubble,
			"timer_progress": view.timer_progress,
			"menu": list(view.menu),
		})

	async def __on_show(self, title: str, window: str = DEFAULT_WINDOW):
		self.__commands.put(("show", title, window))

	# --- called from the Qt thread, hands off to the asyncio thread ---

	def post_event(self, event: str, *args: Any) -> None:
		self.__loop.call_soon_threadsafe(self.env.event_bus.dispatch, event, *args)

	def trigger_menu(self, entity_id: int) -> None:
		def run():
			entity = self.env.data_storage.get_entity(entity_id)
			if entity is not None:
				trigger(self.env.event_bus, entity)
		self.__loop.call_soon_threadsafe(run)

	def invoke_page(self, entity_id: int, method: str, args_json: str) -> None:
		def run():
			page = self.__pages.get().get(entity_id)
			if page is None:
				return
			event = page["methods"].get(method)
			if not event:
				return
			try:
				values = json.loads(args_json) if args_json else []
			except ValueError:
				values = []
			self.env.event_bus.dispatch(event, *(values if isinstance(values, list) else [values]))
		self.__loop.call_soon_threadsafe(run)

	# --- Qt thread: its own loop, never reaches into env.data_storage or env.event_bus ---

	def __run_qt(self):
		app = QApplication([])
		app.setQuitOnLastWindowClosed(False)
		self.__app = app

		self.__avatar_widget = AvatarWidget(self.post_event, self.trigger_menu)
		self.__avatar_widget.show()

		self.__ready.set()
		QtAsyncio.run(self.__qt_loop(), keep_running=True, handle_sigint=False)

	async def __qt_loop(self):
		while True:
			self.__drain_commands()
			self.__apply_pages()
			self.__avatar_widget.apply(self.__avatar.get())
			self.__avatar_widget.advance(POLL_S)
			await asyncio.sleep(POLL_S)

	def __drain_commands(self) -> None:
		while True:
			try:
				command = self.__commands.get_nowait()
			except queue.Empty:
				return
			if command[0] == "show":
				self.__show(command[1], command[2])

	def __show(self, title: str, window_name: str) -> None:
		window = self.__windows.get(window_name)
		if window is None:
			return
		page = window.select(title)
		window.show()
		window.raise_()
		window.activateWindow()
		if page is not None and not page.loaded:
			asyncio.ensure_future(page.load())

	def __window(self, name: str) -> TabbedWindow:
		window = self.__windows.get(name)
		if window is None:
			window = TabbedWindow(name)
			self.__windows[name] = window
			window.tabs.currentChanged.connect(lambda index, w=window: self.__on_tab_changed(w, index))
		return window

	def __on_tab_changed(self, window: TabbedWindow, index: int) -> None:
		html = window.tabs.widget(index)
		if isinstance(html, HtmlPage) and not html.loaded:
			asyncio.ensure_future(html.load())

	def __apply_pages(self) -> None:
		for entity_id, spec in self.__pages.get().items():
			built = self.__built.get(entity_id)
			if built is None:
				window = self.__window(spec["window"])
				bridge = Bridge(entity_id, self)
				html_page = window.add_page(spec["title"], spec["path"], {spec["channel"]: bridge})
				bridge.push(spec["snapshot"])
				self.__built[entity_id] = (bridge, html_page)
			else:
				bridge, _ = built
				bridge.push(spec["snapshot"])
