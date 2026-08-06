from avatar_api import EntityComponent


class PomodoroSessionEC(EntityComponent):
	def __init__(self, phase: str = ""):
		super().__init__()
		self.phase: str = phase
