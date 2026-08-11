from datetime import date
from typing import Dict, Optional

from avatar_api import EntityComponent

DEFAULT_NAME = "Classic"
DEFAULT_WORK_S = 25 * 60
DEFAULT_SHORT_BREAK_S = 5 * 60
DEFAULT_LONG_BREAK_S = 15 * 60
DEFAULT_LONG_BREAK_EVERY = 4
DEFAULT_SEQUENCES = 4


class PomodoroLogEC(EntityComponent):
	def __init__(self,
	             days: Optional[Dict[str, int]] = None,
	             seconds: Optional[Dict[str, float]] = None):
		super().__init__()
		self.days: Dict[str, int] = days or {}
		self.seconds: Dict[str, float] = dict(seconds or {})

	def add(self, day: date, focus: float = 0.0, count: int = 1) -> None:
		key = day.isoformat()
		self.days[key] = self.days.get(key, 0) + count
		self.seconds[key] = self.seconds.get(key, 0.0) + float(focus)

	def count(self, day: date) -> int:
		return self.days.get(day.isoformat(), 0)

	def focus(self, day: date) -> float:
		return self.seconds.get(day.isoformat(), 0.0)

	@property
	def total(self) -> int:
		return sum(self.days.values())


class PomodoroChoiceEC(EntityComponent):
	def __init__(self, preset: str = ""):
		super().__init__()
		self.preset: str = preset


class PomodoroSettingsEC(EntityComponent):
	def __init__(self,
	             name: str = DEFAULT_NAME,
	             work: float = DEFAULT_WORK_S,
	             short_break: float = DEFAULT_SHORT_BREAK_S,
	             long_break: float = DEFAULT_LONG_BREAK_S,
	             long_break_every: int = DEFAULT_LONG_BREAK_EVERY,
	             sequences: int = DEFAULT_SEQUENCES):
		super().__init__()
		self.name: str = name
		self.work: float = work
		self.short_break: float = short_break
		self.long_break: float = long_break
		self.long_break_every: int = long_break_every
		self.sequences: int = sequences
