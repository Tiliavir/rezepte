---
name: recipe-normalizer
description: Übernimmt ein Rezept (URL, Text, Markdown, HTML, Bild oder PDF) in dieses Repo – auf Deutsch, mit metrischen Einheiten, als Hugo-Rezept unter content/recipes/. Verwenden, wenn ein Rezept hinzugefügt, importiert oder übernommen werden soll.
---

# Rezept übernehmen

Lies die Quelle, normalisiere das Rezept nach den Regeln unten und lege es als
Markdown-Datei mit YAML-Front-Matter unter `content/recipes/` an. Du bist dabei
Koch und YAML-Experte zugleich: Mengen und Abläufe müssen fachlich stimmen, das
YAML muss gültig sein.

## Ablauf

1. **Quelle lesen**
   - URL: Seite abrufen, nur die Rezeptkarte und relevante Hinweise verwenden
     (Navigation, Kommentare, Werbung ignorieren).
   - Text/Markdown: direkt lesen.
   - HTML: Hauptinhalt extrahieren.
   - Bild: Text erkennen (OCR).
   - PDF: Text extrahieren, OCR als Fallback.
2. **Duplikat prüfen**: In `content/recipes/` nach Titel und Hauptzutat suchen.
   Gibt es ein ähnliches Rezept, nachfragen, bevor eine Kopie entsteht.
3. **Normalisieren** nach den Regeln unten.
4. **Dateien schreiben** (eine pro Rezept bzw. Komponente).
5. **YAML prüfen**: Jede Datei muss sich fehlerfrei parsen lassen.
6. **Auf einem Branch committen und einen PR gegen `main` öffnen** – nicht direkt
   auf `main` pushen.

## Regeln

1. Sprache immer Deutsch.
2. Einheiten metrisch:
   - tbsp → EL, tsp → TL
   - cups → ml/l (Flüssigkeiten) bzw. g/kg (feste Zutaten, nach Zutat umrechnen)
   - oz → g, lb → g/kg
   - °F → °C
   - inch/feet → cm/m
3. Mengen korrekt umrechnen und sinnvoll runden (z.B. 226 g → 225 g).
4. Mengenschreibweise: Zahl direkt vor der Einheit, `200g`, `100ml`, `2 EL`, `1 TL`,
   Brüche als `1/2`.
5. Keine Zutaten ergänzen oder weglassen. Fehlt eine Menge in der Quelle, Zutat
   ohne Menge übernehmen.
6. Anleitung: präzise, kurz, aktiv formuliert, ein Arbeitsschritt pro Listeneintrag,
   keine Füllsätze. In eigenen Worten formulieren – keinen Blogtext kopieren.
7. Ofenart (Ober-/Unterhitze, Umluft), Temperatur und Formgröße übernehmen, wenn
   angegeben.
8. Unklarheiten (fehlende Portionszahl, widersprüchliche Mengen, unlesbare Stellen)
   nachfragen statt raten.

## Komponenten

Hat ein Rezept klar getrennte Bestandteile mit eigenen Zutaten (Teig, Füllung,
Sauce, Topping …), wird jeder Bestandteil ein eigenes Rezept:

- **Titel**: `"<Hauptrezept>: <Bestandteil>"`, z.B. `"Kürbiskuchen: Frischkäse-Topping"`.
  Wegen des Doppelpunkts **immer in Anführungszeichen**.
- **Slug**: `<slug-hauptrezept>-<bestandteil>`, z.B. `kuerbiskuchen-frischkaese-topping`.
- Das Hauptrezept referenziert die Komponenten unter `components` mit exakt
  demselben Titel.
- Komponenten haben nur `layout`, `date`, `title`, `ingredients`, `directions`.
- Das `date` der Komponenten liegt eine Minute vor dem Hauptrezept.

Nicht aufteilen, wenn ein „Bestandteil“ nur aus Zutaten besteht, die im selben
Arbeitsschritt verarbeitet werden.

## Dateiformat

Pfad: `content/recipes/<slug>/index.md`

- **Slug**: aus dem Titel, kleingeschrieben, nur `a-z`, `0-9` und `-`.
  Umlaute umschreiben: ä→ae, ö→oe, ü→ue, ß→ss.
- **Datum**: ISO 8601 mit Zeitzone Europe/Berlin, z.B. `2026-11-02T21:07:00+01:00`.
- Encoding UTF-8.

### Felder

| Feld | Pflicht | Hinweis |
|------|---------|---------|
| `layout` | ja | immer `recipe` |
| `date` | ja | siehe oben |
| `title` | ja | in Anführungszeichen |
| `authorName` | wenn bekannt | Autor:in der Quelle |
| `authorURL` | optional | Profil- oder Über-mich-Seite |
| `sourceName` | wenn bekannt | Originaltitel des Rezepts |
| `sourceURL` | bei URL-Quelle | Link zum Original |
| `image` | optional | nur eigene Fotos im Rezeptordner, keine Bilder der Quelle |
| `category` | ja | einer der Werte unten |
| `cuisine` | optional | Landesküche, z.B. `Deutsch`, `Italienisch`, `Japanisch` |
| `tags` | optional | Hauptzutat, Anlass, Saison, Ernährungsform |
| `yield` | ja | mit Einheit: `4 Portionen`, `12 Stück`, `1 Kuchen` |
| `prepTime` | optional | Minuten, nur Zahl |
| `cookTime` | optional | Minuten, nur Zahl |
| `ingredients` | ja* | *entfällt, wenn alles in Komponenten steckt |
| `components` | optional | Titel der Komponenten |
| `directions` | ja | |

**Erlaubte Kategorien**: `Hauptgericht`, `Beilage`, `Vorspeise`, `Salat`, `Suppe`,
`Kuchen`, `Gebäck`, `Dessert`, `Sauce`, `Dip`, `Dressing`, `Teig`, `Marmelade`,
`Getränke`, `Grundkomponente`.

`Vegan`, `Vegetarisch` oder Jahreszeiten gehören in `tags`, nicht in `cuisine`.

### Text unter dem Front-Matter

Optional. Nur kurze eigene Hinweise, die beim Nachkochen helfen (Lagerung,
Austauschzutaten, kritische Stellen) – in eigenen Worten, kein kopierter Blogtext.

## Beispiel

`content/recipes/kuerbiskuchen/index.md`

```yaml
---
layout: recipe
date: 2026-11-02T21:07:00+01:00

title: "Kürbiskuchen nach Omas Rezept"

authorName: Bianca Zapatka
authorURL: https://biancazapatka.com/de/ueber-mich/
sourceName: Saftiger Kürbiskuchen nach Omas Rezept
sourceURL: https://biancazapatka.com/de/kuerbiskuchen-rezept/

category: Kuchen
cuisine: Deutsch
tags:
- Kürbis
- Herbst
- Vegan

yield: 12 Stück
prepTime: 20
cookTime: 50

ingredients:
- 200g Hokkaido-Kürbis
- 180g Mehl
- 2 TL Backpulver
- 1 Bio-Orange (Saft und Schale)
- 100ml Öl

components:
- "Kürbiskuchen: Frischkäse-Topping"

directions:
- Ofen auf 180°C Ober-/Unterhitze vorheizen, eine 20cm Backform vorbereiten.
- Kürbis mit Schale fein raspeln.
- Teig in die Form füllen und ca. 50 Minuten backen.
- Topping zubereiten und auf dem ausgekühlten Kuchen verteilen.
---

Hokkaido muss nicht geschält werden, andere Kürbissorten schon.
```

`content/recipes/kuerbiskuchen-frischkaese-topping/index.md`

```yaml
---
layout: recipe
date: 2026-11-02T21:06:00+01:00

title: "Kürbiskuchen: Frischkäse-Topping"

ingredients:
- 200g veganer Frischkäse
- 50g Puderzucker

directions:
- Frischkäse mit Puderzucker cremig mixen.
---
```
