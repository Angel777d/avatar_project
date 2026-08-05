from typing import List

from avatar_api import Env, Plugin, System

from avatar_calendar.system import CalendarSystem


class CalendarPlugin(Plugin):
	def get_systems(self, env: Env) -> List[System]:
		return [CalendarSystem(env)]


plugin = CalendarPlugin()
