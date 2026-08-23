import json
import logging
import os
import sys
from importlib import metadata
from pathlib import Path
from typing import Dict, List, Optional

from avatar_api import Env, System, events

logger = logging.getLogger(__name__)

WORKSPACE_VAR = "SUPERVISOR_WORKSPACE"

PLUGINS_FILE = "plugins.json"
REQUEST_FILE = "request.json"
REPLY_FILE = "reply.json"


def loaded_distributions() -> List[str]:
	mapping = metadata.packages_distributions()
	found = set()
	for module in list(sys.modules):
		for name in mapping.get(module.split(".")[0], ()):
			found.add(name)
	return sorted(found)


def read_json(path: Path) -> Optional[dict]:
	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return None


def write_json(path: Path, payload: dict) -> None:
	temp = path.with_suffix(path.suffix + ".tmp")
	temp.write_text(json.dumps(payload, indent="\t"), encoding="utf-8")
	os.replace(temp, path)


class SupervisorSystem(System):
	"""The only thing that talks to the supervisor. Everything else asks through the bus."""

	def __init__(self, env: Env):
		super().__init__(env)
		self.__workspace: Optional[Path] = None
		self.__revision = 0
		self.__requirements: List[str] = []
		self.__waiting = 0
		self.__stamp: Optional[float] = None
		self.__status: Dict = {"busy": False, "step": "", "applied": [], "deferred": [],
		                       "failed": [], "restart": False, "error": ""}

	async def start(self):
		self.__workspace = self.__resolve()
		self.env.workspace = self.__workspace

		if self.__workspace is None:
			logger.info("no supervisor workspace, plugin changes are unavailable")
		else:
			logger.info("supervisor workspace at %s", self.__workspace)
			self.__read()

		self.add_listener(events.REQUEST_PLUGINS_APPLY, self.__on_apply)
		await self.__announce()

	async def _update(self, delta_time: float):
		if self.__workspace is None or self.__waiting == 0:
			return
		await self.__poll()

	@property
	def available(self) -> bool:
		return self.__workspace is not None

	def __resolve(self) -> Optional[Path]:
		named = os.environ.get(WORKSPACE_VAR, "").strip()
		if not named:
			return None
		path = Path(named)
		return path if path.is_dir() else None

	def __read(self) -> None:
		payload = read_json(self.__workspace / PLUGINS_FILE) or {}
		self.__revision = int(payload.get("revision", 0))
		self.__requirements = [str(entry) for entry in payload.get("requirements", [])]

	async def __on_apply(self, requirements: List[str]):
		if self.__workspace is None:
			self.__status |= {"error": "no supervisor is running this app", "busy": False}
			await self.__announce()
			return

		wanted = [str(entry).strip() for entry in requirements if str(entry).strip()]
		self.__revision += 1
		self.__waiting = self.__revision

		# The desired state reaches disk before anything is asked to act on it.
		write_json(self.__workspace / PLUGINS_FILE,
		           {"revision": self.__revision, "requirements": wanted})
		write_json(self.__workspace / REQUEST_FILE,
		           {"op": "reconcile", "revision": self.__revision, "loaded": loaded_distributions()})

		self.__requirements = wanted
		self.__status = {"busy": True, "step": "Asking the supervisor", "applied": [],
		                 "deferred": [], "failed": [], "restart": False, "error": ""}
		logger.info("asked the supervisor for revision %d, %d requirement(s)", self.__revision, len(wanted))
		await self.__announce()

	async def __poll(self) -> None:
		path = self.__workspace / REPLY_FILE
		try:
			stamp = path.stat().st_mtime
		except OSError:
			return
		if stamp == self.__stamp:
			return
		self.__stamp = stamp

		reply = read_json(path)
		if reply is None or int(reply.get("revision", -1)) != self.__waiting:
			return

		done = str(reply.get("state", "")) == "done"
		self.__status = {
			"busy": not done,
			"step": str(reply.get("step", "")),
			"applied": list(reply.get("applied", [])),
			"deferred": list(reply.get("deferred", [])),
			"failed": list(reply.get("failed", [])),
			"restart": bool(reply.get("restart", False)),
			"error": str(reply.get("error", "")),
		}

		if done:
			self.__waiting = 0
			self.__read()
			logger.info("supervisor applied %d, deferred %d, failed %d",
			            len(self.__status["applied"]), len(self.__status["deferred"]),
			            len(self.__status["failed"]))

		await self.__announce()

	async def __announce(self) -> None:
		await self.env.event_bus.dispatch_async(events.ACTION_PLUGINS_CHANGED, {
			"available": self.__workspace is not None,
			"revision": self.__revision,
			"requirements": list(self.__requirements),
			**self.__status,
		})
