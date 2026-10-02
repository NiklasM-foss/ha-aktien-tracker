"""
Client für den Aktien-Tracker.

Der Tracker rechnet das Depot selbst aus und liefert es unter `/api/summary`
als JSON: Gesamtvermögen, Depotwert, Gewinn/Verlust und je Aktie Kurs, Wert
und Gewinn, alle Beträge schon in Euro. Die Integration muss deshalb nichts
nachrechnen und zeigt dieselben Zahlen wie die Webseite.
"""

from __future__ import annotations

from typing import Any

import aiohttp

_TIMEOUT = aiohttp.ClientTimeout(total=30)


class TrackerResponseError(Exception):
    """Server erreichbar, aber die Antwort ist kein Aktien-Tracker."""


class AktienTrackerClient:
    """Asynchroner Client, wird vom Coordinator pro Refresh genutzt."""

    def __init__(self, session: aiohttp.ClientSession, url: str) -> None:
        self._session = session
        self._url = normalize_url(url)

    @property
    def url(self) -> str:
        return self._url

    async def async_get_summary(self) -> dict[str, Any]:
        async with self._session.get(f"{self._url}/api/summary", timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            try:
                data = await resp.json(content_type=None)
            except ValueError as err:
                raise TrackerResponseError("Antwort ist kein JSON") from err
        if not isinstance(data, dict) or not isinstance(data.get("stocks"), list):
            raise TrackerResponseError("Antwort enthält kein Depot")
        return data


def normalize_url(url: str) -> str:
    """Leerzeichen und abschließende Schrägstriche weg, Schema ergänzen."""
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url
