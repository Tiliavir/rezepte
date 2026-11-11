*In contrast to my other repositories this one is in German, since the recipes are German.*

[![Build State](https://github.com/Tiliavir/rezepte/workflows/Build%20on%20Push/badge.svg)](https://github.com/Tiliavir/rezepte/actions?query=workflow%3A%22Build+on+Push%22)
&nbsp;
[![Publish State](https://github.com/Tiliavir/rezepte/workflows/Publish%20to%20GH%20Pages%20on%20Tag/badge.svg)](https://github.com/Tiliavir/rezepte/actions?query=workflow%3A%22Publish+to+GH+Pages+on+Tag%22)

# Die Gute-Sachen Liste

Unsere Rezeptsammlung – [auf GitHub Pages](https://tiliavir.github.io/rezepte/).
Mit Suche, Portionsrechner und Einkaufsliste.

## Lokal starten

Voraussetzungen: [Hugo extended](https://gohugo.io/installation/) 0.169+, Node.js 22.12+, Java (für die HTML-Validierung).

```bash
npm ci
npm start          # hugo server, ohne Suchindex
npm run lint       # Biome + TypeScript
npm run build      # Hugo → CSP-Hashes → Suchindex → HTML-Validierung
```

## Rezept hinzufügen

```bash
hugo new --kind recipe-bundle recipes/rezeptname
```

Oder mit dem Skill `recipe-normalizer` (`.claude/skills/`) aus einer URL, einem Foto oder PDF.
Bilder vorher verkleinern: `mogrify -strip -resize 2000x2000 **/*.jpg`

### Komponenten

Rezepte mit eigenständigen Bestandteilen (Teig, Füllung, Sauce …) listen diese unter `components`:

```yaml
components:
- title: Teig            # inline: gehört nur zu diesem Rezept
  ingredients: [...]
  directions: [...]
  notes: Optionaler Hinweis (Markdown)
- "Quiche Teig"          # Verweis per Titel auf eine geteilte Komponente oder ein anderes Rezept
```

Geteilte Komponenten liegen unter `content/components/` – nur für Bausteine, die mehrere Rezepte nutzen.

## Aufbau

Kein externes Theme: `layouts/` (Hugo-Templates), `assets/css/` (reines CSS, nach Dateiname zusammengefügt),
`assets/ts/` (TypeScript, gebündelt von Hugo). Schrift (Fraunces, OFL) liegt unter `static/fonts/`;
die Seite lädt nichts von fremden Servern.
