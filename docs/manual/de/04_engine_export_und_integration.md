# Engine-Export und Integration

Low Poly Colorizer nutzt ein generisches, templatebasiertes Export-System (`.tpl`), das flexibel auf weitere Engines erweiterbar ist. Als mitgeliefertes Standard-Target dient **Godot 4** (*Godot Materials*).

## Der 1-Klick Export nach Godot

LPC exportiert **keine Meshes** (Modelle importieren Sie als `.blend` oder glTF mit ihren `lpc_uv0`/`lpc_uv1`-Maps). Der **Export-Button** öffnet einen Ordner-Dialog und schreibt vorbereitete Materialien, Shader und Hilfsklassen in den gewählten Ordner:

* **Texturen**: `lpc_palette.png` (Albedo/Farben) und `lpc_preset_lut.png` (PBR-Lookup-Tabelle).
* **Shader & Materialien**: Vorkonfigurierte ShaderMaterials (`.tres`), Shader (`.gdshader`) und Shared-Code (`.gdshaderinc`) – in zwei Varianten, `lpc_multicolor` und `lpc_singlecolor`.
* **Hilfsklassen**: GDScript-Klasse `lpc_singlecolor_resource.gd` für wiederverwendbare, benannte Looks (Palettenzelle, Preset, Emission) mit generiertem `Preset`-Enum.
* **Import-Hinweise**: `README.md` mit den Textur-Import-Einstellungen, die Godot benötigt.
* **Dirty-Flag-Erkennung**: Der Button leuchtet rot, sobald der letzte Export veraltet ist, und neutral im synchronen Zustand.

## Die Dateien in Godot verwenden

1. **Textur-Import-Einstellungen**: Beide PNGs sind Datentexturen, keine gewöhnlichen Farbtexturen. Wählen Sie jede im *FileSystem*-Dock, setzen Sie im *Import*-Tab folgende Werte und klicken Sie auf *Reimport*: *Detect 3D ▸ Compress To* = **Disabled**, *Compress ▸ Mode* = **Lossless**, *Mipmaps ▸ Generate* = **Off**. Für `lpc_preset_lut.png` zusätzlich *Process ▸ Fix Alpha Border* = **Off**. Die Einstellungen bleiben bei späteren Exporten erhalten.
2. **Bemalte Meshes**: Weisen Sie dem importierten Mesh `lpc_multicolor.tres` als Material-Override zu. Es liest Farbe und Preset pro Fläche aus UV/UV2.
3. **Andere Meshes** (nicht in LPC bemalt): Verwenden Sie `lpc_singlecolor.tres`. Palettenzelle, Preset und Emission werden pro `MeshInstance3D` als Instance-Shader-Parameter gesetzt – viele Objekte teilen sich so ein Material und sehen trotzdem unterschiedlich aus.
4. **Arbeitsablauf**: Änderungen an bemalten Flächen reisen mit dem Modell – Godot übernimmt sie beim Reimport der `.blend` bzw. glTF. Ein neuer LPC-Export ist nur nötig, wenn der Export-Button rot ist.

## Prozedurale Workflows mit Geometry Nodes

Für prozedurale Meshes erzeugen Sie über das Preset-Zusatzmenü (**▾**) mit **Create Geometry Node Group** die Node-Gruppe `lpc_set_material`:

1. LPC erstellt die Node-Gruppe und bindet sie als Geometry-Nodes-Modifier an das aktive Objekt.
2. Im Node-Editor steuern Sie Palettenzelle $(X, Y)$ sowie das Preset prozedural per Eingangs-Socket. Das Material `lpc_multicolor` übernimmt das Shading automatisch.


![Die Node-Gruppe lpc_set_material im Geometry-Nodes-Editor](images/geo_nodes_lpc_set_material.png)

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
| **Farben falsch oder Presets wirkungslos in Godot** | Godot hat die Datentexturen beim Import komprimiert. | Textur-Import-Einstellungen setzen (siehe *Die Dateien in Godot verwenden*) und *Reimport* klicken. |


