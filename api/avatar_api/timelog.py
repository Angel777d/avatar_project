import uuid
from datetime import datetime
from typing import Iterable, Optional

from angelovich.core.Dispatcher import Dispatcher

from avatar_api.events import ACTION_LOG_DATA, ACTION_LOG_EVENT, REQUEST_LOG_TIME

SPAN = "span"
STARTED = "started"
DURATION = "duration"
SOURCE = "source"
TYPE = "type"
LABEL = "label"
REF = "ref"
TAGS = "tags"
DATA = "data"

WHEN = "when"
EVENT = "event"

CREATED = "created"
DONE = "done"
UNDONE = "undone"


def new_span() -> str:
	return uuid.uuid4().hex


def measure(started: datetime, duration: float, source: str, span: str = "") -> dict:
	return {
		SPAN: span or new_span(),
		STARTED: started,
		DURATION: float(duration),
		SOURCE: source,
	}


def log_time(event_bus: Dispatcher,
             started: datetime,
             duration: float,
             source: str,
             span: str = "") -> dict:
	measured = measure(started, duration, source, span)
	event_bus.dispatch(REQUEST_LOG_TIME, measured)
	return measured


def log_data(event_bus: Dispatcher,
             measured: dict,
             type: str,
             label: str = "",
             ref: str = "",
             tags: Iterable[str] = (),
             data: Optional[dict] = None) -> dict:
	record = {
		SPAN: measured.get(SPAN, ""),
		STARTED: measured.get(STARTED) or datetime.now(),
		DURATION: float(measured.get(DURATION, 0.0)),
		SOURCE: measured.get(SOURCE, ""),
		TYPE: type,
		LABEL: label,
		REF: ref,
		TAGS: list(tags),
		DATA: dict(data or {}),
	}
	event_bus.dispatch(ACTION_LOG_DATA, record)
	return record


def log_event(event_bus: Dispatcher,
              type: str,
              event: str,
              label: str = "",
              ref: str = "",
              when: Optional[datetime] = None,
              tags: Iterable[str] = (),
              data: Optional[dict] = None) -> dict:
	moment = {
		WHEN: when or datetime.now(),
		TYPE: type,
		EVENT: event,
		LABEL: label,
		REF: ref,
		TAGS: list(tags),
		DATA: dict(data or {}),
	}
	event_bus.dispatch(ACTION_LOG_EVENT, moment)
	return moment
