import asyncio
import json
import logging
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from avatar_api import Env
from avatar_api.components import StaticIdEC
from avatar_api.migrations import MigrationRegistry, component_tables, table_of
from avatar_api.registry import NAME_FIELD

logger = logging.getLogger(__name__)

APP_FOLDER = "avatar_project"
DB_NAME = "avatar.db"

SCHEMA_TABLE = "core_schema"


def default_path() -> Path:
	root = os.environ.get("LOCALAPPDATA") or Path.home()
	return Path(root) / APP_FOLDER / DB_NAME


class Storage:
	def __init__(self, path: Optional[Path] = None):
		self.path: Path = Path(path) if path else default_path()
		self.__connection: Optional[sqlite3.Connection] = None
		self.__known: Set[str] = set()
		self.__protected: Dict[str, Set[str]] = {}
		self.__thread: Optional[ThreadPoolExecutor] = None

	async def __on_thread(self, work, *args):
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor(self.__thread, partial(work, *args))

	async def open(self) -> None:
		# a sqlite connection belongs to the thread that opened it, so every call gets that one
		self.__thread = ThreadPoolExecutor(max_workers=1, thread_name_prefix="avatar-storage")
		await self.__on_thread(self.__open)

	async def close(self) -> None:
		if self.__connection is not None:
			await self.__on_thread(self.__close)
		if self.__thread is not None:
			self.__thread.shutdown(wait=True)
			self.__thread = None

	async def load(self, env: Env) -> int:
		await self.__on_thread(self.__migrate, env.migrations)

		names = self.__registered(env)
		rows = await self.__on_thread(self.__read, names)

		self.__protected.clear()
		components: Dict[str, list] = {}
		for name, table_rows in rows.items():
			for static_id, raw in table_rows:
				component = self.__decode(env, name, static_id, raw)
				if component is not None:
					components.setdefault(static_id, []).append(component)

		for static_id, parts in components.items():
			entity = env.data_storage.create_entity()
			entity.add_component(StaticIdEC(static_id))
			for component in parts:
				entity.add_component(component)

		self.__known = set(components)
		return len(components)

	async def save(self, env: Env) -> int:
		live: Dict[str, List[Tuple[str, str]]] = {}
		live_ids: Set[str] = set()

		for entity in env.data_storage.get_collection(StaticIdEC):
			static_id = entity.get_component(StaticIdEC).static_id
			live_ids.add(static_id)
			for component_type in env.registry.types:
				if component_type is StaticIdEC or not entity.has_component(component_type):
					continue
				payload = env.registry.encode(entity.get_component(component_type))
				if payload is None:
					continue
				name = payload[NAME_FIELD]
				live.setdefault(name, []).append((static_id, json.dumps(payload)))

		removed = self.__known - live_ids
		await self.__on_thread(self.__write, live, self.__registered(env), removed)
		self.__known = live_ids
		return len(live_ids)

	def __registered(self, env: Env) -> List[str]:
		return [
			env.registry.name_of(component_type)
			for component_type in env.registry.types
			if component_type is not StaticIdEC
		]

	def __decode(self, env: Env, name: str, static_id: str, raw: str):
		try:
			payload = json.loads(raw)
		except json.JSONDecodeError:
			logger.error("%s row %s is not readable, left untouched", name, static_id)
			self.__protected.setdefault(name, set()).add(static_id)
			return None

		component = env.registry.decode(payload)
		if component is None:
			self.__protected.setdefault(name, set()).add(static_id)
		return component

	def __open(self) -> None:
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self.__connection = sqlite3.connect(self.path)
		self.__connection.execute("pragma journal_mode=wal")
		self.__connection.commit()

	def __close(self) -> None:
		self.__connection.execute("pragma wal_checkpoint(truncate)")
		self.__connection.close()
		self.__connection = None

	def __tables(self) -> Set[str]:
		return set(component_tables(self.__connection))

	def __ensure(self, table: str) -> None:
		self.__connection.execute(
			f'create table if not exists "{table}" '
			f"(static_id text primary key, data text not null)"
		)

	def __read(self, names: Sequence[str]) -> Dict[str, List[Tuple[str, str]]]:
		existing = self.__tables()
		rows = {}
		for name in names:
			table = table_of(name)
			if table not in existing:
				continue
			rows[name] = self.__connection.execute(
				f'select static_id, data from "{table}"'
			).fetchall()
		return rows

	def __write(self,
	            live: Dict[str, List[Tuple[str, str]]],
	            names: Sequence[str],
	            removed: Set[str]) -> None:
		with self.__connection as connection:
			for name, rows in live.items():
				table = table_of(name)
				self.__ensure(table)
				connection.executemany(
					f'insert into "{table}" (static_id, data) values (?, ?) '
					f"on conflict(static_id) do update set data = excluded.data",
					rows,
				)

			existing = self.__tables()
			for name in names:
				table = table_of(name)
				if table not in existing:
					continue
				keep = [static_id for static_id, _ in live.get(name, ())]
				keep += sorted(self.__protected.get(name, ()))
				if keep:
					marks = ",".join("?" * len(keep))
					connection.execute(
						f'delete from "{table}" where static_id not in ({marks})', keep
					)
				else:
					connection.execute(f'delete from "{table}"')

			if removed:
				marks = ",".join("?" * len(removed))
				ids = sorted(removed)
				for table in existing:
					connection.execute(
						f'delete from "{table}" where static_id in ({marks})', ids
					)

	def __versions(self) -> dict:
		self.__connection.execute(
			f"create table if not exists {SCHEMA_TABLE} "
			f"(name text primary key, version integer not null)"
		)
		return dict(self.__connection.execute(f"select name, version from {SCHEMA_TABLE}"))

	def __set_version(self, name: str, version: int) -> None:
		self.__connection.execute(
			f"insert into {SCHEMA_TABLE} (name, version) values (?, ?) "
			f"on conflict(name) do update set version = excluded.version",
			(name, version),
		)

	def __migrate(self, migrations: MigrationRegistry) -> None:
		current = self.__versions()
		existing = self.__tables()

		with self.__connection as connection:
			for name in migrations.names:
				latest = migrations.latest(name)
				if name not in current and table_of(name) not in existing:
					self.__set_version(name, latest)
					continue

				version = current.get(name, 0)
				for step_version, step in migrations.steps(name):
					if step_version <= version:
						continue
					logger.info("migrating %s to version %d", name, step_version)
					step(connection)
					self.__set_version(name, step_version)
					version = step_version
