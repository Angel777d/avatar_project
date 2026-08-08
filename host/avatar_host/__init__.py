import asyncio
import logging
import sys

from PySide6.QtWidgets import QApplication
import PySide6.QtAsyncio as QtAsyncio

from avatar_api import Env
from avatar_core.application import Application

LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"


async def _run(application: Application, qapp: QApplication) -> None:
	await application.run()
	qapp.quit()


def main() -> int:
	logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

	qapp = QApplication(sys.argv)
	qapp.setQuitOnLastWindowClosed(False)

	env = Env()
	env.close_event = asyncio.Event()
	qapp.aboutToQuit.connect(env.close_event.set)

	application = Application(env)
	QtAsyncio.run(_run(application, qapp), keep_running=True, handle_sigint=True)
	return 0
