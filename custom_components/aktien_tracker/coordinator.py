"""
DataUpdateCoordinator: holt das ausgewertete Depot in einem festen Intervall.

Die Aktien im Depot können sich jederzeit ändern (auf der Webseite lassen sich
Aktien hinzufügen und entfernen). Der Coordinator legt die Liste deshalb
zusätzlich als Dict nach Symbol ab, die Sensor-Plattform gleicht sie bei jedem
Refresh mit den vorhandenen Entities ab.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AktienTrackerClient, TrackerResponseError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AktienTrackerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Hält die letzte Auswertung des Depots."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: AktienTrackerClient) -> None:
        seconds = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=seconds))
        self.client = client
        self.depot_device_id: str | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.async_get_summary()
        except TrackerResponseError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Aktien-Tracker nicht erreichbar: {err}") from err
        if data.get("errors"):
            _LOGGER.debug("Keine Kurse für %s", ", ".join(data["errors"]))
        data["by_symbol"] = {s["symbol"]: s for s in data["stocks"] if s.get("symbol")}
        return data

    def stock(self, symbol: str) -> dict[str, Any] | None:
        return (self.data or {}).get("by_symbol", {}).get(symbol)
