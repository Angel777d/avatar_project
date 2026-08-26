import asyncio
import ctypes
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

WORKSPACE = Path(__file__).resolve().parent

CONFIG = WORKSPACE / "config.json"
PLUGINS = WORKSPACE / "plugins.json"
STATE = WORKSPACE / "state.json"
LOG = WORKSPACE / "supervisor.log"

UV = WORKSPACE / "uv" / "uv.exe"
PYTHON_DIR = WORKSPACE / "python"
CACHE_DIR = WORKSPACE / "cache"
VENV = WORKSPACE / ".venv"
VENV_PYTHON = VENV / "Scripts" / "pythonw.exe"

RESTART_CODE = 75
HOST = "127.0.0.1"

NAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
PINNED = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?==[A-Za-z0-9][A-Za-z0-9.*+!_-]*$")
DIRECT = re.compile(r"^(?P<name>[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)\s+@\s+(?P<url>\S+)$")

logger = logging.getLogger("supervisor")


def setup_logging() -> None:
	handler = RotatingFileHandler(LOG, maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
	handler.setFormatter(logging.Formatter("%(asctime)s %(name)-5s | %(message)s", "%Y-%m-%d %H:%M:%S"))
	logging.basicConfig(level=logging.INFO, handlers=[handler])


def read_json(path: Path) -> Optional[dict]:
	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return None


def write_json(path: Path, payload: dict) -> None:
	temp = path.with_suffix(path.suffix + ".tmp")
	temp.write_text(json.dumps(payload, indent="\t"), encoding="utf-8")
	os.replace(temp, path)


def requirement_name(requirement: str) -> str:
	direct = DIRECT.match(requirement.strip())
	text = direct.group("name") if direct else requirement.strip().split("==")[0]
	return text.strip().lower().replace("_", "-").replace(".", "-")


def validate(requirement: str) -> Optional[str]:
	text = requirement.strip()
	if not text:
		return "empty requirement"
	if "\n" in requirement or "\r" in requirement:
		return "requirement contains a line break"
	if text.startswith("-"):
		return "requirement starts with a dash, which is an option and not a package"

	direct = DIRECT.match(text)
	if direct:
		url = direct.group("url")
		if not url.startswith("https://github.com/"):
			return f"{url} is not an allowed source"
		return None
	if PINNED.match(text) or NAME.match(text):
		return None
	return f"{text} is not a package"


class Config:
	def __init__(self, payload: dict):
		app = payload.get("app") or {}
		self.python: str = str(payload.get("python", "3.13"))
		self.port: int = int(payload.get("port", 0))
		self.packages: List[str] = [str(p) for p in payload.get("packages", [])]
		self.module: str = str(app.get("module", "avatar_core"))
		self.restarts: int = int(app.get("restarts", 3))
		self.window: float = float(app.get("window", 60))
		self.backoff: float = float(app.get("backoff", 2))

	def problem(self) -> Optional[str]:
		if not self.port:
			return "no port configured"
		if not self.packages:
			return "no packages configured"
		if not self.module:
			return "no app module configured"
		return None


def uv_environment() -> dict:
	environment = dict(os.environ)
	environment["UV_PYTHON_INSTALL_DIR"] = str(PYTHON_DIR)
	environment["UV_CACHE_DIR"] = str(CACHE_DIR)
	environment["UV_PYTHON_INSTALL_BIN"] = "0"
	environment["UV_NO_PROGRESS"] = "1"
	return environment


def run_uv(*arguments: str) -> Tuple[int, str]:
	try:
		done = subprocess.run(
			[str(UV), *arguments],
			cwd=str(WORKSPACE), env=uv_environment(),
			capture_output=True, text=True, encoding="utf-8", errors="replace",
			creationflags=subprocess.CREATE_NO_WINDOW,
		)
	except OSError as ex:
		logger.error("cannot run uv: %s", ex)
		return -1, f"{ex}"

	output = (done.stdout or "") + (done.stderr or "")
	for line in output.splitlines():
		if line.strip():
			logger.info("uv | %s", line.rstrip())
	return done.returncode, output


class Packages:
	"""The venv is brought to match config.packages plus plugins.json."""

	def __init__(self, config: Config):
		self.__config = config

	def desired(self) -> List[str]:
		wanted = list(self.__config.packages)
		payload = read_json(PLUGINS)
		entries = payload if isinstance(payload, list) else (payload or {}).get("packages", [])
		for entry in entries or []:
			requirement = str(entry).strip()
			problem = validate(requirement)
			if problem:
				logger.error("refused %r: %s", requirement, problem)
				continue
			wanted.append(requirement)
		return wanted

	@staticmethod
	def recorded() -> List[str]:
		payload = read_json(STATE) or {}
		return [str(p) for p in payload.get("packages", [])]

	@staticmethod
	def record(packages: Sequence[str]) -> None:
		write_json(STATE, {"packages": list(packages)})

	def reconcile(self, clean: bool = False) -> Dict[str, list]:
		wanted = self.desired()
		known = self.recorded()

		if not clean and VENV.exists() and sorted(wanted) == sorted(known):
			return {"installed": [], "removed": [], "failed": []}

		if clean and VENV.exists():
			logger.info("clearing the environment")
			shutil.rmtree(VENV, ignore_errors=True)

		if not VENV.exists():
			code, _ = run_uv("venv", str(VENV), "--python", self.__config.python)
			if code != 0:
				return {"installed": [], "removed": [], "failed": list(wanted)}
			known = []

		result: Dict[str, list] = {"installed": [], "removed": [], "failed": []}

		gone = self.__dropped(known, wanted)
		if gone:
			code, output = run_uv("pip", "uninstall", "--python", str(VENV_PYTHON), *gone)
			if code == 0:
				result["removed"] = gone
			else:
				result["failed"].extend(gone)
				logger.error("could not remove %s", ", ".join(gone))

		code, output = run_uv("pip", "install", "--python", str(VENV_PYTHON), *wanted)
		if code != 0:
			result["failed"].extend(n for n in self.__added(known, wanted) if n not in result["failed"])
			logger.error("install failed, keeping the recorded set")
			return result

		result["installed"] = self.__added(known, wanted)
		if not result["failed"]:
			self.record(wanted)
		return result

	@staticmethod
	def __dropped(known: Sequence[str], wanted: Sequence[str]) -> List[str]:
		"""Only ever what a previous run installed on purpose - the rest is a dependency."""
		names = {requirement_name(r) for r in wanted}
		return sorted({requirement_name(r) for r in known} - names)

	@staticmethod
	def __added(known: Sequence[str], wanted: Sequence[str]) -> List[str]:
		names = {requirement_name(r) for r in known}
		return sorted({requirement_name(r) for r in wanted} - names)


class Job:
	"""Children die with the supervisor, however it dies."""

	LIMIT_KILL_ON_CLOSE = 0x2000
	EXTENDED_LIMIT = 9

	def __init__(self):
		self.__handle = None
		try:
			kernel = ctypes.windll.kernel32
			handle = kernel.CreateJobObjectW(None, None)
			if not handle:
				return

			class BasicLimit(ctypes.Structure):
				_fields_ = [
					("PerProcessUserTimeLimit", ctypes.c_int64),
					("PerJobUserTimeLimit", ctypes.c_int64),
					("LimitFlags", ctypes.c_uint32),
					("MinimumWorkingSetSize", ctypes.c_size_t),
					("MaximumWorkingSetSize", ctypes.c_size_t),
					("ActiveProcessLimit", ctypes.c_uint32),
					("Affinity", ctypes.c_size_t),
					("PriorityClass", ctypes.c_uint32),
					("SchedulingClass", ctypes.c_uint32),
				]

			class IoCounters(ctypes.Structure):
				_fields_ = [(name, ctypes.c_uint64) for name in (
					"ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
					"ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

			class ExtendedLimit(ctypes.Structure):
				_fields_ = [
					("BasicLimitInformation", BasicLimit),
					("IoInfo", IoCounters),
					("ProcessMemoryLimit", ctypes.c_size_t),
					("JobMemoryLimit", ctypes.c_size_t),
					("PeakProcessMemoryUsed", ctypes.c_size_t),
					("PeakJobMemoryUsed", ctypes.c_size_t),
				]

			information = ExtendedLimit()
			information.BasicLimitInformation.LimitFlags = self.LIMIT_KILL_ON_CLOSE
			kernel.SetInformationJobObject(
				handle, self.EXTENDED_LIMIT, ctypes.byref(information), ctypes.sizeof(information))
			self.__handle = handle
		except (AttributeError, OSError) as ex:
			logger.error("no job object, the app can outlive the supervisor: %s", ex)

	def add(self, pid: int) -> None:
		if self.__handle is None:
			return
		kernel = ctypes.windll.kernel32
		process = kernel.OpenProcess(0x1F0FFF, False, pid)
		if not process:
			return
		try:
			if not kernel.AssignProcessToJobObject(self.__handle, process):
				logger.error("could not tie the app to the supervisor")
		finally:
			kernel.CloseHandle(process)


class Supervisor:
	def __init__(self, config: Config):
		self.__config = config
		self.__packages = Packages(config)
		self.__job = Job()
		self.__process: Optional[asyncio.subprocess.Process] = None
		self.__pending: Optional[str] = None
		self.__closing = False

	async def run(self) -> int:
		server = await asyncio.start_server(self.__serve, HOST, self.__config.port)
		logger.info("listening on %s:%d", HOST, self.__config.port)

		try:
			return await self.__supervise()
		finally:
			server.close()

	async def __supervise(self) -> int:
		failures: List[float] = []
		backoff = self.__config.backoff
		loop = asyncio.get_running_loop()

		while True:
			action, self.__pending = self.__pending, None
			outcome = await asyncio.to_thread(self.__packages.reconcile, action == "clean")
			if outcome["failed"]:
				logger.error("environment incomplete: %s", ", ".join(outcome["failed"]))

			started = loop.time()
			code = await self.__start_app()
			alive = loop.time() - started

			if self.__closing:
				return 0
			if code == 0:
				logger.info("app closed")
				return 0
			if code == RESTART_CODE:
				logger.info("app asked to be restarted")
				continue

			if alive > self.__config.window:
				failures.clear()
				backoff = self.__config.backoff

			failures.append(loop.time())
			failures[:] = [f for f in failures if loop.time() - f <= self.__config.window]
			if len(failures) > self.__config.restarts:
				logger.error("app failed %d times in %.0fs, giving up", len(failures), self.__config.window)
				return code

			logger.info("app exited with %s, restart %d of %d in %.0fs",
			            code, len(failures), self.__config.restarts, backoff)
			await asyncio.sleep(backoff)
			backoff = min(backoff * 2, 60)

	async def __start_app(self) -> int:
		environment = dict(os.environ)
		environment["SUPERVISOR_WORKSPACE"] = str(WORKSPACE)
		environment["PYTHONIOENCODING"] = "utf-8"

		try:
			self.__process = await asyncio.create_subprocess_exec(
				str(VENV_PYTHON), "-u", "-m", self.__config.module,
				cwd=str(WORKSPACE), env=environment,
				stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
				creationflags=subprocess.CREATE_NO_WINDOW,
			)
		except OSError as ex:
			logger.error("cannot start the app: %s", ex)
			return -1

		self.__job.add(self.__process.pid)
		await self.__drain(self.__process.stdout)
		code = await self.__process.wait()
		self.__process = None
		return code

	@staticmethod
	async def __drain(stream) -> None:
		async for line in stream:
			text = line.decode("utf-8", "replace").rstrip()
			if text:
				logger.info("app | %s", text)

	async def __serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
		try:
			async for line in reader:
				if not line.strip():
					continue
				try:
					request = json.loads(line)
				except ValueError:
					continue
				reply = await self.__handle(request if isinstance(request, dict) else {})
				writer.write(json.dumps(reply).encode("utf-8") + b"\n")
				await writer.drain()
		except (ConnectionError, OSError):
			pass
		finally:
			writer.close()

	async def __handle(self, request: dict) -> dict:
		if request.get("op") != "reconcile":
			return {"op": "error", "error": "unknown request"}

		action = str(request.get("action", "")).strip().lower()
		if action in ("restart", "clean"):
			self.__pending = action
			logger.info("reconcile deferred to a %s", action)
			return {"op": "done", "installed": [], "removed": [], "failed": [], "action": action}

		logger.info("reconcile while the app runs")
		outcome = await asyncio.to_thread(self.__packages.reconcile, False)
		return {"op": "done", **outcome}

	def stop(self) -> None:
		self.__closing = True
		process = self.__process
		if process is not None and process.returncode is None:
			process.terminate()


def main() -> int:
	setup_logging()

	payload = read_json(CONFIG)
	if payload is None:
		logger.error("cannot read %s", CONFIG)
		return 2

	config = Config(payload)
	problem = config.problem()
	if problem:
		logger.error("cannot start: %s", problem)
		return 2

	if not UV.exists():
		logger.error("no uv at %s, run the installer again", UV)
		return 2

	logger.info("supervisor start in %s", WORKSPACE)
	supervisor = Supervisor(config)
	try:
		return asyncio.run(supervisor.run())
	except OSError as ex:
		logger.error("cannot listen on %d, another supervisor owns this workspace: %s",
		             config.port, ex)
		return 0
	except KeyboardInterrupt:
		supervisor.stop()
		return 0


if __name__ == "__main__":
	raise SystemExit(main())
