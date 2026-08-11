import json
import sqlite3
import uuid
from collections import defaultdict

from avatar_api.migrations import forget, table_exists, table_of

SESSIONS = "pomodoro_session"
LOG = "pomodoro_log"


def register(migrations) -> None:
	migrations.add(SESSIONS, 1, _fold_into_the_log)


def _fold_into_the_log(connection: sqlite3.Connection) -> None:
	if not table_exists(connection, SESSIONS):
		return

	ids = [i for (i,) in connection.execute(f'select static_id from "{table_of(SESSIONS)}"')]
	if not ids:
		return

	days = defaultdict(int)
	seconds = defaultdict(float)
	dates = _column(connection, "DateEC", ids)
	spans = _column(connection, "DurationEC", ids)

	for static_id in ids:
		day = dates.get(static_id)
		if not day:
			continue
		days[day] += 1
		seconds[day] += spans.get(static_id, 0.0)

	_merge(connection, dict(days), dict(seconds))
	forget(connection, ids)


def _column(connection: sqlite3.Connection, name: str, ids: list) -> dict:
	if not table_exists(connection, name):
		return {}
	marks = ",".join("?" * len(ids))
	out = {}
	for static_id, raw in connection.execute(
			f'select static_id, data from "{table_of(name)}" where static_id in ({marks})', ids):
		value = json.loads(raw)["fields"]["value"]
		out[static_id] = value["$v"] if isinstance(value, dict) else value
	return out


def _merge(connection: sqlite3.Connection, days: dict, seconds: dict) -> None:
	table = table_of(LOG)
	connection.execute(
		f'create table if not exists "{table}" (static_id text primary key, data text not null)'
	)
	row = connection.execute(f'select static_id, data from "{table}" limit 1').fetchone()

	if row:
		static_id, raw = row
		fields = json.loads(raw)["fields"]
		for day, count in days.items():
			fields["days"][day] = fields["days"].get(day, 0) + count
		for day, total in seconds.items():
			fields["seconds"][day] = fields["seconds"].get(day, 0.0) + total
	else:
		static_id = uuid.uuid4().hex
		fields = {"days": days, "seconds": seconds}

	payload = json.dumps({"type": LOG, "fields": fields})
	connection.execute(
		f'insert into "{table}" (static_id, data) values (?, ?) '
		f"on conflict(static_id) do update set data = excluded.data",
		(static_id, payload),
	)
