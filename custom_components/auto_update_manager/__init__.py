"""PatchPilot integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_DRY_RUN,
    ATTR_IGNORE_WINDOW,
    DATA_MANAGERS,
    DATA_SERVICES_REGISTERED,
    DOMAIN,
    PLATFORMS,
    SERVICE_EXCLUDE_ENTITIES,
    SERVICE_INCLUDE_ENTITIES,
    SERVICE_RUN_UPDATES,
    SERVICE_SCAN,
)
from .manager import AutoUpdateManager, service_options_from_call

_LOGGER = logging.getLogger(__name__)

RUN_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_IGNORE_WINDOW, default=False): cv.boolean,
        vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean,
    }
)

SCAN_SERVICE_SCHEMA = vol.Schema({})
ENTITY_LIST_SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PatchPilot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_MANAGERS, {})

    manager = AutoUpdateManager(hass, entry)
    hass.data[DOMAIN][DATA_MANAGERS][entry.entry_id] = manager

    await manager.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    manager = hass.data[DOMAIN][DATA_MANAGERS].pop(entry.entry_id)
    await manager.async_stop()

    if not hass.data[DOMAIN][DATA_MANAGERS]:
        hass.services.async_remove(DOMAIN, SERVICE_RUN_UPDATES)
        hass.services.async_remove(DOMAIN, SERVICE_SCAN)
        hass.services.async_remove(DOMAIN, SERVICE_EXCLUDE_ENTITIES)
        hass.services.async_remove(DOMAIN, SERVICE_INCLUDE_ENTITIES)
        hass.data[DOMAIN][DATA_SERVICES_REGISTERED] = False

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.data[DOMAIN].get(DATA_SERVICES_REGISTERED):
        return

    async def async_handle_run_updates(call: ServiceCall) -> None:
        """Handle manual update pass."""
        options = service_options_from_call(dict(call.data))
        for manager in _selected_managers(hass, call.data):
            await manager.async_run(reason="service", **options)

    async def async_handle_scan(call: ServiceCall) -> None:
        """Handle manual scan."""
        for manager in _selected_managers(hass, call.data):
            await manager.async_scan()

    async def async_handle_exclude_entities(call: ServiceCall) -> None:
        """Handle persistent update entity exclusions."""
        for manager in _selected_managers(hass, call.data):
            await manager.async_set_entities_excluded(call.data[ATTR_ENTITY_ID], True)

    async def async_handle_include_entities(call: ServiceCall) -> None:
        """Handle removing persistent update entity exclusions."""
        for manager in _selected_managers(hass, call.data):
            await manager.async_set_entities_excluded(call.data[ATTR_ENTITY_ID], False)

    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_UPDATES,
        async_handle_run_updates,
        schema=RUN_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN,
        async_handle_scan,
        schema=SCAN_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXCLUDE_ENTITIES,
        async_handle_exclude_entities,
        schema=ENTITY_LIST_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_INCLUDE_ENTITIES,
        async_handle_include_entities,
        schema=ENTITY_LIST_SERVICE_SCHEMA,
    )
    hass.data[DOMAIN][DATA_SERVICES_REGISTERED] = True


def _selected_managers(
    hass: HomeAssistant, call_data: dict[str, Any]
) -> list[AutoUpdateManager]:
    """Return managers selected by a service call."""
    managers = list(hass.data[DOMAIN][DATA_MANAGERS].values())
    config_entry_id = call_data.get("config_entry_id")
    if config_entry_id:
        managers = [
            manager
            for manager in managers
            if manager.entry.entry_id == config_entry_id
        ]
    return managers
