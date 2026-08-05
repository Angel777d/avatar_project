from avatar_api import EntityComponent

COLUMNS = (
	("todo", "To do"),
	("doing", "Doing"),
	("done", "Done"),
)


class KanbanTaskEC(EntityComponent):
	def __init__(self, column: str = "todo", position: int = 0):
		super().__init__()
		self.column: str = column
		self.position: int = position
