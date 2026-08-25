import csv
from pathlib import Path
from typing import Tuple

from avatar_api import DataStorage

from avatar_stats.components import DEFAULT_RANGE
from avatar_stats.summary import build_snapshot

DATA_FOLDER = "data"
COLUMNS = ("day", "time", "kind", "type", "label", "source", "seconds", "tags")


def folder() -> Path:
	return Path.cwd() / DATA_FOLDER


def write_csv(data_storage: DataStorage,
              days: int = DEFAULT_RANGE,
              since: str = "",
              until: str = "") -> Tuple[Path, int]:
	snapshot = build_snapshot(data_storage, days, since, until)
	rows = snapshot["rows"]
	span = snapshot["range"]
	path = folder() / f"time-{span['since']}-{span['until']}.csv"

	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.writer(handle)
		writer.writerow(COLUMNS)
		for row in rows:
			writer.writerow([
				row["day"], row["time"], row["kind"], row["type"], row["label"],
				row["source"], row["seconds"], " ".join(row["tags"]),
			])
	return path, len(rows)
