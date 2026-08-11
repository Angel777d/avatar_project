import colorsys
import json
import random
from typing import Iterable, List, Optional

from angelovich.core.DataStorage import DataStorage, Entity

from avatar_api.components import ColorEC, StaticIdEC, TagEC, TagNameEC

SATURATION = 0.55
LIGHTNESS = 0.62


def random_color() -> str:
	red, green, blue = colorsys.hls_to_rgb(random.random(), LIGHTNESS, SATURATION)
	return "#{:02x}{:02x}{:02x}".format(round(red * 255), round(green * 255), round(blue * 255))


def find_tag(data_storage: DataStorage, name: str) -> Optional[Entity]:
	return data_storage.get_collection(TagNameEC).find(TagNameEC.make_hash(name))


def ensure_tag(data_storage: DataStorage, name: str) -> Optional[Entity]:
	name = name.strip()
	if not name:
		return None

	known = find_tag(data_storage, name)
	if known is not None:
		return known

	entity = data_storage.create_entity()
	entity.add_component(StaticIdEC())
	entity.add_component(TagNameEC(name))
	entity.add_component(ColorEC(random_color()))
	return entity


def color_of(data_storage: DataStorage, name: str) -> str:
	entity = find_tag(data_storage, name)
	if entity is None or not entity.has_component(ColorEC):
		return ""
	return entity.get_component(ColorEC).value


def catalogue(data_storage: DataStorage) -> List[dict]:
	found = [
		{
			"name": entity.get_component(TagNameEC).name,
			"color": entity.get_component(ColorEC).value if entity.has_component(ColorEC) else "",
		}
		for entity in data_storage.get_collection(TagNameEC)
	]
	found.sort(key=lambda tag: tag["name"].lower())
	return found


def tags_of(data_storage: DataStorage, entity: Entity) -> List[dict]:
	if not entity.has_component(TagEC):
		return []
	return [
		{"name": name, "color": color_of(data_storage, name)}
		for name in sorted(entity.get_component(TagEC).tags, key=str.lower)
	]


def names_from(payload: str) -> List[str]:
	if not payload:
		return []
	try:
		loaded = json.loads(payload)
	except json.JSONDecodeError:
		return []
	if not isinstance(loaded, list):
		return []
	return [name for name in loaded if isinstance(name, str)]


def apply_tags(data_storage: DataStorage, entity: Entity, names: Iterable[str]) -> List[str]:
	wanted = []
	for name in names:
		name = name.strip()
		if name and name not in wanted:
			ensure_tag(data_storage, name)
			wanted.append(name)

	if entity.has_component(TagEC):
		entity.get_component(TagEC).tags = set(wanted)
	elif wanted:
		entity.add_component(TagEC(wanted))
	return wanted
