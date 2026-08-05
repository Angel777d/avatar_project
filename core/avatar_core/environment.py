import asyncio
from typing import Optional

from angelovich.core.Environment import Environment as CoreEnvironment

from avatar_api.registry import TypeRegistry


class Environment(CoreEnvironment):
	def __init__(self):
		super().__init__()
		self.registry: TypeRegistry = TypeRegistry()
		self.close_event: Optional[asyncio.Event] = None
