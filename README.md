*In contrast to my other repositories this one is in German, since the recipes are German.*

[![Build State](https://github.com/Tiliavir/rezepte/workflows/Build%20on%20Push/badge.svg)](https://github.com/Tiliavir/rezepte/actions?query=workflow%3A%22Build+on+Push%22)
&nbsp;
[![Publish State](https://github.com/Tiliavir/rezepte/workflows/Publish%20to%20GH%20Pages%20on%20Tag/badge.svg)](https://github.com/Tiliavir/rezepte/actions?query=workflow%3A%22Publish+to+GH+Pages+on+Tag%22)

# Rezepte
Sammlung an Rezepten. Das Resultat ist [auf GitHub Pages](https://tiliavir.github.io/rezepte/).

# Rezepte beisteuern
## Allgemein
Pull Requests sind immer herzlich willkommen. Im Gegensatz zu meinen anderen Repositories ist der Inhalt dieses Repositories auf deutsch. Folglich sollen auch alle Rezepte deutsch erfasst werden.

## Best Practices
### Bilder hinzufügen
Um Bildgröße zu verringern:
```bash
$ mogrify -resize 2000x2000 **/*.jpg
```

### Rezept hinzufügen
```bash
$ hugo new --kind recipe-bundle recipes/rezeptname
```

### Update GoChowDown
```bash
$ cd themes/gochowdown
$ git submodule update --remote
```
