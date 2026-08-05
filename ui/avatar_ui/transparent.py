from typing import Callable, Iterable, Optional, Tuple

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QGuiApplication, QRegion
from PySide6.QtWidgets import QMenu, QWidget

DRAG_SLOP = 4


class TransparentWindow(QWidget):
	def __init__(self, size: Tuple[int, int]):
		super().__init__()
		self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
		self.setAttribute(Qt.WA_TranslucentBackground)
		self.setFixedSize(*size)

		self.__press_global: Optional[QPoint] = None
		self.__dragged = False

	def place_bottom_right(self, margin_x: int = 24, margin_y: int = 12) -> None:
		area = QGuiApplication.primaryScreen().availableGeometry()
		self.move(area.right() - self.width() - margin_x, area.bottom() - self.height() - margin_y)

	def set_shape(self, region: QRegion) -> None:
		self.setMask(region)

	def show_menu(self, global_pos: QPoint, actions: Iterable[Tuple[str, Callable[[], None]]]) -> None:
		menu = QMenu(self)
		for title, callback in actions:
			action = QAction(title, menu)
			action.triggered.connect(lambda _checked=False, cb=callback: cb())
			menu.addAction(action)
		if menu.actions():
			menu.exec(global_pos)

	def on_click(self) -> None:
		pass

	def on_drag_end(self, position: QPoint) -> None:
		pass

	def on_context_menu(self, global_pos: QPoint) -> None:
		pass

	def mousePressEvent(self, event):
		if event.button() == Qt.RightButton:
			self.on_context_menu(event.globalPosition().toPoint())
			return
		if event.button() == Qt.LeftButton:
			self.__press_global = event.globalPosition().toPoint()
			self.__dragged = False

	def mouseMoveEvent(self, event):
		if self.__press_global is None:
			return
		delta = event.globalPosition().toPoint() - self.__press_global
		if not self.__dragged and delta.manhattanLength() < DRAG_SLOP:
			return
		self.__dragged = True
		self.move(self.pos() + delta)
		self.__press_global = event.globalPosition().toPoint()

	def mouseReleaseEvent(self, event):
		if event.button() != Qt.LeftButton:
			return
		if self.__dragged:
			self.on_drag_end(self.pos())
		elif self.__press_global is not None:
			self.on_click()
		self.__press_global = None
		self.__dragged = False
