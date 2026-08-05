import math
import random
from typing import Callable, List, Tuple

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import (
	QColor,
	QFont,
	QFontMetrics,
	QPainter,
	QPainterPath,
	QPen,
	QRadialGradient,
	QRegion,
)
from avatar_api.menu import menu_items
from avatar_ui.transparent import TransparentWindow

EVENT_CLICKED = "avatar.clicked"
EVENT_MOVED = "avatar.moved"

AVATAR_SIZE = 128
BUBBLE_MAX_W = 236
MARGIN = 14
BOB_AMPLITUDE = 5


class AvatarWidget(TransparentWindow):
	def __init__(self, env):
		super().__init__((BUBBLE_MAX_W + 2 * MARGIN, AVATAR_SIZE + 96))
		self.__env = env
		self.__font = QFont("Segoe UI", 10)
		self.__phase = 0.0
		self.__blink = 0.0
		self.__next_blink = random.uniform(2.0, 5.0)
		self.__elapsed = 0.0
		self.__bubble_text = ""
		self.__bubble_rect = QRect()

		base_x = (self.width() - AVATAR_SIZE) // 2
		base_y = self.height() - AVATAR_SIZE - 4
		self.__avatar_rect = QRect(base_x, base_y, AVATAR_SIZE, AVATAR_SIZE)

		self.place_bottom_right()
		self.__apply_shape()

	@property
	def bubble_text(self) -> str:
		return self.__bubble_text

	def advance(self, delta: float) -> None:
		self.__phase += delta
		self.__elapsed += delta
		if self.__blink > 0:
			self.__blink = max(0.0, self.__blink - delta * 7.0)
		elif self.__elapsed >= self.__next_blink:
			self.__blink = 1.0
			self.__next_blink = self.__elapsed + random.uniform(2.5, 6.0)
		self.update()

	def set_bubble(self, text: str) -> None:
		self.__bubble_text = text
		if not text:
			self.__bubble_rect = QRect()
		else:
			metrics = QFontMetrics(self.__font)
			inner = metrics.boundingRect(
				QRect(0, 0, BUBBLE_MAX_W - 24, 0),
				Qt.TextWordWrap | Qt.AlignLeft,
				text,
			)
			w = max(inner.width() + 24, 70)
			h = inner.height() + 18
			x = self.__avatar_rect.center().x() - w // 2
			x = max(MARGIN, min(x, self.width() - MARGIN - w))
			self.__bubble_rect = QRect(x, self.__avatar_rect.top() - h - 16, w, h)
		self.__apply_shape()
		self.update()

	def on_click(self) -> None:
		self.__env.event_bus.dispatch(EVENT_CLICKED)

	def on_drag_end(self, position: QPoint) -> None:
		self.__env.event_bus.dispatch(EVENT_MOVED, position)

	def on_context_menu(self, global_pos: QPoint) -> None:
		self.show_menu(global_pos, self.menu_actions())

	def menu_actions(self) -> List[Tuple[str, Callable[[], None]]]:
		bus = self.__env.event_bus
		return [
			(item.name, lambda event=item.event: bus.dispatch(event))
			for item in menu_items(self.__env.data_storage)
		]

	def __apply_shape(self) -> None:
		avatar = self.__avatar_rect.adjusted(0, -BOB_AMPLITUDE, 0, BOB_AMPLITUDE)
		region = QRegion(avatar, QRegion.Ellipse)
		if self.__bubble_text:
			region = region.united(QRegion(self.__bubble_rect.adjusted(-2, -2, 2, 14)))
		self.set_shape(region)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.Antialiasing, True)
		painter.setFont(self.__font)
		if self.__bubble_text:
			self.__paint_bubble(painter)
		self.__paint_avatar(painter)

	def __paint_bubble(self, painter) -> None:
		box = QRectF(self.__bubble_rect)
		anchor = min(max(box.center().x(), box.left() + 18), box.right() - 18)
		tail = QPainterPath()
		tail.moveTo(anchor - 9, box.bottom() - 1)
		tail.lineTo(anchor + 2, box.bottom() + 13)
		tail.lineTo(anchor + 9, box.bottom() - 1)
		tail.closeSubpath()

		shape = QPainterPath()
		shape.addRoundedRect(box, 12, 12)
		shape = shape.united(tail)

		painter.setPen(QPen(QColor(30, 34, 44, 90), 1.4))
		painter.setBrush(QColor(252, 252, 254, 242))
		painter.drawPath(shape)

		painter.setPen(QColor(28, 32, 40))
		painter.drawText(
			self.__bubble_rect.adjusted(12, 9, -12, -9),
			Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter,
			self.__bubble_text,
		)

	def __paint_avatar(self, painter) -> None:
		rect = QRectF(self.__avatar_rect).translated(0, math.sin(self.__phase * 1.6) * BOB_AMPLITUDE)

		painter.setPen(Qt.NoPen)
		painter.setBrush(QColor(0, 0, 0, 45))
		painter.drawEllipse(
			QRectF(
				rect.center().x() - rect.width() * 0.28,
				self.__avatar_rect.bottom() - 6,
				rect.width() * 0.56,
				12,
			)
		)

		body = rect.adjusted(6, 6, -6, -6)
		gradient = QRadialGradient(
			body.center().x() - body.width() * 0.2,
			body.center().y() - body.height() * 0.25,
			body.width(),
		)
		gradient.setColorAt(0.0, QColor(126, 214, 255))
		gradient.setColorAt(0.6, QColor(78, 150, 230))
		gradient.setColorAt(1.0, QColor(56, 104, 196))
		painter.setBrush(gradient)
		painter.setPen(QPen(QColor(24, 62, 122, 160), 1.5))
		painter.drawEllipse(body)

		painter.setPen(Qt.NoPen)
		painter.setBrush(QColor(255, 255, 255, 70))
		painter.drawEllipse(
			QRectF(
				body.left() + body.width() * 0.22,
				body.top() + body.height() * 0.12,
				body.width() * 0.3,
				body.height() * 0.18,
			)
		)

		eye_open = 1.0 - self.__blink
		eye_w = body.width() * 0.10
		eye_h = max(body.height() * 0.13 * eye_open, 1.5)
		eye_y = body.center().y() - body.height() * 0.06
		painter.setBrush(QColor(18, 26, 42))
		for dx in (-0.17, 0.17):
			cx = body.center().x() + body.width() * dx
			painter.drawEllipse(QRectF(cx - eye_w / 2, eye_y - eye_h / 2, eye_w, eye_h))

		if eye_open > 0.5:
			painter.setBrush(QColor(255, 255, 255, 220))
			for dx in (-0.17, 0.17):
				cx = body.center().x() + body.width() * dx + eye_w * 0.2
				painter.drawEllipse(
					QRectF(cx - eye_w * 0.16, eye_y - eye_h * 0.28, eye_w * 0.32, eye_h * 0.28)
				)

		painter.setBrush(Qt.NoBrush)
		painter.setPen(QPen(QColor(18, 26, 42), 2.4, Qt.SolidLine, Qt.RoundCap))
		painter.drawArc(
			QRectF(
				body.center().x() - body.width() * 0.16,
				body.center().y() + body.height() * 0.08,
				body.width() * 0.32,
				body.height() * 0.20,
			),
			200 * 16,
			140 * 16,
		)
