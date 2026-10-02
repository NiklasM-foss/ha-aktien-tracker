# Zentrale Konstanten der Aktien-Tracker-Integration.

from __future__ import annotations

DOMAIN = "aktien_tracker"

PLATFORMS = ["sensor"]

CONF_URL = "url"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval_seconds"

DEFAULT_URL = "https://aktien.niklasmetzger.de"
DEFAULT_NAME = "Aktien-Tracker"
# Der Tracker selbst holt Kurse alle paar Sekunden; für Home Assistant reicht
# eine Minute, kürzer bringt in den Verläufen kaum etwas.
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
