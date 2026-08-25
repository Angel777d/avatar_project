from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass(frozen=True)
class PageView:
	title: str = ""
	window: str = ""
	path: str = ""
	channel: str = ""
	snapshot: str = "{}"
	methods: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AvatarView:
	bubble: str = ""
	timer_progress: float = -1.0
	menu: List[Tuple[int, str]] = field(default_factory=list)
