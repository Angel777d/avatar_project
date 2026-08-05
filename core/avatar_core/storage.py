import asyncio
import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from avatar_api import Env
from avatar_api.components import StaticIdEC
from avatar_api.registry import NAME_FIELD

logger = logging.getLogger(__name__)

APP_FOLDER = "avatar_project"
DB_NAME = "avatar.db"
TABLE = "core_entities"


def default_path() -> Path:
	root = os.environ.get("LOCALAPPDATA") or Path.home()
	return Path(root) / APP_FOLDER / DB_NAME


class Storage:
	def __init__(self, path: Optional[Path] = None):
		self.path: Path = Path(path) if path else default_path()
		self.__connection: Optional[sqlite3.Connection] = None
		self.__unreadable: Set[str] = set()
		self.__unknown: Dict[str, List[dict]] = {}

	async def open(self) -> None:
		await asyncio.to_thread(self.__open)

	async def close(self) -> None:
		if self.__connection is not None:
			await asyncio.to_thread(self.__close)

	async def load(self, env: Env) -> int:
		rows = await asyncio.to_thread(self.__read)
		self.__unreadable.clear()
		self.__unknown.clear()
		restored = 0
		for static_id, raw in rows:
			if self.__restore(env, static_id, raw):
				restored += 1
		return restored

	async def save(self, env: Env) -> int:
		rows = []
		for entity in env.data_storage.get_collection(StaticIdEC):
			static_id = entity.get_component(StaticIdEC).static_id
			payloads = env.registry.encode_entity(entity)
			kept = self.__unknown.get(static_id)
			if kept:
				live = {payload[NAME_FIELD] for payload in payloads}
				payloads = payloads + [p for p in kept if p.get(NAME_FIELD) not in live]
			rows.append((static_id, json.dumps(payloads)))
		await asyncio.to_thread(self.__write, rows)
		return len(rows)

	def __open(self) -> None:
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self.__connection = sqlite3.connect(self.path)
		self.__connection.execute("pragma journal_mode=wal")
		self.__connection.execute(
			f"create table if not exists {TABLE} (static_id text primary key, data text not null)"
		)
		self.__connection.commit()

	def __close(self) -> None:
		self.__connection.execute("pragma wal_checkpoint(truncate)")
		self.__connection.close()
		self.__connection = None

	def __read(self) -> List[Tuple[str, str]]:
		return self.__connection.execute(f"select static_id, data from {TABLE}").fetchall()

	def __write(self, rows: Sequence[Tuple[str, str]]) -> None:
		keep = [static_id for static_id, _ in rows] + sorted(self.__unreadable)
		with self.__connection as connection:
			connection.executemany(
				f"insert into {TABLE} (static_id, data) values (?, ?) "
				f"on conflict(static_id) do update set data = excluded.data",
				rows,
			)
			if keep:
				marks = ",".join("?" * len(keep))
				connection.execute(f"delete from {TABLE} where static_id not in ({marks})", keep)
			else:
				connection.execute(f"delete from {TABLE}")

	def __restore(self, env: Env, static_id: str, raw: str) -> bool:
		try:
			payloads = json.loads(raw)
		except json.JSONDecodeError:
			logger.error("entity %s is not readable, left untouched", static_id)
			self.__unreadable.add(static_id)
			return False

		components = []
		kept = []
		for payload in payloads:
			component = env.registry.decode(payload)
			if component is None:
				kept.append(payload)
			else:
				components.append(component)

		if kept:
			logger.warning("entity %s carries %d unregistered types, kept as stored", static_id, len(kept))
			self.__unknown[static_id] = kept
		if not any(isinstance(component, StaticIdEC) for component in components):
			return False

		entity = env.data_storage.create_entity()
		for component in components:
			entity.add_component(component)
		return True
