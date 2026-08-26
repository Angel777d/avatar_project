import asyncio
import logging

from avatar_api import Env
from avatar_core.application import Application

LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"


def main() -> int:
	logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

	env = Env()
	application = Application(env)
	asyncio.run(application.run())
	return env.exit_code
