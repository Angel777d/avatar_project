import threading
from typing import Generic, TypeVar

_T = TypeVar("_T")


class Guarded(Generic[_T]):
	def __init__(self, value: _T):
		self.__lock = threading.Lock()
		self.__value = value

	def get(self) -> _T:
		with self.__lock:
			return self.__value

	def set(self, value: _T) -> None:
		with self.__lock:
			self.__value = value
