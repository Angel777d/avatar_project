from typing import List, Set

from avatar_api import Env, Plugin, System

from avatar_ui.shell import ShellSystem


class UiPlugin(Plugin):
	def get_systems(self, env: Env) -> List[System]:
		return [ShellSystem(env)]

	@staticmethod
	def get_purpose() -> Set[str]:
		return {"shell"}


plugin = UiPlugin()
