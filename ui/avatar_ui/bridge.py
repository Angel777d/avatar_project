from PySide6.QtCore import QObject, Signal, Slot


class Bridge(QObject):
	changed = Signal()

	def __init__(self, entity_id: int, ui):
		super().__init__()
		self.__entity_id = entity_id
		self.__ui = ui
		self.__state = "{}"

	def push(self, state: str) -> None:
		if state == self.__state:
			return
		self.__state = state
		self.changed.emit()

	@Slot(result=str)
	def state(self) -> str:
		return self.__state

	@Slot(str, str)
	def invoke(self, method: str, args: str) -> None:
		self.__ui.invoke_page(self.__entity_id, method, args)
