from datetime import datetime
from typing import Optional

from avatar_api import EntityComponent

ROLE_BACKLOG = "backlog"
ROLE_DONE = "done"

DEFAULT_COLUMNS = (
	("todo", "To do", ROLE_BACKLOG),
	("next", "Do next", ""),
	("doing", "In Progress", ""),
	("done", "Done", ROLE_DONE),
)


class KanbanColumnEC(EntityComponent):
	def __init__(self, name: str = "", position: int = 0, role: str = "", key: str = ""):
		super().__init__()
		self.name: str = name
		self.position: int = position
		self.role: str = role
		self.key: str = key


class KanbanTaskEC(EntityComponent):
	def __init__(self, column: str = "todo", position: int = 0):
		super().__init__()
		self.column: str = column
		self.position: int = position


class KanbanCurrentEC(EntityComponent):
	def __init__(self, since: Optional[datetime] = None):
		super().__init__()
		self.since: datetime = since or datetime.now()
