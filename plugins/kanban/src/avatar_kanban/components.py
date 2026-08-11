from avatar_api import EntityComponent

DEFAULT_COLUMNS = (
	("todo", "To do"),
	("doing", "Doing"),
	("done", "Done"),
)


class KanbanColumnEC(EntityComponent):
	def __init__(self, name: str = "", position: int = 0):
		super().__init__()
		self.name: str = name
		self.position: int = position


class KanbanTaskEC(EntityComponent):
	def __init__(self, column: str = "todo", position: int = 0):
		super().__init__()
		self.column: str = column
		self.position: int = position
