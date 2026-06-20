"""Constants for PatchPilot."""

from __future__ import annotations

from datetime import time

DOMAIN = "patchpilot"
PLATFORMS = ["sensor"]

CONF_ENABLED = "enabled"
CONF_CHECK_INTERVAL_MINUTES = "check_interval_minutes"
CONF_WINDOW_START = "window_start"
CONF_WINDOW_END = "window_end"
CONF_INCLUDE_PATTERNS = "include_patterns"
CONF_EXCLUDE_PATTERNS = "exclude_patterns"
CONF_EXCLUDED_ENTITIES = "excluded_entities"
CONF_CREATE_BACKUP = "create_backup"
CONF_MAX_UPDATES_PER_RUN = "max_updates_per_run"
CONF_RUN_ON_STATE_CHANGE = "run_on_state_change"
CONF_NOTIFY_ON_FAILURE = "notify_on_failure"
CONF_LOG_SIZE = "log_size"

DEFAULT_ENABLED = True
DEFAULT_CHECK_INTERVAL_MINUTES = 60
DEFAULT_WINDOW_START = "03:00:00"
DEFAULT_WINDOW_END = "05:00:00"
DEFAULT_INCLUDE_PATTERNS = ["update.*"]
DEFAULT_EXCLUDE_PATTERNS: list[str] = []
DEFAULT_EXCLUDED_ENTITIES: list[str] = []
DEFAULT_CREATE_BACKUP = True
DEFAULT_MAX_UPDATES_PER_RUN = 0
DEFAULT_RUN_ON_STATE_CHANGE = True
DEFAULT_NOTIFY_ON_FAILURE = True
DEFAULT_LOG_SIZE = 25

SERVICE_RUN_UPDATES = "run_updates"
SERVICE_SCAN = "scan"
SERVICE_EXCLUDE_ENTITIES = "exclude_entities"
SERVICE_INCLUDE_ENTITIES = "include_entities"

ATTR_ENTITY_ID = "entity_id"
ATTR_IGNORE_WINDOW = "ignore_window"
ATTR_DRY_RUN = "dry_run"

DATA_MANAGERS = "managers"
DATA_SERVICES_REGISTERED = "services_registered"

STATE_PENDING = "on"
STATE_CLEAR = "off"

TIME_ZERO = time(0, 0, 0)
