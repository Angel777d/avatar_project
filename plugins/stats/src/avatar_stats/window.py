from pathlib import Path
from typing import Dict

PAGE = Path(__file__).resolve().parent / "time.html"
WINDOW = "Statistics"

EVENT_OPEN = "request.stats.open"
EVENT_START = "request.stats.start"
EVENT_STOP = "request.stats.stop"
EVENT_ADD = "request.stats.add"
EVENT_FORGET = "request.stats.forget"
EVENT_EXPORT = "request.stats.export"
EVENT_RANGE = "request.stats.range"

CHANNEL = "stats"
METHODS: Dict[str, str] = {
	"snapshot": EVENT_RANGE,
	"start": EVENT_START,
	"stop": EVENT_STOP,
	"add": EVENT_ADD,
	"forget": EVENT_FORGET,
	"export": EVENT_EXPORT,
}
