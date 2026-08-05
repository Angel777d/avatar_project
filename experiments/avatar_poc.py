import asyncio
import math
import random
import sys

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QRegion,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget
import PySide6.QtAsyncio as QtAsyncio

from angelovich.core.Dispatcher import Dispatcher

EVENT_CLICKED = "avatar.clicked"
EVENT_MOVED = "avatar.moved"
EVENT_SAY = "avatar.say"
EVENT_QUIT = "avatar.quit"

AVATAR_SIZE = 128
BUBBLE_MAX_W = 236
MARGIN = 14
BOB_AMPLITUDE = 5
FRAME_S = 1 / 30
BUBBLE_S = 4.5
IDLE_S = 30.0
DRAG_SLOP = 4

PHRASES = [
    "Still here.",
    "Anything to do?",
    "I like this corner.",
    "Just floating around.",
    "Nice desktop you have.",
    "Poke me if you need me.",
]


class AvatarWidget(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.__bus = bus
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(BUBBLE_MAX_W + 2 * MARGIN, AVATAR_SIZE + 96)

        self.__font = QFont("Segoe UI", 10)
        self.__phase = 0.0
        self.__blink = 0.0
        self.__next_blink = random.uniform(2.0, 5.0)
        self.__elapsed = 0.0
        self.__bubble_text = ""
        self.__bubble_rect = QRect()
        self.__press_global = None
        self.__dragged = False

        base_x = (self.width() - AVATAR_SIZE) // 2
        base_y = self.height() - AVATAR_SIZE - 4
        self.__avatar_rect = QRect(base_x, base_y, AVATAR_SIZE, AVATAR_SIZE)

        self.__place_bottom_right()
        self.__apply_mask()

    def advance(self, delta):
        self.__phase += delta
        self.__elapsed += delta
        if self.__blink > 0:
            self.__blink = max(0.0, self.__blink - delta * 7.0)
        elif self.__elapsed >= self.__next_blink:
            self.__blink = 1.0
            self.__next_blink = self.__elapsed + random.uniform(2.5, 6.0)
        self.update()

    def set_bubble(self, text):
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
        self.__apply_mask()
        self.update()

    def __place_bottom_right(self):
        area = QGuiApplication.primaryScreen().availableGeometry()
        self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 12)

    def __apply_mask(self):
        avatar = self.__avatar_rect.adjusted(0, -BOB_AMPLITUDE, 0, BOB_AMPLITUDE)
        region = QRegion(avatar, QRegion.Ellipse)
        if self.__bubble_text:
            region = region.united(QRegion(self.__bubble_rect.adjusted(-2, -2, 2, 14)))
        self.setMask(region)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.__context_menu(event.globalPosition().toPoint())
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
            self.__bus.dispatch(EVENT_MOVED, self.pos())
        elif self.__press_global is not None:
            self.__bus.dispatch(EVENT_CLICKED)
        self.__press_global = None
        self.__dragged = False

    def __context_menu(self, pos):
        menu = QMenu(self)
        action = QAction("Quit", menu)
        action.triggered.connect(lambda: self.__bus.dispatch(EVENT_QUIT))
        menu.addAction(action)
        menu.exec(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setFont(self.__font)
        if self.__bubble_text:
            self.__paint_bubble(painter)
        self.__paint_avatar(painter)

    def __paint_bubble(self, painter):
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

    def __paint_avatar(self, painter):
        rect = QRectF(self.__avatar_rect).translated(
            0, math.sin(self.__phase * 1.6) * BOB_AMPLITUDE
        )

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
                    QRectF(
                        cx - eye_w * 0.16,
                        eye_y - eye_h * 0.28,
                        eye_w * 0.32,
                        eye_h * 0.28,
                    )
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


class AvatarBehavior:
    def __init__(self, bus, widget):
        self.__bus = bus
        self.__widget = widget
        self.__bubble_task = None
        self.__poked = asyncio.Event()
        bus.add_listener(EVENT_CLICKED, self.on_clicked, self)
        bus.add_listener(EVENT_SAY, self.on_say, self)

    async def on_clicked(self):
        self.__poked.set()
        await self.on_say("Hello!")

    async def on_say(self, text):
        if self.__bubble_task and not self.__bubble_task.done():
            self.__bubble_task.cancel()
        self.__bubble_task = asyncio.create_task(self.__bubble(text))

    async def __bubble(self, text):
        self.__widget.set_bubble(text)
        try:
            await asyncio.sleep(BUBBLE_S)
        except asyncio.CancelledError:
            raise
        self.__widget.set_bubble("")

    async def run_idle(self):
        while True:
            try:
                await asyncio.wait_for(self.__poked.wait(), IDLE_S)
                self.__poked.clear()
            except TimeoutError:
                self.__bus.dispatch(EVENT_SAY, random.choice(PHRASES))


async def animate(widget):
    while True:
        widget.advance(FRAME_S)
        await asyncio.sleep(FRAME_S)


async def main():
    bus = Dispatcher()
    widget = AvatarWidget(bus)
    behavior = AvatarBehavior(bus, widget)

    stopping = asyncio.Event()

    async def on_quit():
        stopping.set()

    async def on_moved(pos):
        print(f"moved to {pos.x()}, {pos.y()}")

    bus.add_listener(EVENT_QUIT, on_quit, "main")
    bus.add_listener(EVENT_MOVED, on_moved, "main")

    widget.show()

    workers = [
        asyncio.create_task(animate(widget)),
        asyncio.create_task(behavior.run_idle()),
    ]
    await stopping.wait()
    for task in workers:
        task.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
    QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    QtAsyncio.run(main(), keep_running=True, handle_sigint=True)
