"""Constants for the Buy Me a Pie integration."""

from datetime import timedelta

DOMAIN = "buymeapie"

CONF_PIN = "pin"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

# Persisted set of "ghost" item ids: the API still lists them, but they no
# longer exist server-side (PUT/DELETE answer 404).
GHOST_STORAGE_VERSION = 1
