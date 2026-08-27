import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from avatar_api import Env, System, events

logger = logging.getLogger(__name__)

WORKSPACE_VAR = "SUPERVISOR_WORKSPACE"

CONFIG_FILE = "config.json"
PLUGINS_FILE = "plugins.json"

HOST = "127.0.0.1"
TIMEOUT = 600
RESTART_CODE = 75

IDLE: Dict = {"busy": False, "step": "", "applied": [], "deferred": [],
              "failed": [], "restart": False, "error": ""}


def read_json(path: Path):
	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return None


def write_json(path: Path, payload) -> None:
	temp = path.with_suffix(path.suffix + ".tmp")
	temp.write_text(json.dumps(payload, indent="\t"), encoding="utf-8")
	os.replace(temp, path)


class SupervisorSystem(System):
	"""The only thing that talks to the supervisor. Everything else asks through the bus."""

	def __init__(self, env: Env):
		super().__init__(env)
		self.__workspace: Optional[Path] = None
		self.__port = 0
		self.__requirements: List[str] = []
		self.__status: Dict = dict(IDLE)

		self.add_listener(events.REQUEST_PLUGINS_APPLY, self.__on_apply)

	async def start(self):
		self.__workspace = self.__resolve()
		self.env.workspace = self.__workspace

		if self.__workspace is None:
			logger.info("no supervisor workspace, plugin changes are unavailable")
		else:
			self.__port = self.__read_port()
			self.__requirements = self.__read_plugins()
			logger.info("supervisor workspace at %s, port %d", self.__workspace, self.__port)

		await self.__announce()

	@property
	def available(self) -> bool:
		return self.__workspace is not None and self.__port > 0

	def __resolve(self) -> Optional[Path]:
		named = os.environ.get(WORKSPACE_VAR, "").strip()
		if not named:
			return None
		path = Path(named)
		return path if path.is_dir() else None

	def __config(self) -> dict:
		return read_json(self.__workspace / CONFIG_FILE) or {}

	def __read_port(self) -> int:
		try:
			return int(self.__config().get("port", 0))
		except (TypeError, ValueError):
			return 0

	def __read_plugins(self) -> List[str]:
		payload = read_json(self.__workspace / PLUGINS_FILE)
		if isinstance(payload, list):
			return [str(entry) for entry in payload]
		return [str(entry) for entry in self.__config().get("plugins", [])]

	async def __on_apply(self, requirements: List[str], action: str = ""):
		if not self.available:
			self.__status = {**IDLE, "error": "no supervisor is running this app"}
			await self.__announce()
			return

		wanted = [str(entry).strip() for entry in requirements if str(entry).strip()]
		write_json(self.__workspace / PLUGINS_FILE, wanted)
		self.__requirements = wanted

		self.__status = {**IDLE, "busy": True, "step": "Asking the supervisor"}
		await self.__announce()

		logger.info("asked the supervisor for %d requirement(s)%s",
		            len(wanted), f" and a {action}" if action else "")
		reply = await self.__ask(action)

		if reply is None:
			self.__status = {**IDLE, "error": "the supervisor did not answer"}
			await self.__announce()
			return

		if reply.get("op") == "error":
			self.__status = {**IDLE, "error": str(reply.get("error", "refused"))}
			await self.__announce()
			return

		installed = [str(name) for name in reply.get("installed", [])]
		removed = [str(name) for name in reply.get("removed", [])]
		failed = [str(name) for name in reply.get("failed", [])]
		deferred = wanted if reply.get("action") else []

		self.__status = {
			"busy": False,
			"step": "",
			"applied": installed,
			"removed": removed,
			"deferred": deferred,
			"failed": failed,
			"restart": bool(reply.get("action")),
			"error": "",
		}
		logger.info("supervisor installed %d, removed %d, failed %d",
		            len(installed), len(removed), len(failed))
		await self.__announce()

		if reply.get("action"):
			await self.__stand_aside()

	async def __ask(self, action: str) -> Optional[dict]:
		request: Dict = {"op": "reconcile"}
		if action:
			request["action"] = action

		try:
			reader, writer = await asyncio.open_connection(HOST, self.__port)
		except OSError as ex:
			logger.error("cannot reach the supervisor on %d: %s", self.__port, ex)
			return None

		try:
			writer.write(json.dumps(request).encode("utf-8") + b"\n")
			await writer.drain()
			line = await asyncio.wait_for(reader.readline(), TIMEOUT)
		except (asyncio.TimeoutError, ConnectionError, OSError) as ex:
			logger.error("the supervisor stopped answering: %s", ex)
			return None
		finally:
			writer.close()

		if not line:
			return None
		try:
			answer = json.loads(line)
		except ValueError:
			return None
		return answer if isinstance(answer, dict) else None

	async def __stand_aside(self) -> None:
		"""The supervisor reconciles with nothing running, so this process gets out of the way."""
		logger.info("closing so the supervisor can finish")
		self.env.exit_code = RESTART_CODE
		await self.env.event_bus.dispatch_async(events.REQUEST_APP_CLOSE)

	async def __announce(self) -> None:
		await self.env.event_bus.dispatch_async(events.ACTION_PLUGINS_CHANGED, {
			"available": self.available,
			"requirements": list(self.__requirements),
			**self.__status,
		})
