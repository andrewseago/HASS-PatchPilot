"""Config flow for PatchPilot."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)
import voluptuous as vol

from .const import (
    CONF_CHECK_INTERVAL_MINUTES,
    CONF_CREATE_BACKUP,
    CONF_ENABLED,
    CONF_EXCLUDE_PATTERNS,
    CONF_EXCLUDED_ENTITIES,
    CONF_INCLUDE_PATTERNS,
    CONF_LOG_SIZE,
    CONF_MAX_UPDATES_PER_RUN,
    CONF_NOTIFY_ON_FAILURE,
    CONF_RUN_ON_STATE_CHANGE,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    DEFAULT_CHECK_INTERVAL_MINUTES,
    DEFAULT_CREATE_BACKUP,
    DEFAULT_ENABLED,
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_EXCLUDED_ENTITIES,
    DEFAULT_INCLUDE_PATTERNS,
    DEFAULT_LOG_SIZE,
    DEFAULT_MAX_UPDATES_PER_RUN,
    DEFAULT_NOTIFY_ON_FAILURE,
    DEFAULT_RUN_ON_STATE_CHANGE,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DOMAIN,
)
from .update_logic import parse_time


class PatchPilotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a PatchPilot config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title="PatchPilot",
                    data=_normalize_input(user_input),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return PatchPilotOptionsFlow(config_entry)


class PatchPilotOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            errors = _validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title="",
                    data=_normalize_input(user_input),
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or current),
            errors=errors,
        )


def _schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Return config/options schema."""
    values = values or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_ENABLED,
                default=values.get(CONF_ENABLED, DEFAULT_ENABLED),
            ): BooleanSelector(),
            vol.Optional(
                CONF_CHECK_INTERVAL_MINUTES,
                default=values.get(
                    CONF_CHECK_INTERVAL_MINUTES, DEFAULT_CHECK_INTERVAL_MINUTES
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=1440,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Optional(
                CONF_WINDOW_START,
                default=values.get(CONF_WINDOW_START, DEFAULT_WINDOW_START),
            ): TextSelector(TextSelectorConfig()),
            vol.Optional(
                CONF_WINDOW_END,
                default=values.get(CONF_WINDOW_END, DEFAULT_WINDOW_END),
            ): TextSelector(TextSelectorConfig()),
            vol.Optional(
                CONF_INCLUDE_PATTERNS,
                default=_patterns_to_text(
                    values.get(CONF_INCLUDE_PATTERNS, DEFAULT_INCLUDE_PATTERNS)
                ),
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_EXCLUDE_PATTERNS,
                default=_patterns_to_text(
                    values.get(CONF_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_PATTERNS)
                ),
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_EXCLUDED_ENTITIES,
                default=values.get(CONF_EXCLUDED_ENTITIES, DEFAULT_EXCLUDED_ENTITIES),
            ): EntitySelector(EntitySelectorConfig(domain="update", multiple=True)),
            vol.Optional(
                CONF_CREATE_BACKUP,
                default=values.get(CONF_CREATE_BACKUP, DEFAULT_CREATE_BACKUP),
            ): BooleanSelector(),
            vol.Optional(
                CONF_MAX_UPDATES_PER_RUN,
                default=values.get(
                    CONF_MAX_UPDATES_PER_RUN, DEFAULT_MAX_UPDATES_PER_RUN
                ),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=100, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_RUN_ON_STATE_CHANGE,
                default=values.get(
                    CONF_RUN_ON_STATE_CHANGE, DEFAULT_RUN_ON_STATE_CHANGE
                ),
            ): BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_ON_FAILURE,
                default=values.get(CONF_NOTIFY_ON_FAILURE, DEFAULT_NOTIFY_ON_FAILURE),
            ): BooleanSelector(),
            vol.Optional(
                CONF_LOG_SIZE,
                default=values.get(CONF_LOG_SIZE, DEFAULT_LOG_SIZE),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=100, mode=NumberSelectorMode.BOX)
            ),
        }
    )


def _validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate config/options input."""
    errors: dict[str, str] = {}
    for key in (CONF_WINDOW_START, CONF_WINDOW_END):
        try:
            parse_time(str(user_input[key]))
        except (KeyError, ValueError):
            errors[key] = "invalid_time"
    if not _patterns_to_list(user_input.get(CONF_INCLUDE_PATTERNS, "")):
        errors[CONF_INCLUDE_PATTERNS] = "empty_include_patterns"
    return errors


def _normalize_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize saved values."""
    data = dict(user_input)
    data[CONF_CHECK_INTERVAL_MINUTES] = int(data[CONF_CHECK_INTERVAL_MINUTES])
    data[CONF_MAX_UPDATES_PER_RUN] = int(data[CONF_MAX_UPDATES_PER_RUN])
    data[CONF_LOG_SIZE] = int(data[CONF_LOG_SIZE])
    data[CONF_INCLUDE_PATTERNS] = _patterns_to_list(data[CONF_INCLUDE_PATTERNS])
    data[CONF_EXCLUDE_PATTERNS] = _patterns_to_list(data[CONF_EXCLUDE_PATTERNS])
    data[CONF_EXCLUDED_ENTITIES] = _patterns_to_list(
        data.get(CONF_EXCLUDED_ENTITIES, [])
    )
    return data


def _patterns_to_list(value: Any) -> list[str]:
    """Convert a multiline string or list to patterns."""
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _patterns_to_text(value: Any) -> str:
    """Convert pattern list to multiline text."""
    if isinstance(value, str):
        return value
    return "\n".join(str(item) for item in value)
