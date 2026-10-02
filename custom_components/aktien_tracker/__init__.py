"""
Setup-Einstiegspunkt der Aktien-Tracker-Integration.

Pro ConfigEntry ein Coordinator, der `/api/summary` des Trackers abfragt und
die Werte an die Sensoren verteilt.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import AktienTrackerClient
from .const import CONF_NAME, CONF_URL, DEFAULT_NAME, DEFAULT_URL, DOMAIN, PLATFORMS
from .coordinator import AktienTrackerCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = AktienTrackerClient(async_get_clientsession(hass), entry.data.get(CONF_URL, DEFAULT_URL))
    coordinator = AktienTrackerCoordinator(hass, entry, client)

    # Erster Refresh synchron: scheitert er, versucht HA das Setup später erneut
    await coordinator.async_config_entry_first_refresh()

    # Depot-Gerät vorab anlegen: die Geräte der einzelnen Aktien hängen über
    # seine Registry-ID darunter (via_device_id)
    depot = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME) or DEFAULT_NAME,
        manufacturer="Aktien-Tracker",
        model="Depot",
        configuration_url=entry.data.get(CONF_URL),
    )
    coordinator.depot_device_id = depot.id

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry) -> bool:
    """Geräte einzelner Aktien darf man löschen, sobald sie nicht mehr im Depot sind."""
    coordinator: AktienTrackerCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        return True
    prefix = f"{entry.entry_id}_"
    for domain, ident in device.identifiers:
        if domain == DOMAIN and ident.startswith(prefix) and coordinator.stock(ident[len(prefix):]):
            return False
    return not any(domain == DOMAIN and ident == entry.entry_id for domain, ident in device.identifiers)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload, wenn sich das Abfrageintervall ändert."""
    await hass.config_entries.async_reload(entry.entry_id)
