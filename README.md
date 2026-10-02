# Aktien-Tracker für Home Assistant

Custom-Integration für den [Aktien-Tracker](https://github.com/NiklasM-foss/aktien-tracker),
eine Live-Kursanzeige für ein Planspiel-Börse-Depot. Die Integration liest das
ausgewertete Depot über `/api/summary` und stellt es als Sensoren bereit. Sie
rechnet nichts selbst, die Zahlen sind also dieselben wie auf der Webseite.

## Installation

### HACS (benutzerdefiniertes Repository)

1. HACS → Integrationen → Menü oben rechts → **Benutzerdefinierte Repositories**
2. URL `https://github.com/NiklasM-foss/ha-aktien-tracker`, Kategorie **Integration**
3. **Aktien-Tracker** installieren und Home Assistant neu starten

### Manuell

Den Ordner `custom_components/aktien_tracker` nach `config/custom_components/`
kopieren und Home Assistant neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → **Integration hinzufügen** → *Aktien-Tracker*.

| Feld    | Bedeutung |
|---------|-----------|
| Adresse | Adresse des Trackers, z.B. `https://aktien.niklasmetzger.de` oder `http://192.168.177.28:8080` |
| Name    | Name des Depot-Geräts, Standard *Aktien-Tracker* |

Beim Speichern wird der Tracker einmal abgefragt. Über **Neu konfigurieren**
lassen sich Adresse und Name später ändern, ohne den Eintrag zu löschen. Unter
**Optionen** steht das Abfrageintervall (Standard 60 s, mindestens 15 s).

## Entitäten

**Depot** (ein Gerät), alle Beträge in Euro:

| Sensor | Inhalt |
|--------|--------|
| Gesamtvermögen | Startkapital minus Bezahltes plus Depotwert. Attribute: Startkapital, Anzahl Aktien, EUR/USD, Stand, Fehler |
| Depotwert | aktueller Wert aller Positionen |
| Verfügbares Geld | Startkapital minus Bezahltes inkl. Gebühren |
| Gewinn/Verlust | inkl. Gebühren |
| Gewinn/Verlust Prozent | bezogen auf das Bezahlte |
| Gewinn ohne Gebühren | |
| Heute | Veränderung seit gestrigem Schluss bzw. seit Kauf, wenn heute gekauft |
| Bezahlt inkl. Gebühren, Gebühren | standardmäßig deaktiviert |

**Je Aktie** (eigenes Gerät unter dem Depot):

| Sensor | Inhalt |
|--------|--------|
| Kurs | in Kurswährung. Attribute: Name, ISIN, Kurs in Euro, Veränderung in %, Quelle (Tradegate/Yahoo) |
| Wert | Positionswert in Euro. Attribute: Stück, Kaufpreis, Gebühren, Kaufzeit |
| Gewinn/Verlust | in Euro, Attribut Prozent |
| Heute | Veränderung heute in Euro |

Wird auf der Webseite eine Aktie hinzugefügt, bekommt sie beim nächsten Abruf
ihre Sensoren. Das Gerät einer entfernten Aktie wird samt Sensoren gelöscht.

## Beispiel

Die Entity-IDs entstehen aus dem Gerätenamen und den Sensornamen in der
Systemsprache, bei deutschem Home Assistant und Name *Aktien-Tracker* also z.B.
`sensor.aktien_tracker_gesamtvermogen`, `sensor.aktien_tracker_heute` und je
Aktie `sensor.nvda_kurs`.

Tägliche Zusammenfassung um 22:15:

```yaml
triggers:
  - trigger: time
    at: "22:15:00"
actions:
  - action: notify.notify
    data:
      message: >
        Depot {{ states('sensor.aktien_tracker_gesamtvermogen') | float | round(2) }} €,
        heute {{ states('sensor.aktien_tracker_heute') | float | round(2) }} €
```

## Lizenz

MIT
