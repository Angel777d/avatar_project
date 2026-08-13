from typing import List

from avatar_api import Env, Plugin, System

from avatar_stats.system import StatsSystem


class StatsPlugin(Plugin):
	def get_systems(self, env: Env) -> List[System]:
		return [StatsSystem(env)]


plugin = StatsPlugin()
