import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow
import PySide6.QtAsyncio as QtAsyncio

from angelovich.core.Dispatcher import Dispatcher

HERE = Path(__file__).resolve().parent
PAGE = HERE / "html_window_poc.html"
STORE = HERE / ".board.json"

EVENT_MOVE = "board.move"
EVENT_ADD = "board.add"
EVENT_DELETE = "board.delete"
EVENT_RESET = "board.reset"

DEFAULT_BOARD = {
    "columns": [
        {
            "id": "todo",
            "name": "To do",
            "cards": [
                {"id": "seed-1", "title": "Pick the UI layer", "created": ""},
                {"id": "seed-2", "title": "Define plugin API", "created": ""},
            ],
        },
        {
            "id": "doing",
            "name": "Doing",
            "cards": [{"id": "seed-3", "title": "HTML window PoC", "created": ""}],
        },
        {
            "id": "done",
            "name": "Done",
            "cards": [{"id": "seed-4", "title": "Avatar PoC", "created": ""}],
        },
    ]
}


def await_signal(signal):
    future = asyncio.get_running_loop().create_future()

    def handler(*args):
        signal.disconnect(handler)
        if not future.done():
            future.set_result(args[0] if len(args) == 1 else args)

    signal.connect(handler)
    return future


def eval_js(page, script):
    future = asyncio.get_running_loop().create_future()
    page.runJavaScript(
        script, lambda value: future.done() or future.set_result(value)
    )
    return future


class Board(QObject):
    changed = Signal()

    def __init__(self, bus):
        super().__init__()
        self.__bus = bus
        self.__data = json.loads(json.dumps(DEFAULT_BOARD))
        bus.add_listener(EVENT_MOVE, self.__on_move, self)
        bus.add_listener(EVENT_ADD, self.__on_add, self)
        bus.add_listener(EVENT_DELETE, self.__on_delete, self)
        bus.add_listener(EVENT_RESET, self.__on_reset, self)

    async def load(self):
        if not STORE.exists():
            return
        try:
            raw = await asyncio.to_thread(STORE.read_text, encoding="utf-8")
            self.__data = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            pass

    async def __commit(self):
        payload = json.dumps(self.__data, indent=2)
        await asyncio.to_thread(STORE.write_text, payload, encoding="utf-8")
        self.changed.emit()

    def __column(self, column_id):
        for column in self.__data["columns"]:
            if column["id"] == column_id:
                return column
        return None

    def __take(self, card_id):
        for column in self.__data["columns"]:
            for index, card in enumerate(column["cards"]):
                if card["id"] == card_id:
                    return column["cards"].pop(index)
        return None

    async def __on_move(self, card_id, column_id, position):
        target = self.__column(column_id)
        if target is None:
            return
        card = self.__take(card_id)
        if card is None:
            return
        target["cards"].insert(max(0, min(position, len(target["cards"]))), card)
        await self.__commit()

    async def __on_add(self, column_id, title):
        title = title.strip()
        target = self.__column(column_id)
        if not title or target is None:
            return
        target["cards"].append(
            {
                "id": uuid.uuid4().hex[:8],
                "title": title,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )
        await self.__commit()

    async def __on_delete(self, card_id):
        if self.__take(card_id) is not None:
            await self.__commit()

    async def __on_reset(self):
        self.__data = json.loads(json.dumps(DEFAULT_BOARD))
        await self.__commit()

    @Slot(result=str)
    def snapshot(self):
        return json.dumps(self.__data)

    @Slot(str, str, int)
    def move_card(self, card_id, column_id, position):
        self.__bus.dispatch(EVENT_MOVE, card_id, column_id, position)

    @Slot(str, str)
    def add_card(self, column_id, title):
        self.__bus.dispatch(EVENT_ADD, column_id, title)

    @Slot(str)
    def delete_card(self, card_id):
        self.__bus.dispatch(EVENT_DELETE, card_id)

    @Slot()
    def reset(self):
        self.__bus.dispatch(EVENT_RESET)


class BoardWindow(QMainWindow):
    def __init__(self, board):
        super().__init__()
        self.setWindowTitle("Kanban (async, HTML + QWebChannel)")
        self.resize(940, 620)

        self.view = QWebEngineView(self)
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("board", board)
        self.view.page().setWebChannel(self.channel)
        self.setCentralWidget(self.view)

    async def load(self):
        ready = await_signal(self.view.loadFinished)
        self.view.load(QUrl.fromLocalFile(str(PAGE)))
        return await ready

    async def run_status(self):
        started = datetime.now()
        while True:
            uptime = int((datetime.now() - started).total_seconds())
            await eval_js(
                self.view.page(),
                f"window.setStatus && window.setStatus('core alive · {uptime}s')",
            )
            await asyncio.sleep(1)


async def main():
    bus = Dispatcher()
    board = Board(bus)
    await board.load()

    window = BoardWindow(board)
    window.show()
    await window.load()

    status = asyncio.create_task(window.run_status())
    closed = await_signal(window.view.page().windowCloseRequested)
    try:
        await closed
    finally:
        status.cancel()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    QtAsyncio.run(main(), keep_running=True, handle_sigint=True)
