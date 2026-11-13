# Changelog

Wichtige Änderungen an der Seite. Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/);
Versionen nach Datum (`JJJJ.M.T`, ohne führende Nullen). Veröffentlichen: siehe [README](README.md#veröffentlichen).
Ältere Versionen ohne Changelog: Git-Tags `2024.06.16` bis `2026.10.13`.

## [2026.11.13] - 2026-11-13

### Neu

- Als App installierbar (Web-App-Manifest und App-Icons): auf Android über „App installieren“ im Chrome-Menü.

## [2026.11.11] - 2026-11-11

### Neu

- Eigenes Design: Terrakotta-Farben, Überschriften in Instrument Serif, Dark Mode (folgt dem System, umschaltbar), Navigation unten auf dem Handy.
- Suche über alle Rezepte, direkt auf der Startseite, kombinierbar mit Kategorien.
- Rezeptseite: Komponenten als Abschnitte, Zutaten und Schritte abhaken, Portionsrechner, Bildschirm anlassen, Druckansicht.
- Einkaufsliste neu: Mengen werden über Rezepte und Einheiten zusammengerechnet, nach Regalen sortiert, eigene Einträge, abhaken, teilen.
- Seite „Entdecken“ mit Kategorien, Küchen und Tags.

### Geändert

- Komponenten, die nur ein Rezept nutzt, stehen jetzt direkt im Rezept.
- Die Seite lädt nichts mehr von fremden Servern (Schriften und Styles liegen auf der Seite selbst).
- Veröffentlicht wird automatisch, sobald eine neue Version auf `main` landet.
