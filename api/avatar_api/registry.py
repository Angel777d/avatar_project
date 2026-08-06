import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Type

from angelovich.core.DataStorage import DataStorage, Entity, EntityComponent

logger = logging.getLogger(__name__)

TYPE_KEY = "$t"
VALUE_KEY = "$v"

NAME_FIELD = "type"
FIELDS_FIELD = "fields"

PASS_THROUGH = (str, int, float, bool)


def encode_value(value: Any) -> Any:
	if value is None or isinstance(value, PASS_THROUGH):
		return value
	if isinstance(value, datetime):
		return {TYPE_KEY: "datetime", VALUE_KEY: value.isoformat()}
	if isinstance(value, date):
		return {TYPE_KEY: "date", VALUE_KEY: value.isoformat()}
	if isinstance(value, time):
		return {TYPE_KEY: "time", VALUE_KEY: value.isoformat()}
	if isinstance(value, timedelta):
		return {TYPE_KEY: "timedelta", VALUE_KEY: value.total_seconds()}
	if isinstance(value, (set, frozenset)):
		return {TYPE_KEY: "set", VALUE_KEY: [encode_value(item) for item in value]}
	if isinstance(value, tuple):
		return {TYPE_KEY: "tuple", VALUE_KEY: [encode_value(item) for item in value]}
	if isinstance(value, list):
		return [encode_value(item) for item in value]
	if isinstance(value, dict):
		if TYPE_KEY in value:
			raise TypeError(f"dict key {TYPE_KEY} is reserved")
		if any(not isinstance(key, str) for key in value):
			raise TypeError("only string keys can be stored")
		return {key: encode_value(item) for key, item in value.items()}
	raise TypeError(f"cannot store {type(value)}")


def decode_value(value: Any) -> Any:
	if isinstance(value, list):
		return [decode_value(item) for item in value]
	if not isinstance(value, dict):
		return value
	if TYPE_KEY not in value:
		return {key: decode_value(item) for key, item in value.items()}

	kind = value[TYPE_KEY]
	raw = value[VALUE_KEY]
	if kind == "datetime":
		return datetime.fromisoformat(raw)
	if kind == "date":
		return date.fromisoformat(raw)
	if kind == "time":
		return time.fromisoformat(raw)
	if kind == "timedelta":
		return timedelta(seconds=raw)
	if kind == "set":
		return {decode_value(item) for item in raw}
	if kind == "tuple":
		return tuple(decode_value(item) for item in raw)
	raise TypeError(f"unknown stored type {kind}")


class TypeRegistry:
	def __init__(self):
		self.__by_name: Dict[str, Type[EntityComponent]] = {}
		self.__by_type: Dict[Type[EntityComponent], str] = {}
		self.__fields: Dict[Type[EntityComponent], Optional[Tuple[str, ...]]] = {}

	def register(self,
	             component_type: Type[EntityComponent],
	             name: Optional[str] = None,
	             fields: Optional[Sequence[str]] = None) -> None:
		name = name or component_type.__name__
		known = self.__by_type.get(component_type)
		if known is not None:
			if known != name:
				raise RuntimeError(f"{component_type.__name__} already registered as '{known}'")
			return

		taken = self.__by_name.get(name)
		if taken is not None:
			raise RuntimeError(f"name '{name}' already registered to {taken.__name__}")

		self.__by_name[name] = component_type
		self.__by_type[component_type] = name
		self.__fields[component_type] = tuple(fields) if fields is not None else None

	def register_all(self, component_types: Iterable[Type[EntityComponent]]) -> None:
		for component_type in component_types:
			self.register(component_type)

	@property
	def types(self) -> Tuple[Type[EntityComponent], ...]:
		return tuple(self.__by_type)

	def name_of(self, component_type: Type[EntityComponent]) -> Optional[str]:
		return self.__by_type.get(component_type)

	def type_of(self, name: str) -> Optional[Type[EntityComponent]]:
		return self.__by_name.get(name)

	def encode(self, component: EntityComponent) -> Optional[dict]:
		component_type = type(component)
		name = self.__by_type.get(component_type)
		if name is None:
			logger.warning("%s is not registered, not stored", component_type.__name__)
			return None

		declared = self.__fields[component_type]
		keys = declared if declared is not None else [
			key for key in vars(component) if not key.startswith("_")
		]
		return {
			NAME_FIELD: name,
			FIELDS_FIELD: {key: encode_value(getattr(component, key)) for key in keys},
		}

	def decode(self, payload: dict) -> Optional[EntityComponent]:
		name = payload.get(NAME_FIELD)
		component_type = self.__by_name.get(name)
		if component_type is None:
			logger.warning("stored type '%s' is not registered, skipped", name)
			return None

		stored = payload.get(FIELDS_FIELD, {})
		component = component_type.__new__(component_type)
		EntityComponent.__init__(component)
		for key, value in stored.items():
			setattr(component, key, decode_value(value))
		self.__fill_missing(component_type, component, stored)
		return component

	def __fill_missing(self, component_type, component: EntityComponent, stored: dict) -> None:
		declared = self.__fields[component_type]
		expected = declared if declared is not None else None
		if expected is not None and all(key in stored for key in expected):
			return

		try:
			fresh = component_type()
		except TypeError:
			logger.warning("%s cannot be built without arguments, missing fields left unset",
			               component_type.__name__)
			return

		for key, value in vars(fresh).items():
			if key.startswith("_") or key in stored:
				continue
			logger.info("%s.%s was not stored, using the default", component_type.__name__, key)
			setattr(component, key, value)

	def encode_entity(self, entity: Entity) -> List[dict]:
		payloads = []
		for component_type in self.__by_type:
			if entity.has_component(component_type):
				payload = self.encode(entity.get_component(component_type))
				if payload is not None:
					payloads.append(payload)
		return payloads

	def decode_entity(self, data_storage: DataStorage, payloads: Iterable[dict]) -> Entity:
		entity = data_storage.create_entity()
		for payload in payloads:
			component = self.decode(payload)
			if component is not None:
				entity.add_component(component)
		return entity
