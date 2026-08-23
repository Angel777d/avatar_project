import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BUILTIN = Path(__file__).resolve().parent / "registry.json"
BUILTIN_NAME = "default"

REGISTRIES_FILE = "registries.json"
CACHE_DIR = "registries"

TIMEOUT = 15


def read_json(path: Path) -> Optional[dict]:
	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return None


def write_json(path: Path, payload: dict) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	temp = path.with_suffix(path.suffix + ".tmp")
	temp.write_text(json.dumps(payload, indent="\t"), encoding="utf-8")
	os.replace(temp, path)


def read_registries(workspace: Optional[Path]) -> List[dict]:
	if workspace is None:
		return []
	payload = read_json(workspace / REGISTRIES_FILE) or {}
	entries = []
	for entry in payload.get("registries", []):
		name = str(entry.get("name", "")).strip()
		if not name or name == BUILTIN_NAME:
			continue
		if entry.get("url"):
			entries.append({"name": name, "url": str(entry["url"]).strip()})
		elif entry.get("path"):
			entries.append({"name": name, "path": str(entry["path"]).strip()})
	return entries


def write_registries(workspace: Optional[Path], entries: List[dict]) -> None:
	if workspace is None:
		return
	write_json(workspace / REGISTRIES_FILE, {"registries": entries})


def sources(workspace: Optional[Path]) -> List[dict]:
	"""The built-in registry first, then whatever the user added, in the order they were added."""
	return [{"name": BUILTIN_NAME, "path": str(BUILTIN), "builtin": True}] + read_registries(workspace)


def rank(entries: List[dict]) -> List[Tuple[int, dict]]:
	"""A local path outranks a remote one; otherwise the order they appear in."""
	order = []
	for index, entry in enumerate(entries):
		local = "path" in entry and not entry.get("builtin")
		order.append(((0 if local else 1, index), entry))
	order.sort(key=lambda pair: pair[0])
	return [(index, entry) for index, (_, entry) in enumerate(order)]


def load(entry: dict, workspace: Optional[Path], refresh: bool) -> Tuple[Optional[dict], str]:
	"""Returns the registry document and whatever went wrong reaching it."""
	if "path" in entry:
		path = Path(entry["path"])
		document = read_json(path)
		return (document, "") if document is not None else (None, f"cannot read {path}")

	cache = None
	if workspace is not None:
		cache = workspace / CACHE_DIR / f"{entry['name']}.json"

	if refresh or cache is None or not cache.exists():
		document, problem = fetch(entry["url"], cache)
		if document is not None:
			return document, ""
		if cache is None or not cache.exists():
			return None, problem
		logger.info("using the cached copy of %s: %s", entry["name"], problem)

	document = read_json(cache)
	return (document, "") if document is not None else (None, "the cached copy is unreadable")


def fetch(url: str, cache: Optional[Path]) -> Tuple[Optional[dict], str]:
	try:
		request = urllib.request.Request(url, headers={"Accept": "application/json"})
		with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
			body = response.read().decode("utf-8")
	except (urllib.error.URLError, OSError, UnicodeDecodeError) as ex:
		return None, f"{ex}"

	try:
		document = json.loads(body)
	except ValueError as ex:
		return None, f"not a registry: {ex}"

	if cache is not None:
		try:
			write_json(cache, document)
		except OSError as ex:
			logger.info("could not cache %s: %s", url, ex)
	return document, ""


def catalogue(workspace: Optional[Path], refresh: bool = False) -> Tuple[List[dict], List[dict]]:
	"""Every plugin every registry offers, first registry to name one wins."""
	found: Dict[str, dict] = {}
	report: List[dict] = []

	for _, entry in rank(sources(workspace)):
		document, problem = load(entry, workspace, refresh)
		count = 0

		for plugin in (document or {}).get("plugins", []):
			name = str(plugin.get("name", "")).strip()
			requirement = str(plugin.get("requirement", "")).strip()
			if not name or not requirement or name in found:
				continue
			found[name] = {
				"name": name,
				"title": str(plugin.get("title", name)),
				"summary": str(plugin.get("summary", "")),
				"version": str(plugin.get("version", "")),
				"requirement": requirement,
				"homepage": str(plugin.get("homepage", "")),
				"restartNeeded": bool(plugin.get("restartNeeded", False)),
				"registry": entry["name"],
			}
			count += 1

		report.append({
			"name": entry["name"],
			"location": entry.get("path") or entry.get("url", ""),
			"local": "path" in entry,
			"builtin": bool(entry.get("builtin")),
			"count": count,
			"problem": problem,
		})

	return sorted(found.values(), key=lambda plugin: plugin["title"].lower()), report
