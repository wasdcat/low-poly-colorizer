# Engine-Export und Integration

Low Poly Colorizer nutzt ein generisches, templatebasiertes Export-System (`.tpl`), das flexibel auf weitere Engines erweiterbar ist. Als mitgeliefertes Standard-Target dient **Godot 4** (*Godot Materials*).

## Der 1-Klick Export nach Godot

LPC exportiert **keine Meshes** (Modelle importieren Sie als `.blend` oder glTF mit ihren `lpc_uv0`/`lpc_uv1`-Maps). Der **Export-Button** öffnet einen Ordner-Dialog und schreibt vorbereitete Materialien, Shader und Hilfsklassen in den gewählten Ordner:

* **Texturen**: `lpc_palette.png` (Albedo/Farben) und `lpc_preset_lut.png` (PBR-Lookup-Tabelle), jeweils mit passender `.import`-Datei, sodass Godot sie ohne manuelle Einstellungen korrekt importiert.
* **Shader & Materialien**: Vorkonfigurierte ShaderMaterials (`.tres`), Shader (`.gdshader`) und Shared-Code (`.gdshaderinc`) – in zwei Varianten, `lpc_multicolor` und `lpc_singlecolor`.
* **Hilfsklassen**: GDScript-Klasse `lpc_palette_color_resource.gd` für eine reine Palettenfarbe (nur Palettenzelle, ohne Preset und Emission) – etwa für Decals, Beschriftungen, UI oder Lichter. Davon abgeleitet `lpc_singlecolor_resource.gd` für wiederverwendbare, benannte Looks (Palettenzelle, Preset, Emission) mit generiertem `Preset`-Enum. Beide liefern die Farbe ihrer Zelle per `get_color()` und zeigen sie im Inspektor im schreibgeschützten Feld `color` an (wird nicht gespeichert, folgt immer der Zelle).
* **Feste UIDs**: Jede exportierte Datei trägt eine stabile UID (`.uid`-/`.import`-Datei bzw. `.tres`-Kopf), die nur vom Dateinamen abhängt. Verweise per UID bleiben so über erneute Exporte hinweg gültig.
* **Hinweise**: `README.md` mit Erläuterungen zu Texturen, UIDs und Hilfsklassen.
* **Dirty-Flag-Erkennung**: Der Button leuchtet rot, sobald der letzte Export veraltet ist, und neutral im synchronen Zustand.

## Die Dateien in Godot verwenden

1. **Export in den Godot-Projektordner**: Wählen Sie einen Ordner innerhalb Ihres Godot-Projekts. Die mitexportierten `.import`-Dateien setzen die nötigen Import-Einstellungen der beiden Datentexturen automatisch (verlustfrei, ohne VRAM-Kompression und Mipmaps, *Fix Alpha Border* aus). Ändern Sie diese Einstellungen nicht – jeder Export stellt sie wieder her.
2. **Bemalte Meshes**: Weisen Sie dem importierten Mesh `lpc_multicolor.tres` als Material-Override zu. Es liest Farbe und Preset pro Fläche aus UV/UV2.
3. **Andere Meshes** (nicht in LPC bemalt): Verwenden Sie `lpc_singlecolor.tres`. Palettenzelle, Preset und Emission werden pro `MeshInstance3D` als Instance-Shader-Parameter gesetzt – viele Objekte teilen sich so ein Material und sehen trotzdem unterschiedlich aus.
4. **Nur die Farbe**: Wo kein LPC-Shader läuft (Decal, `Label3D`, UI, Licht), typisieren Sie Exporte als `LpcPaletteColorResource` und lesen die Farbe mit `get_color()`. Ein solches Feld akzeptiert auch jeden `LpcSinglecolorResource`-Look. Anders als ein fester `Color`-Wert folgt die Farbe Palettenänderungen beim nächsten Export.
   Im Inspektor ist die Palettenspalte (`palette_cell_x`) ein Auswahlfeld mit den Spaltennamen (z. B. *Nature · Moss*); gespeichert wird die Nummer. Für eigenen Code enthält das Skript zusätzlich `PALETTE_GROUPS` und `PALETTE_COLUMN_NAMES`.
   > [!WARNING]
   > Hinzufügen, Entfernen oder Umsortieren von Palettenspalten verschiebt die Spaltennummern. LPC rechnet die bemalten Meshes um, gespeicherte `.tres`-Dateien behalten aber ihre Nummer und zeigen nach dem nächsten Export auf eine andere Spalte – prüfen Sie sie nach einem solchen Umbau (wie bei Preset-Positionen).
5. **Arbeitsablauf**: Änderungen an bemalten Flächen reisen mit dem Modell – Godot übernimmt sie beim Reimport der `.blend` bzw. glTF. Ein neuer LPC-Export ist nur nötig, wenn der Export-Button rot ist.

## Prozedurale Workflows mit Geometry Nodes

Für prozedurale Meshes erzeugen Sie über das Preset-Zusatzmenü (**▾**) mit **Create Geometry Node Group** die Node-Gruppe `lpc_set_material`:

1. LPC erstellt die Node-Gruppe und bindet sie als Geometry-Nodes-Modifier an das aktive Objekt.
2. Im Node-Editor steuern Sie Palettenzelle $(X, Y)$ sowie das Preset prozedural per Eingangs-Socket. Das Material `lpc_multicolor` übernimmt das Shading automatisch.


![Die Node-Gruppe lpc_set_material im Geometry-Nodes-Editor](../common/images/geo_nodes_lpc_set_material.png)

## Wartung: UV-Maps reparieren (*Fix UV Maps*)

Low Poly Colorizer nutzt zwei definierte UV-Kanäle: `lpc_uv0` (Paletten-Farbkoordinaten) und `lpc_uv1` (Preset-LUT-Koordinaten).

Werden Meshes zusammengefügt (`Ctrl + J`), durch Booleans zerschnitten oder importiert, können UV-Kanäle vertauscht sein oder fehlen. LPC blendet in diesem Fall am unteren Rand des N-Panels automatisch eine Warnbox ein:

> [!WARNING]
> **UV maps need fixing:** Ein Klick auf den Button **Fix UV Maps** (nur im Object Mode) legt fehlende LPC-UV-Maps neu an, verschiebt `lpc_uv0` / `lpc_uv1` auf die ersten beiden UV-Slots und sichert den sauberen Import in Godot. Musste `lpc_uv0` neu angelegt werden, sind die Palettenfarben der betroffenen Flächen verloren – LPC meldet das, und diese Flächen müssen neu bemalt werden.


## Troubleshooting-Checkliste

| Problem | Ursache | Lösung |
|:---|:---|:---|
| **Keine Farben im Viewport** | 3D-Viewport steht auf *Wireframe* oder *Solid* ohne Texture-Preview. | Schalten Sie mit `Z` in den Shading-Modus **Material Preview** oder **Rendered**. |
| **Flächen färben sich nicht** | Im Edit Mode ist keine Fläche markiert oder kein Preset aktiv. | Flächen mit `A` oder `L` selektieren und sicherstellen, dass in der Liste ein Preset markiert ist. |
| **Minus-Button (`-`) gesperrt** | Das ausgewählte Preset wird noch von Flächen verwendet (Refcount > 0). | Bemalen Sie diese Flächen mit einem anderen Preset. *Select* findet Flächen mit aktueller Farbe **und** aktuellem Preset – wählen Sie vorher die passende Farbe (z. B. per *Sample*). |
| **Exportierter Godot-Look weicht ab** | Texturen wurden nach Preset- oder Paletten-Änderungen nicht exportiert (roter Button). | Klicken Sie im N-Panel auf den roten **Export-Button**, um die Texturen zu aktualisieren. |
| **Farben falsch oder Presets wirkungslos in Godot** | Die `.import`-Dateien fehlen (z. B. beim manuellen Kopieren nicht mitgenommen) oder wurden verändert. | Erneut exportieren – der Export schreibt die `.import`-Dateien neu. |
| **Godot warnt nach dem Update vor ungültigen UIDs** | Das Projekt verweist noch auf die zufälligen UIDs eines Exports vor Version 1.2. | Einmalig: betroffene Szenen/Ressourcen öffnen und speichern oder die alten UIDs projektweit ersetzen. Danach bleiben die UIDs bei jedem Export gleich. |


