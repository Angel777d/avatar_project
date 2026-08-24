import asyncio
import json
import logging
import queue
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtWidgets import QApplication
import PySide6.QtAsyncio as QtAsyncio

from avatar_api import Entity, Env, System, events
from avatar_api.action import trigger

from avatar_ui.avatar_widget import AvatarWidget
from avatar_ui.bridge import Bridge
from avatar_ui.components import (
	DEFAULT_WINDOW,
	AvatarViewEC,
	CurrentTabEC,
	RenderDirtyEC,
	TabEC,
	TabViewEC,
	WindowEC,
)
from avatar_ui.page import HtmlPage
from avatar_ui.render import AvatarView, PageView
from avatar_ui.sync import Guarded
from avatar_ui.tabs import TabbedWindow

logger = logging.getLogger(__name__)

POLL_S = 1 / 30

WATCHED = (WindowEC, CurrentTabEC, TabEC)


class UiSystem(System):
	"""Everything Qt lives on one dedicated thread with its own loop. The asyncio thread
	that runs every other System never touches a widget - it only writes guarded copies
	and posts commands, both of which are safe to cross a thread boundary.

	Windows and tabs are entities: a WindowEC entity is a window and losing it closes one,
	the CurrentTabEC marker is which tab is up. ADDED/REMOVED on those collections is the
	only change notification the storage offers, and it is exactly the one this needs."""

	def __init__(self, env: Env):
		super().__init__(env)
		self.__loop: Optional[asyncio.AbstractEventLoop] = None
		self.__thread: Optional[threading.Thread] = None
		self.__app: Optional[QApplication] = None
		self.__ready = threading.Event()
		self.__stopping = threading.Event()
		self.__failure: Optional[BaseException] = None

		self.__pages: Guarded[Dict[int, PageView]] = Guarded({})
		self.__avatar: Guarded[Optional[AvatarView]] = Guarded(None)
		self.__commands: "queue.SimpleQueue[Callable[[], None]]" = queue.SimpleQueue()

		# built on the Qt thread only - never touched from the asyncio side
		self.__windows: Dict[str, TabbedWindow] = {}
		self.__window_names: Dict[int, str] = {}
		self.__built: Dict[int, Tuple[Bridge, HtmlPage]] = {}
		self.__avatar_widget: Optional[AvatarWidget] = None
		self.__pending_select: Optional[Tuple[str, str]] = None

		self.add_listener(events.REQUEST_PAGE_SHOW, self.__on_show)

	async def start(self):
		self.__loop = asyncio.get_running_loop()
		self.__thread = threading.Thread(target=self.__run_qt, name="avatar-ui", daemon=True)
		self.__thread.start()
		await asyncio.get_running_loop().run_in_executor(None, self.__ready.wait)
		if self.__failure is not None:
			raise RuntimeError("the interface could not start") from self.__failure
		self.__subscribe()
		self.add_task(self.__poll_dirty())

	async def stop(self):
		await super().stop()
		# a collection is its own Dispatcher, so System.stop() knows nothing about these
		for component in WATCHED:
			self.env.data_storage.get_collection(component).remove_all_listeners(self)

		# The Qt thread tears itself down: widgets and the QApplication belong to it,
		# and a daemon thread parked in Qt's C++ loop never returns to python to be killed.
		self.__stopping.set()
		if self.__thread is not None:
			await asyncio.get_running_loop().run_in_executor(None, self.__thread.join, 5.0)
			if self.__thread.is_alive():
				logger.error("the interface thread did not stop")

	def __subscribe(self) -> None:
		storage = self.env.data_storage
		windows = storage.get_collection(WindowEC)
		windows.add_listener(windows.EVENT_ADDED, self.__on_window_added, scope=self)
		windows.add_listener(windows.EVENT_REMOVED, self.__on_window_removed, scope=self)

		current = storage.get_collection(CurrentTabEC)
		current.add_listener(current.EVENT_ADDED, self.__on_tab_current, scope=self)

		tabs = storage.get_collection(TabEC)
		tabs.add_listener(tabs.EVENT_REMOVED, self.__on_tab_removed, scope=self)

	# --- asyncio side: reads the storage, never touches a widget ---

	async def __on_window_added(self, entity: Entity, component: WindowEC):
		name, entity_id = component.name, entity.entity_id
		self.__commands.put(lambda: self.__open_window(entity_id, name))

	async def __on_window_removed(self, entity_id: int):
		# REMOVED carries the id, not the entity: by the time this runs the entity is a husk
		self.__commands.put(lambda: self.__close_window(entity_id))

	async def __on_tab_current(self, entity: Entity, component: CurrentTabEC):
		if not entity.has_component(TabEC):
			return
		tab = entity.get_component(TabEC)
		title, window = tab.title, tab.window
		self.__commands.put(lambda: self.__request_select(window, title))

	async def __on_tab_removed(self, entity_id: int):
		pages = dict(self.__pages.get())
		view = pages.pop(entity_id, None)
		if view is None:
			return
		self.__pages.set(pages)
		window, title = view.window, view.title
		self.__commands.put(lambda: self.__drop_tab(entity_id, window, title))

	async def __on_show(self, title: str, window: str = DEFAULT_WINDOW):
		page = self.__tab(title, window)
		if page is None:
			return
		self.__ensure_window(window)
		for entity in list(self.env.data_storage.get_collection(CurrentTabEC)):
			if entity.has_component(TabEC) and entity.get_component(TabEC).window == window:
				entity.remove_component(CurrentTabEC)
		page.add_component(CurrentTabEC())

	def __tab(self, title: str, window: str) -> Optional[Entity]:
		for entity in self.env.data_storage.get_collection(TabEC):
			tab = entity.get_component(TabEC)
			if tab.title == title and tab.window == window:
				return entity
		return None

	def __ensure_window(self, name: str) -> None:
		storage = self.env.data_storage
		if storage.get_collection(WindowEC).find(WindowEC.make_hash(name)) is not None:
			return
		storage.create_entity().add_component(WindowEC(name))

	async def __poll_dirty(self):
		while True:
			self.__scan_dirty()
			await asyncio.sleep(POLL_S)

	def __scan_dirty(self):
		for entity in list(self.env.data_storage.get_collection(RenderDirtyEC)):
			if entity.has_component(TabEC) and entity.has_component(TabViewEC):
				self.__sync_page(entity)
			if entity.has_component(AvatarViewEC):
				self.__sync_avatar(entity)
			entity.remove_component(RenderDirtyEC)

	def __sync_page(self, entity: Entity) -> None:
		"""The only place a TabEC/TabViewEC pair becomes a PageView - trivial field
		copying, nothing the Qt side has to interpret."""
		tab = entity.get_component(TabEC)
		view = entity.get_component(TabViewEC)
		pages = dict(self.__pages.get())
		pages[entity.entity_id] = PageView(
			title=tab.title,
			window=tab.window,
			path=view.path,
			channel=view.channel,
			snapshot=view.snapshot,
			methods=dict(view.methods),
		)
		self.__pages.set(pages)

	def __sync_avatar(self, entity: Entity) -> None:
		"""The only place an AvatarViewEC becomes an AvatarView."""
		view = entity.get_component(AvatarViewEC)
		self.__avatar.set(AvatarView(
			bubble=view.bubble,
			timer_progress=view.timer_progress,
			menu=list(view.menu),
		))

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
			event = page.methods.get(method)
			if not event:
				return
			try:
				values = json.loads(args_json) if args_json else []
			except ValueError:
				values = []
			self.env.event_bus.dispatch(event, *(values if isinstance(values, list) else [values]))
		self.__loop.call_soon_threadsafe(run)

	def window_closed(self, entity_id: int) -> None:
		"""The user closed the window, so the window entity is what goes away.
		Teardown closes every window too, and that is not the user asking for anything."""
		if self.__stopping.is_set():
			return

		def run():
			entity = self.env.data_storage.get_entity(entity_id)
			if entity is not None:
				self.env.data_storage.remove_entity(entity)
		self.__loop.call_soon_threadsafe(run)

	# --- Qt thread: its own loop, never reaches into env.data_storage or env.event_bus ---

	def __run_qt(self):
		try:
			app = QApplication([])
			app.setQuitOnLastWindowClosed(False)
			self.__app = app

			self.__avatar_widget = AvatarWidget(self.post_event, self.trigger_menu)
			self.__avatar_widget.show()
		except BaseException as ex:
			# Nothing above reaches a caller, and a half-built interface would hang start()
			# on __ready forever. Record it, release the wait, let start() raise it.
			self.__failure = ex
			self.__ready.set()
			return

		self.__ready.set()
		# keep_running=False: when __qt_loop returns, the Qt loop stops and this thread ends.
		QtAsyncio.run(self.__qt_loop(), keep_running=False, handle_sigint=False)

	async def __qt_loop(self):
		while not self.__stopping.is_set():
			self.__drain_commands()
			self.__apply_pages()
			# after the tabs exist, or selecting one that was registered this tick misses
			self.__apply_select()
			self.__avatar_widget.apply(self.__avatar.get())
			self.__avatar_widget.advance(POLL_S)
			await asyncio.sleep(POLL_S)
		self.__teardown()

	def __teardown(self) -> None:
		"""On the Qt thread, where every widget was built. Returning from __qt_loop is what
		stops the loop - quitting the QApplication here closes it under QtAsyncio's own
		cleanup instead, which then raises on a loop it can no longer use."""
		for window in self.__windows.values():
			window.close()
		self.__windows.clear()
		self.__window_names.clear()
		self.__built.clear()
		if self.__avatar_widget is not None:
			self.__avatar_widget.close()
			self.__avatar_widget = None

	def __drain_commands(self) -> None:
		while True:
			try:
				command = self.__commands.get_nowait()
			except queue.Empty:
				return
			try:
				command()
			except Exception as ex:
				logger.error("interface command failed: %s", ex, exc_info=True)

	def __open_window(self, entity_id: int, name: str) -> None:
		self.__window_names[entity_id] = name
		if name in self.__windows:
			return
		window = TabbedWindow(name, on_close=lambda eid=entity_id: self.window_closed(eid))
		window.tabs.currentChanged.connect(
			lambda index, opened=window: self.__on_tab_changed(opened, index))
		self.__windows[name] = window

	def __close_window(self, entity_id: int) -> None:
		name = self.__window_names.pop(entity_id, None)
		if name is None:
			return
		window = self.__windows.pop(name, None)
		if window is None:
			return
		for page_id, view in self.__pages.get().items():
			if view.window == name:
				self.__built.pop(page_id, None)
		if self.__pending_select is not None and self.__pending_select[0] == name:
			self.__pending_select = None
		window.close()
		window.deleteLater()

	def __drop_tab(self, page_id: int, window_name: str, title: str) -> None:
		self.__built.pop(page_id, None)
		window = self.__windows.get(window_name)
		if window is not None:
			window.remove_page(title)

	def __request_select(self, window_name: str, title: str) -> None:
		self.__pending_select = (window_name, title)

	def __apply_select(self) -> None:
		if self.__pending_select is None:
			return
		window_name, title = self.__pending_select
		window = self.__windows.get(window_name)
		if window is None:
			return
		self.__pending_select = None
		page = window.select(title)
		window.show()
		window.raise_()
		window.activateWindow()
		if page is not None and not page.loaded:
			asyncio.ensure_future(page.load())

	def __on_tab_changed(self, window: TabbedWindow, index: int) -> None:
		html = window.tabs.widget(index)
		if isinstance(html, HtmlPage) and not html.loaded:
			asyncio.ensure_future(html.load())

	def __apply_pages(self) -> None:
		for entity_id, view in self.__pages.get().items():
			window = self.__windows.get(view.window)
			if window is None:
				continue  # its window is not open, so there is nowhere to put the tab yet
			built = self.__built.get(entity_id)
			if built is None:
				bridge = Bridge(entity_id, self)
				html = window.add_page(view.title, view.path, {view.channel: bridge})
				bridge.push(view.snapshot)
				self.__built[entity_id] = (bridge, html)
			else:
				built[0].push(view.snapshot)
