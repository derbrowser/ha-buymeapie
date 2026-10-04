# Buy Me a Pie für Home Assistant

Bindet deine [Buy Me a Pie](https://app.buymeapie.com)-Einkaufslisten als
**Todo-Listen** in Home Assistant ein. Jede Liste wird eine `todo.*`-Entität.

> Inoffiziell: Buy Me a Pie hat keine dokumentierte API. Die Integration nutzt
> dieselben Endpoints wie die Web-App und kann brechen, wenn sich diese ändern.

## Funktionen

- Eine Todo-Entität pro Liste, neue Listen erscheinen automatisch
- Artikel hinzufügen, umbenennen, abhaken (= gekauft), löschen
- Menge im Feld „Beschreibung“ (z. B. `2` oder `500 g`)
- Funktioniert mit der Todo-Karte, `todo.add_item`, `todo.update_item`,
  `todo.remove_completed_items` und Sprachassistenten
- Aktualisierung per Polling alle 60 Sekunden
- Re-Auth-Flow, falls sich die PIN ändert

## Installation

1. Ordner `custom_components/buymeapie` nach `<config>/custom_components/` kopieren
   (oder das Repo als benutzerdefiniertes Repository in HACS hinzufügen).
2. Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Buy Me a Pie*.
4. E-Mail und PIN deines Kontos eingeben.

## Beispiele

Artikel zur Einkaufsliste hinzufügen:

```yaml
action: todo.add_item
target:
  entity_id: todo.einkaufsliste
data:
  item: Milch
  description: "2"
```

Gekaufte Artikel aufräumen:

```yaml
action: todo.remove_completed_items
target:
  entity_id: todo.einkaufsliste
```
