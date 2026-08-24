import asyncio
import logging

from avatar_core.application import Application
from avatar_api.env import Env

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main():
	env = Env()
	application = Application(env, tick_time=0.5)
	asyncio.run(application.run())


if __name__ == "__main__":
	main()
