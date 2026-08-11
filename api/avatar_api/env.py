import asyncio
from typing import Optional

from angelovich.core.Environment import Environment

from avatar_api.migrations import MigrationRegistry
from avatar_api.registry import TypeRegistry


class Env(Environment):
	def __init__(self):
		super().__init__()
		self.registry: TypeRegistry = TypeRegistry()
		self.migrations: MigrationRegistry = MigrationRegistry()
		self.close_event: Optional[asyncio.Event] = None
