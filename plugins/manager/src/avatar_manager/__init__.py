from typing import List

from avatar_api import Env, Plugin, System

from avatar_manager.system import ManagerSystem


class ManagerPlugin(Plugin):
	def get_systems(self, env: Env) -> List[System]:
		return [ManagerSystem(env)]


plugin = ManagerPlugin()
