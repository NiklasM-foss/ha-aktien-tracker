"""
Config-Flow.

Ein Schritt: Adresse des Trackers (vorbelegt) und optional ein Name. Beim
Absenden wird `/api/summary` einmal abgefragt, damit eine falsche Adresse
sofort auffällt statt erst beim ersten Refresh.

Über „Neu konfigurieren" lassen sich Adresse und Name später ändern, ohne den
Eintrag zu löschen; geprüft wird dort genauso wie bei der Einrichtung. Das
Abfrageintervall steht in den Optionen.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AktienTrackerClient, TrackerResponseError, normalize_url
from .const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_URL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _schema(url: str, name: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=url): str,
            vol.Optional(CONF_NAME, default=name): str,
        }
    )


class AktienTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Einrichtung und Neu-Konfiguration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "AktienTrackerOptionsFlow":
        return AktienTrackerOptionsFlow(config_entry)

    async def _async_validate(self, url: str) -> dict[str, str]:
        """Fragt den Tracker einmal ab und liefert die Fehler fürs Formular."""
        client = AktienTrackerClient(async_get_clientsession(self.hass), url)
        try:
            await client.async_get_summary()
        except TrackerResponseError:
            return {"base": "invalid_response"}
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Aktien-Tracker nicht erreichbar: %s (%s)", url, err)
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            name = user_input.get(CONF_NAME, "").strip() or DEFAULT_NAME
            # Pro Tracker-Adresse nur ein Eintrag
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            errors = await self._async_validate(url)
            if not errors:
                return self.async_create_entry(
                    title=name,
                    data={CONF_URL: url, CONF_NAME: name},
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )
        current = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(current.get(CONF_URL, DEFAULT_URL), current.get(CONF_NAME, DEFAULT_NAME)),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Adresse und Name eines bestehenden Eintrags ändern."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            name = user_input.get(CONF_NAME, "").strip() or DEFAULT_NAME
            if any(
                other.unique_id == url and other.entry_id != entry.entry_id
                for other in self._async_current_entries(include_ignore=False)
            ):
                errors["base"] = "already_configured"
            else:
                errors = await self._async_validate(url)
            if not errors:
                # Titel nur anfassen, wenn sich der Name geändert hat, sonst ginge
                # eine Umbenennung in der Oberfläche verloren
                title = name if name != entry.data.get(CONF_NAME) else entry.title
                return self.async_update_reload_and_abort(
                    entry, unique_id=url, title=title, data_updates={CONF_URL: url, CONF_NAME: name}
                )
        current = user_input or entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(
                current.get(CONF_URL, DEFAULT_URL), current.get(CONF_NAME, entry.title or DEFAULT_NAME)
            ),
            errors=errors,
        )


class AktienTrackerOptionsFlow(config_entries.OptionsFlow):
    """Nachträgliche Option: Abfrageintervall."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)
                    ),
                }
            ),
        )
