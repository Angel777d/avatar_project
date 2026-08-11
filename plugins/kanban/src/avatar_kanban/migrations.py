import sqlite3

from avatar_api.migrations import table_exists, table_of

TASKS = "kanban_task"


def register(migrations) -> None:
	migrations.add(TASKS, 1, _drop_creation_dates)


def _drop_creation_dates(connection: sqlite3.Connection) -> None:
	if not table_exists(connection, "DateEC"):
		return
	connection.execute(
		f'delete from "{table_of("DateEC")}" '
		f'where static_id in (select static_id from "{table_of(TASKS)}")'
	)
