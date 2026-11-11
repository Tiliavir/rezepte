*In contrast to my other repositories this one is in German, since the recipes are German.*

[![CI](https://github.com/Tiliavir/rezepte/actions/workflows/ci.yml/badge.svg)](https://github.com/Tiliavir/rezepte/actions/workflows/ci.yml)

# Die Gute-Sachen Liste

Unsere Rezeptsammlung – [auf GitHub Pages](https://tiliavir.github.io/rezepte/).
Mit Suche, Portionsrechner und Einkaufsliste.

## Lokal starten

Voraussetzungen: [Hugo extended](https://gohugo.io/installation/) 0.169+, Node.js 22.12+, Java mit gesetztem `JAVA_HOME` (für die HTML-Validierung).

```bash
npm ci
npm start          # hugo server, ohne Suchindex
npm run lint       # Biome + TypeScript
npm run build      # Hugo → CSP-Hashes → Suchindex → HTML-Validierung
```

## Veröffentlichen

In einem Pull Request die Version setzen (`npm version --no-git-tag-version JJJJ.M.T`) und in
[CHANGELOG.md](CHANGELOG.md) einen Abschnitt `## [JJJJ.M.T] - JJJJ-MM-TT` ergänzen, dann mergen.
Der Release-Workflow sieht die neue Version, baut und prüft alles, veröffentlicht auf GitHub Pages
und legt Tag `vJJJJ.M.T` samt GitHub-Release an. Keine Tags von Hand pushen.

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
`assets/ts/` (TypeScript, gebündelt von Hugo). Schrift (Instrument Serif, OFL) liegt unter `static/fonts/`;
die Seite lädt nichts von fremden Servern.
