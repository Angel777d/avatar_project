from typing import List

from avatar_api import Env, Plugin, System

from avatar_pomodoro.system import PomodoroSystem


class PomodoroPlugin(Plugin):
	def get_systems(self, env: Env) -> List[System]:
		return [PomodoroSystem(env)]


plugin = PomodoroPlugin()
