from pathlib import Path
from typing import Dict

PAGE = Path(__file__).resolve().parent / "manager.html"

EVENT_OPEN = "request.manager.open"
EVENT_TOGGLE = "request.manager.toggle"
EVENT_APPLY = "request.manager.apply"
EVENT_REVERT = "request.manager.revert"
EVENT_REFRESH = "request.manager.refresh"
EVENT_REGISTRY_ADD = "request.manager.registry.add"
EVENT_REGISTRY_REMOVE = "request.manager.registry.remove"

CHANNEL = "manager"
METHODS: Dict[str, str] = {
	"toggle": EVENT_TOGGLE,
	"apply": EVENT_APPLY,
	"revert": EVENT_REVERT,
	"refresh": EVENT_REFRESH,
	"add_registry": EVENT_REGISTRY_ADD,
	"remove_registry": EVENT_REGISTRY_REMOVE,
}
