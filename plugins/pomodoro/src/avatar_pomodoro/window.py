from pathlib import Path
from typing import Dict

PAGE = Path(__file__).resolve().parent / "timer.html"

EVENT_OPEN = "request.pomodoro.open"
EVENT_START = "request.pomodoro.start"
EVENT_PAUSE = "request.pomodoro.pause"
EVENT_RESET = "request.pomodoro.reset"
EVENT_SKIP = "request.pomodoro.skip"
EVENT_SELECT = "request.pomodoro.select"
EVENT_PRESET_SAVE = "request.pomodoro.preset.save"
EVENT_PRESET_DELETE = "request.pomodoro.preset.delete"

ACTION_PHASE_CHANGED = "action.pomodoro.phase"

CHANNEL = "pomodoro"
METHODS: Dict[str, str] = {
	"start": EVENT_START,
	"pause": EVENT_PAUSE,
	"reset": EVENT_RESET,
	"skip": EVENT_SKIP,
	"select_preset": EVENT_SELECT,
	"delete_preset": EVENT_PRESET_DELETE,
	"save_preset": EVENT_PRESET_SAVE,
}
