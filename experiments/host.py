import logging
import sys

from PySide6.QtWidgets import QApplication
import PySide6.QtAsyncio as QtAsyncio

from avatar_core.application import Application
from avatar_api.env import Env

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def run(application: Application, qapp: QApplication):
	await application.run()
	qapp.quit()


def main():
	qapp = QApplication(sys.argv)
	qapp.setQuitOnLastWindowClosed(False)
	env = Env()
	application = Application(env, tick_time=0.5)
	QtAsyncio.run(run(application, qapp), keep_running=True, handle_sigint=True)


if __name__ == "__main__":
	main()
