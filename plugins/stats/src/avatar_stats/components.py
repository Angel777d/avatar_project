from datetime import datetime, timedelta
from typing import Dict, List, Optional

from avatar_api import EntityComponent

MAX_ENTRIES = 200
RANGES = (1, 7, 30)
DEFAULT_RANGE = 7


class LogEntryEC(EntityComponent):
	def __init__(self,
	             span: str = "",
	             started: Optional[datetime] = None,
	             duration: float = 0.0,
	             type: str = "",
	             label: str = "",
	             ref: str = "",
	             source: str = "",
	             tags: Optional[List[str]] = None,
	             data: Optional[Dict] = None):
		super().__init__()
		self.span: str = span
		self.started: datetime = started or datetime.now()
		self.duration: float = float(duration)
		self.type: str = type
		self.label: str = label
		self.ref: str = ref
		self.source: str = source
		self.tags: List[str] = list(tags or ())
		self.data: dict = dict(data or {})

	@property
	def ended(self) -> datetime:
		return self.started + timedelta(seconds=self.duration)


class LogEventEC(EntityComponent):
	def __init__(self,
	             when: Optional[datetime] = None,
	             type: str = "",
	             event: str = "",
	             label: str = "",
	             ref: str = "",
	             tags: Optional[List[str]] = None,
	             data: Optional[Dict] = None):
		super().__init__()
		self.when: datetime = when or datetime.now()
		self.type: str = type
		self.event: str = event
		self.label: str = label
		self.ref: str = ref
		self.tags: List[str] = list(tags or ())
		self.data: dict = dict(data or {})


class StopwatchEC(EntityComponent):
	def __init__(self, label: str = "", started: Optional[datetime] = None, span: str = ""):
		super().__init__()
		self.label: str = label
		self.started: datetime = started or datetime.now()
		self.span: str = span

	def elapsed(self, now: Optional[datetime] = None) -> float:
		return max(0.0, ((now or datetime.now()) - self.started).total_seconds())
