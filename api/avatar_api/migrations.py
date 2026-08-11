import re
import sqlite3
from typing import Callable, Dict, List, Tuple

PREFIX = "c_"
UNSAFE = re.compile(r"[^A-Za-z0-9_]")

Step = Callable[[sqlite3.Connection], None]


def table_of(name: str) -> str:
	return PREFIX + UNSAFE.sub("_", name)


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
	return connection.execute(
		"select 1 from sqlite_master where type = 'table' and name = ?", (table_of(name),)
	).fetchone() is not None


def forget(connection: sqlite3.Connection, static_ids: List[str]) -> None:
	if not static_ids:
		return
	marks = ",".join("?" * len(static_ids))
	tables = component_tables(connection)
	for table in tables:
		connection.execute(f'delete from "{table}" where static_id in ({marks})', static_ids)


def component_tables(connection: sqlite3.Connection) -> List[str]:
	return [
		name for (name,) in connection.execute(
			"select name from sqlite_master where type = 'table'"
		)
		if name.startswith(PREFIX)
	]


class MigrationRegistry:
	def __init__(self):
		self.__steps: Dict[str, List[Tuple[int, Step]]] = {}

	def add(self, name: str, version: int, step: Step) -> None:
		if version < 1:
			raise RuntimeError("migration versions start at 1")
		steps = self.__steps.setdefault(name, [])
		if any(known == version for known, _ in steps):
			raise RuntimeError(f"{name} already has a migration to version {version}")
		steps.append((version, step))
		steps.sort(key=lambda item: item[0])

	@property
	def names(self) -> List[str]:
		return list(self.__steps)

	def steps(self, name: str) -> List[Tuple[int, Step]]:
		return list(self.__steps.get(name, ()))

	def latest(self, name: str) -> int:
		steps = self.__steps.get(name)
		return steps[-1][0] if steps else 0
