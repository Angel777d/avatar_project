from typing import List, Set

from avatar_api import Env, Plugin, System

from avatar_ui.system import UiSystem


class UiPlugin(Plugin):
	def get_systems(self, env: Env) -> List[System]:
		return [UiSystem(env)]

	@staticmethod
	def get_purpose() -> Set[str]:
		return {"shell"}


plugin = UiPlugin()
