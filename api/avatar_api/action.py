from typing import Optional

from angelovich.core.DataStorage import Entity
from angelovich.core.Dispatcher import Dispatcher

from avatar_api.components import ActionEC


def set_action(entity: Entity, event: str) -> Entity:
	if entity.has_component(ActionEC):
		entity.get_component(ActionEC).event = event
	else:
		entity.add_component(ActionEC(event))
	return entity


def action_of(entity: Entity) -> Optional[str]:
	return entity.get_component(ActionEC).event if entity.has_component(ActionEC) else None


def trigger(event_bus: Dispatcher, entity: Entity, *args) -> bool:
	event = action_of(entity)
	if not event:
		return False
	event_bus.dispatch(event, *args)
	return True
