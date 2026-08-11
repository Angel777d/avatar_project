from datetime import time
from typing import Optional

from avatar_api import EntityComponent


class CalendarNoteEC(EntityComponent):
	def __init__(self, begin: Optional[time] = None, end: Optional[time] = None):
		super().__init__()
		self.begin: Optional[time] = begin
		self.end: Optional[time] = end
