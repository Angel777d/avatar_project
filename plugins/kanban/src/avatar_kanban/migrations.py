import json
import sqlite3
import uuid
from typing import Dict, List, Tuple

from avatar_api.migrations import table_exists, table_of

COLUMNS = "kanban_column"
TASKS = "kanban_task"

FIELDS = "fields"
KEY = "key"
COLUMN = "column"


def rows_of(connection: sqlite3.Connection, name: str) -> List[Tuple[str, dict]]:
	if not table_exists(connection, name):
		return []

	found = []
	for static_id, raw in connection.execute(
			f'select static_id, data from "{table_of(name)}"').fetchall():
		try:
			payload = json.loads(raw)
		except json.JSONDecodeError:
			continue
		if isinstance(payload, dict):
			found.append((static_id, payload))
	return found


def generated_ids(connection: sqlite3.Connection) -> None:
	minted: Dict[str, str] = {}

	for static_id, payload in rows_of(connection, COLUMNS):
		fields = payload.setdefault(FIELDS, {})
		if fields.get(KEY):
			continue
		fields[KEY] = static_id
		minted[static_id] = uuid.uuid4().hex
		connection.execute(
			f'update "{table_of(COLUMNS)}" set static_id = ?, data = ? where static_id = ?',
			(minted[static_id], json.dumps(payload), static_id))

	if not minted:
		return

	for static_id, payload in rows_of(connection, TASKS):
		fields = payload.get(FIELDS, {})
		fresh = minted.get(fields.get(COLUMN))
		if fresh is None:
			continue
		fields[COLUMN] = fresh
		connection.execute(
			f'update "{table_of(TASKS)}" set data = ? where static_id = ?',
			(json.dumps(payload), static_id))
