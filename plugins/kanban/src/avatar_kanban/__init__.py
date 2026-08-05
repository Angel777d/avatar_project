from typing import List

from avatar_api import Environment, Plugin, System

from avatar_kanban.system import KanbanSystem


class KanbanPlugin(Plugin):
	def get_systems(self, env: Environment) -> List[System]:
		return [KanbanSystem(env)]


plugin = KanbanPlugin()
