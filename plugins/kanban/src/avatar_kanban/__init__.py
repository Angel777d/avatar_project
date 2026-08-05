from typing import List

from avatar_api import Env, Plugin, System

from avatar_kanban.system import KanbanSystem


class KanbanPlugin(Plugin):
	def get_systems(self, env: Env) -> List[System]:
		return [KanbanSystem(env)]


plugin = KanbanPlugin()
