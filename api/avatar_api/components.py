import uuid
from datetime import date, datetime, timedelta
from typing import Hashable, Iterable, Optional, Set

from angelovich.core.DataStorage import EntityComponent, EntityHashComponent


class StaticIdEC(EntityHashComponent):
	def __init__(self, static_id: Optional[str] = None):
		super().__init__()
		self.static_id: str = static_id or uuid.uuid4().hex

	@staticmethod
	def make_hash(static_id: str) -> Hashable:
		return static_id

	def __hash__(self):
		return hash(self.static_id)

	def __repr__(self):
		return f"StaticIdEC({self.static_id})"


class NoteEC(EntityComponent):
	def __init__(self, title: str = "", text: str = ""):
		super().__init__()
		self.title: str = title
		self.text: str = text
		self.created: datetime = datetime.now()
		self.updated: datetime = self.created

	def touch(self) -> None:
		self.updated = datetime.now()


class TagEC(EntityComponent):
	def __init__(self, tags: Iterable[str] = ()):
		super().__init__()
		self.tags: Set[str] = set(tags)


class TagNameEC(EntityHashComponent):
	def __init__(self, name: str = ""):
		super().__init__()
		self.name: str = name

	@staticmethod
	def make_hash(name: str) -> Hashable:
		return name

	def __hash__(self):
		return hash(self.name)

	def __repr__(self):
		return f"TagNameEC({self.name})"


class ColorEC(EntityComponent):
	def __init__(self, value: str = ""):
		super().__init__()
		self.value: str = value


class DateEC(EntityComponent):
	def __init__(self, value: Optional[date] = None):
		super().__init__()
		self.value: date = value or date.today()


class DurationEC(EntityComponent):
	def __init__(self, value: timedelta = timedelta()):
		super().__init__()
		self.value: timedelta = value


class NotificationEC(EntityComponent):
	def __init__(self, title: str = "", text: str = "", source: str = ""):
		super().__init__()
		self.title: str = title
		self.text: str = text
		self.source: str = source
		self.created: datetime = datetime.now()


class TimerEC(EntityHashComponent):
	def __init__(self, name: str = "", started: Optional[datetime] = None, duration: timedelta = timedelta()):
		super().__init__()
		self.name: str = name
		self.started: datetime = started or datetime.now()
		self.duration: timedelta = duration

	@staticmethod
	def make_hash(name: str) -> Hashable:
		return name

	def __hash__(self):
		return hash(self.name)

	def deadline(self) -> datetime:
		return self.started + self.duration

	def remaining(self, now: Optional[datetime] = None) -> float:
		return max(0.0, (self.deadline() - (now or datetime.now())).total_seconds())

	def __repr__(self):
		return f"TimerEC({self.name})"


class MenuItemEC(EntityComponent):
	def __init__(self, name: str = ""):
		super().__init__()
		self.name: str = name


class ActionEC(EntityComponent):
	def __init__(self, event: str = ""):
		super().__init__()
		self.event: str = event
