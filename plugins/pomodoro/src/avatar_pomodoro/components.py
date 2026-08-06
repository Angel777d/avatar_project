from avatar_api import EntityComponent

DEFAULT_WORK_S = 25 * 60
DEFAULT_SHORT_BREAK_S = 5 * 60
DEFAULT_LONG_BREAK_S = 15 * 60
DEFAULT_LONG_BREAK_EVERY = 4
DEFAULT_SEQUENCES = 4


class PomodoroSessionEC(EntityComponent):
	def __init__(self, phase: str = ""):
		super().__init__()
		self.phase: str = phase


class PomodoroSettingsEC(EntityComponent):
	def __init__(self,
	             work: float = DEFAULT_WORK_S,
	             short_break: float = DEFAULT_SHORT_BREAK_S,
	             long_break: float = DEFAULT_LONG_BREAK_S,
	             long_break_every: int = DEFAULT_LONG_BREAK_EVERY,
	             sequences: int = DEFAULT_SEQUENCES):
		super().__init__()
		self.work: float = work
		self.short_break: float = short_break
		self.long_break: float = long_break
		self.long_break_every: int = long_break_every
		self.sequences: int = sequences
