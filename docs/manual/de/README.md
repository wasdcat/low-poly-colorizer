# Low Poly Colorizer — Benutzerhandbuch

Dieses Verzeichnis enthält das offizielle, deutschsprachige **Benutzerhandbuch für Low Poly Colorizer (LPC)**. Es richtet sich an 3D-Artists, Game-Entwickler und Technical Artists, die 3D-Modelle effizient in Blender gestalten und vorbereitete Materialien sowie Shader für Game-Engines wie Godot 4 bereitstellen möchten.

---

## Inhaltsverzeichnis

- [Vorwort](00_vorwort.md)
1. [Installation und Schnelleinstieg](01_installation_und_schnelleinstieg.md)
2. [Die Benutzeroberfläche](02_die_benutzeroberflaeche.md)
3. [Farbpalette und PBR-Presets](03_farbpalette_und_presets.md)
4. [Engine-Export und Integration](04_engine_export_und_integration.md)

---

## Screenshots & Assets automatisieren

Die im Handbuch verwendeten Screenshots können vollständig autonom direkt aus Blender heraus erzeugt, zugeschnitten und annotiert werden:

```powershell
python scripts/capture_screenshots.py docs/manual/de/images docs/manual/en/images
```

---

## PDF-Generierung mit markpublish

Dieses Handbuch wird mit [markpublish](https://github.com/fwdotcom/markpublish) aus den Markdown-Dateien kompiliert:

```powershell
# Einzeln kompilieren:
markpublish build docs/manual/de/markpublish.yaml -o manual/low_poly_colorizer_de.pdf

# Oder vollständigen Test- und Release-Build ausführen:
python scripts/build_dist.py
```

Das fertige PDF-Dokument wird direkt unter `manual/low_poly_colorizer_de.pdf` abgelegt.
