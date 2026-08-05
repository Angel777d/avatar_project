from typing import List, Set

from avatar_api import Env, Plugin, System

from avatar_default.system import AvatarSystem


class AvatarPlugin(Plugin):
	def get_systems(self, env: Env) -> List[System]:
		return [AvatarSystem(env)]

	@staticmethod
	def get_purpose() -> Set[str]:
		return {"avatar", "notify"}


plugin = AvatarPlugin()
