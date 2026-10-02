"""
Sensor-Plattform.

Depot (ein Gerät): Gesamtvermögen, Depotwert, verfügbares Geld, Gewinn/Verlust
in Euro und Prozent, Gewinn ohne Gebühren, heutige Veränderung, Bezahlt und
Gebühren.

Je Aktie (eigenes Gerät unter dem Depot): Kurs in Kurswährung, Wert,
Gewinn/Verlust und heutige Veränderung in Euro.

Aktien kommen und gehen mit dem Depot auf der Webseite. Neue Aktien bekommen
beim nächsten Refresh ihre Sensoren, das Gerät einer entfernten Aktie wird samt
Sensoren aus der Registry gelöscht.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, CONF_URL, DEFAULT_NAME, DOMAIN
from .coordinator import AktienTrackerCoordinator

EUR = "EUR"


@dataclass(frozen=True, kw_only=True)
class AktienSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


def _desc(key: str, field: str, unit: str | None = EUR, precision: int = 2, **kw: Any) -> AktienSensorDescription:
    return AktienSensorDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=unit,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=precision,
        value_fn=lambda d, f=field: d.get(f),
        **kw,
    )


DEPOT_SENSORS: tuple[AktienSensorDescription, ...] = (
    _desc("gesamtvermoegen", "total"),
    _desc("depotwert", "value"),
    _desc("verfuegbar", "cash"),
    _desc("gewinn_verlust", "pl"),
    _desc("gewinn_verlust_prozent", "pl_pct", PERCENTAGE),
    _desc("gewinn_ohne_gebuehren", "pl_ex_fees"),
    _desc("heute", "day"),
    _desc("bezahlt", "paid", entity_registry_enabled_default=False),
    _desc("gebuehren", "fees", entity_registry_enabled_default=False),
)

STOCK_SENSORS: tuple[AktienSensorDescription, ...] = (
    # Einheit des Kurses ist die Kurswährung der Aktie, siehe StockSensor
    _desc("kurs", "price", None),
    _desc("wert", "value"),
    _desc("aktie_gewinn_verlust", "pl"),
    _desc("aktie_heute", "day"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: AktienTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(DepotSensor(coordinator, entry, d) for d in DEPOT_SENSORS)

    known: set[str] = set()
    dev_reg = dr.async_get(hass)

    @callback
    def _sync_stocks() -> None:
        if not coordinator.data:
            return
        current = set(coordinator.data["by_symbol"])
        new = current - known
        if new:
            async_add_entities(
                StockSensor(coordinator, entry, symbol, d) for symbol in sorted(new) for d in STOCK_SENSORS
            )
            known.update(new)
        # Geräte von Aktien, die nicht mehr im Depot sind, samt Sensoren entfernen.
        # Nur bei vollständiger Antwort, sonst verschwände eine Aktie schon, wenn
        # Yahoo für sie gerade keine Kurse liefert.
        if coordinator.data.get("errors"):
            return
        prefix = f"{entry.entry_id}_"
        for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            for domain, ident in device.identifiers:
                if domain == DOMAIN and ident.startswith(prefix) and ident[len(prefix):] not in current:
                    dev_reg.async_remove_device(device.id)
                    known.discard(ident[len(prefix):])

    _sync_stocks()
    entry.async_on_unload(coordinator.async_add_listener(_sync_stocks))


def _depot_device(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME) or DEFAULT_NAME,
        manufacturer="Aktien-Tracker",
        model="Depot",
        configuration_url=entry.data.get(CONF_URL),
    )


class DepotSensor(CoordinatorEntity[AktienTrackerCoordinator], SensorEntity):
    """Kennzahl des ganzen Depots."""

    _attr_has_entity_name = True
    entity_description: AktienSensorDescription

    def __init__(self, coordinator: AktienTrackerCoordinator, entry: ConfigEntry, description: AktienSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _depot_device(entry)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "gesamtvermoegen" or not self.coordinator.data:
            return None
        d = self.coordinator.data
        return {
            "startkapital": d.get("start_capital"),
            "anzahl_aktien": len(d.get("stocks", [])),
            "eur_usd": d.get("eurusd"),
            "stand": d.get("updated"),
            "vollstaendig": d.get("complete"),
            "fehler": d.get("errors") or None,
        }


class StockSensor(CoordinatorEntity[AktienTrackerCoordinator], SensorEntity):
    """Kennzahl einer einzelnen Aktie."""

    _attr_has_entity_name = True
    entity_description: AktienSensorDescription

    def __init__(
        self,
        coordinator: AktienTrackerCoordinator,
        entry: ConfigEntry,
        symbol: str,
        description: AktienSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._symbol = symbol
        self._attr_unique_id = f"{entry.entry_id}_{symbol}_{description.key}"
        stock = coordinator.stock(symbol) or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{symbol}")},
            name=stock.get("short") or symbol,
            manufacturer="Aktien-Tracker",
            model=f"{stock.get('name') or symbol} ({symbol})",
            serial_number=stock.get("isin"),
        )
        # Ab HA 2026.8 über die Registry-ID des Depot-Geräts, davor über dessen Kennung
        if "via_device_id" in DeviceInfo.__annotations__ and coordinator.depot_device_id:
            self._attr_device_info["via_device_id"] = coordinator.depot_device_id
        else:
            self._attr_device_info["via_device"] = (DOMAIN, entry.entry_id)

    @property
    def _stock(self) -> dict[str, Any] | None:
        return self.coordinator.stock(self._symbol)

    @property
    def available(self) -> bool:
        return super().available and self._stock is not None

    @property
    def native_value(self) -> Any:
        stock = self._stock
        return self.entity_description.value_fn(stock) if stock else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.key == "kurs":
            return (self._stock or {}).get("currency")
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        stock = self._stock
        if not stock:
            return None
        key = self.entity_description.key
        if key == "kurs":
            return {
                "symbol": self._symbol,
                "name": stock.get("name"),
                "isin": stock.get("isin"),
                "kurs_eur": stock.get("price_eur"),
                "veraenderung_prozent": stock.get("change_pct"),
                "quelle": stock.get("source"),
            }
        if key == "wert":
            return {
                "stueck": stock.get("qty"),
                "kaufpreis": stock.get("cost"),
                "gebuehren": stock.get("fees"),
                "gekauft": stock.get("bought"),
            }
        if key == "aktie_gewinn_verlust":
            return {"prozent": stock.get("pl_pct")}
        if key == "aktie_heute":
            return {"seit_kauf_heute": stock.get("bought_today")}
        return None
