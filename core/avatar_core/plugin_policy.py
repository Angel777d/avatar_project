import logging
from typing import Collection, List

from angelovich.core.Plugin import Plugin

logger = logging.getLogger(__name__)

PLUGINS_ENABLED_BY_DEFAULT = True


def select_plugins(plugins: List[Plugin],
                   enabled: Collection[str] = (),
                   disabled: Collection[str] = (),
                   enabled_by_default: bool = PLUGINS_ENABLED_BY_DEFAULT) -> List[Plugin]:
	result = []
	for plugin in plugins:
		if plugin.name in disabled:
			logger.info("plugin %s disabled", plugin.name)
			continue
		if not enabled_by_default and plugin.name not in enabled:
			logger.info("plugin %s not enabled", plugin.name)
			continue
		result.append(plugin)
	return result
