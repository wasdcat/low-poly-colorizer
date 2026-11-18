# Farbpalette und PBR-Presets

In Low Poly Colorizer werden Farbgebung (Albedo) und Oberflächenbeschaffenheit (PBR-Werte) getrennt gesteuert und erst beim Rendern bzw. Shading miteinander kombiniert.

---

## Der interaktive Modal Palette Picker

Klicken Sie im N-Panel auf den **Paletten-Button** (Farbwähler), öffnet sich die Farbpalette als hardwarebeschleunigtes GPU-Overlay direkt im 3D-Viewport.

![Der interaktive GPU-Palette-Picker](../common/images/palette_picker_annotated.png)

| Bereich | Beschreibung |
|:---:|:---|
| **Ⓐ** | **Gruppe**: Die Palette ist in Gruppen gegliedert (z. B. *Neutral*, *Nature*, *Accent*). Jede Gruppe trägt ihren Namen als Überschrift; zwischen den Gruppen liegt eine kleine Lücke. |
| **Ⓑ** | **Spalten**: Jede Spalte ist ein Farbton mit eigener Helligkeitsrampe. Eine Spalte kann sich über zwei Rasterspalten erstrecken – etwa eine lange Grauskala mit doppelt so vielen Stufen. |
| **Ⓒ** | **Zeilen**: Vertikale Abstufung von hell nach dunkel. Zeile 0, die hellste, ist die unterste Zeile. |
| **Ⓓ** | **Aktive Zelle & Selektionsrahmen**: Zweifarbiger Markierungsrahmen um die momentan gewählte Palettenzelle mit direkter Zuweisung per Klick. |

Unter dem Raster zeigt der Picker den Namen der Zelle unter dem Mauszeiger, z. B. *Nature · Moss 3*. Aufbau und Größe der Palette legen Sie unter *Settings…* fest (siehe unten).

### Steuerung im Picker-Overlay

* **Auswählen & Zuweisen**: Klicken Sie mit der **linken Maustaste** auf die gewünschte Zelle. Die Zelle wird gespeichert, der aktuellen Auswahl zugewiesen und das Overlay schließt sich.
* **Zoomen**: Drehen Sie das **Mausrad**, um stufenlos in die Palette hinein- oder herauszuzoomen (0.25× bis 4.0×).
* **Verschieben (Pan)**: Halten Sie die **mittlere Maustaste (MMB)** gedrückt und ziehen Sie die Maus, um das Palettenfenster im Viewport zu bewegen.
* **Abbrechen**: Mit **Rechtsklick**, **Escape** oder einem Linksklick außerhalb der Palette (oder in eine Lücke zwischen Gruppen) schließen Sie das Overlay, ohne die bisherige Farbauswahl zu verändern.

---

## PBR-Presets: Materialeigenschaften steuern

Jedes Preset bündelt vier standardisierte physikalische Materialparameter:

* **Roughness (0.0 – 1.0)**: Oberflächen-Rauheit. Niedrige Werte erzeugen spiegelnde Oberflächen, hohe Werte ein mattes Finish.
* **Metallic (0.0 – 1.0)**: Metallischer Anteil. 0.0 entspricht Dielektrika (Plastik, Holz, Stein), 1.0 echtem Metall.
* **Emission (0.0 – 1.0)**: Eigenleuchtkraft der Fläche, skaliert mit dem globalen *Emission Factor* (*Settings…*). Die Albedo-Farbe der Palettenzelle wird als Leuchtfarbe herangezogen.
* **Clearcoat (0.0 – 1.0)**: Klarlack-Schicht (z. B. für Autolacke, polierte Oberflächen oder nasse Optiken).

> [!IMPORTANT]
> **Live-Aktualisierung:** Die Preset-Regler modifizieren keine individuellen Meshes, sondern die zentrale Lookup-Tabelle. Ändern Sie beispielsweise die *Roughness* des Presets *Solid*, aktualisieren sich **augenblicklich alle Flächen, die *Solid* nutzen**.

### Preset-Zusatzfunktionen (Menü `▾`)

* **Duplicate**: Erstellt eine 1:1-Kopie des aktiven Presets, um rasch Variationen zu erzeugen.
* **Import / Export Palette / Presets**: Speichert Palette und Presets in einer JSON-Datei bzw. lädt sie wieder – ideal zur Wiederverwendung in anderen Projekten. Im Dateidialog wählen Sie per Haken, ob die Palette, die Presets oder beides geschrieben bzw. übernommen werden. Beim Import werden Presets mit bereits vorhandenem Namen aktualisiert, neue werden angehängt; eine Palette ersetzt die aktuelle vollständig (bemalte Flächen ziehen mit, siehe *Bemalte Flächen beim Umbau*).
* **Load Default Presets**: Ergänzt fehlende der vier mitgelieferten Werks-Presets (*Solid*, *Metallic*, *Clearcoat*, *Emission*) und setzt gleichnamige Presets auf die Werkswerte zurück.
* **Create Geometry Node Group**: Siehe Kapitel *Engine-Export und Integration*.

---

## Globale Einstellungen (*Settings…*)

Über den Button **Settings…** im N-Panel öffnen Sie das Konfigurationsfenster für die Palette und die projektweiten Shader-Parameter. Änderungen werden live angezeigt; *OK* übernimmt sie, *Cancel* nimmt sie zurück.

Der Dialog ist von oben nach unten gegliedert: erst die Werte der ganzen Palette, dann die Gruppen, dann die Spalten der gewählten Gruppe, zuletzt die Materialwerte.

![Die globalen LPC-Einstellungen](../common/images/settings_annotated.png)

| Bereich | Beschreibung |
|:---:|:---|
| **①** | **Palette**: Name der Palette (kommt aus der Vorlage bzw. LPC-Datei und erscheint auf dem exportierten Spickzettel), Menü **Templates** mit den mitgelieferten Vorlagen und die Werte der ganzen Palette – Zeilenzahl (*Rows*), Helligkeitsbereich (*Lightest* / *Darkest*), Farbverlauf zu den Enden (*Tint* / *Shade*) sowie Farbtemperatur (*Hue Shift* / *Warmth*, siehe *Artwork*). |
| **②** | **Groups**: Liste der Gruppen (hinzufügen, entfernen, verschieben) und die Werte der gewählten Gruppe: *Chroma* sowie optional ein eigener Helligkeitsbereich. |
| **③** | **Columns of …**: Liste der Spalten der gewählten Gruppe – je Spalte drei Farbfelder (erste, mittlere und letzte Farbe ihrer Rampe) und ihr Name – und die Werte der gewählten Spalte: *Hue*, *Span* und optional ein eigenes *Chroma*. |
| **④** | **Material (all presets)**: Werte des gemeinsamen Materials, die für alle Presets gelten – der globale Emissions-Skalierungsfaktor (*Emission Factor*) und die Rauheit der Klarlackschicht (*Clearcoat Roughness*). Sie gehören nicht zur Palette und ändern keine Farbe. |

*Tint* und *Shade* legen fest, wie stark die Farbigkeit zu den hellsten (*Tint*) bzw. dunkelsten Zeilen (*Shade*) hin abnimmt. Niedrige Werte halten Lichter und Schatten farbig – gut für einen Toon-Look.

---

## Die Palette aufbauen: Gruppen und Spalten

Die Palette besteht aus **Gruppen**, und jede Gruppe aus **Spalten**. Die Reihenfolge im Picker folgt genau dieser Gliederung: erst die Gruppen, darin ihre Spalten.

* **Gruppen** ordnen die Palette nach Rolle. Bewährt hat sich eine Aufteilung in *Neutral* (Grau und fast neutrale Töne), *Nature* (gedämpfte Naturtöne für Gelände und Umgebung) und *Accent* (kräftige Farben für alles Spielrelevante). Das *Chroma* einer Gruppe – die Farbigkeit in OKLCH, 0 = Grau – gilt für alle ihre Spalten ohne eigenen Wert. Optional erhält eine Gruppe einen eigenen Helligkeitsbereich, etwa damit Grau und Stahl dunkler werden (Gummi, dunkles Metall) oder Schnee nie dunkel wird, ohne die übrigen Farben zu verändern.
* **Spalten** sind die eigentlichen Farbtöne. *Hue* ist der Farbton in Grad (OKLCH), *Chroma* optional die eigene Farbigkeit. Mit *Span 2* erstreckt sich eine Spalte über zwei Rasterspalten: Ihre Helligkeitsrampe läuft dann über doppelt so viele Stufen, links die helle, rechts die dunkle Hälfte.
* **Zeilen** gelten für die ganze Palette. *Lightest* und *Darkest* legen fest, wie hell die erste und wie dunkel die letzte Zeile ist (OKLab-Helligkeit, Standard 0.90 und 0.33); dazwischen sind die Stufen in wahrgenommener Helligkeit gleichmäßig verteilt. Die Palette liefert die Grundfarbe (Albedo) der Flächen; wie hell sie im Bild wirken, bestimmt das Licht. *Darkest* unter etwa 0.3 ergibt sehr dunkle Albedo-Werte, die kaum eine reale Oberfläche hat – dunkle Schatten entstehen durch die Beleuchtung.

Alle Farben entstehen im wahrnehmungsgetreuen Farbraum **OKLCH**: Gleiche Helligkeitswerte wirken über alle Farbtöne gleich hell. Gelbtöne behalten ihren sonnigen Charakter, Blautöne bleiben klar und Schattenstufen saufen nicht unkontrolliert ab.

### Vorlagen

Über **Templates** ersetzen Sie die Palette durch eine mitgelieferte Vorlage:

* **Stylized 3D** (Standard für neue Dateien): 21 Spalten × 7 Zeilen in den Gruppen *Neutral*, *Nature* und *Accent* – ruhige Töne für die Umgebung, kräftige Akzente für Spielrelevantes.
* **Toon Outdoor**: 26 Spalten × 5 Zeilen mit Naturfarben für Toon- und Low-Poly-Außenszenen, in den Gruppen *Ground* (Erde, Lehm, Weg, Sand, Fels, Stein), *Foliage* (Wiese, Gras, Laub, Moos, Kiefer, Salbei), *Autumn*, *Wood*, *Water & Sky* (mit eigenem, hellerem Helligkeitsbereich) und *Flowers*. Niedriges *Tint* / *Shade* hält Lichter und Schatten farbig.
* **Industrial Planet**: 25 Spalten × 7 Zeilen für eine stilisierte Sci-Fi-Industriewelt auf einem kargen Planeten, in den Gruppen *Neutral* (Grau, Stahl, Beton – bis zu dunklem Gummi), *Terrain* (Basalt, Fels, rostrotes Oxid, Staub, Ocker, Flechten), *Snow & Ice* (eigener heller Bereich: Schnee, Eis, Dunst), *Industry* (Warngelb, Sicherheitsorange, Signalrot, Kobalt, Petrol, Kupfer, Messing) und *Energy* (Leuchtfarben mit eigenem Bereich 0.91–0.45: Volt, Sodium, Plasma, Neon, Acid, Ion). Für Leuchtschriften und -markierungen die mittleren Zeilen von *Energy* mit einem Emission-Preset verwenden.
* **Classic Color Wheel**: Eine Grauskala plus 16 gleichmäßig verteilte Farbtöne × 9 Zeilen – ein klassischer Farbkreis, berechnet in OKLCH.

Alle Vorlagen bleiben in einem plausiblen Albedo-Bereich, ohne reines Schwarz oder Weiß.

Vorlagen sind JSON-Dateien im selben Format wie *Export Palette / Presets* – eine exportierte Palette lässt sich also jederzeit in ein anderes Projekt übernehmen.

### Bemalte Flächen beim Umbau

Bemalte Flächen speichern ihre Palettenzelle. Damit sie nach einem Umbau der Palette ihre Farbe behalten, rechnet LPC sie beim Klick auf **OK** um:

* **Automatisch**: Spalten hinzufügen, verschieben (auch zwischen Gruppen), Gruppen umsortieren und eine Spalte auf *Span 2* verbreitern sind verlustfrei. Jede Fläche bleibt auf ihrer Spalte und Stufe; LPC erkennt Spalten an einer festen, unsichtbaren Kennung, nicht an ihrer Position.
* **Mit Rückfrage**: Wird eine benutzte Spalte gelöscht, die Zeilenzahl geändert oder eine Spalte verschmälert, öffnet sich der Dialog **Remap Painted Faces**. Er listet jede betroffene alte Farbe mit der Zahl ihrer Flächen und schlägt die nächstliegende neue Farbe vor – in derselben Spalte, wenn es sie noch gibt. Die Vorschläge können Sie über X/Y korrigieren. *Cancel* stellt die vorherige Palette wieder her.

Farbänderungen (Farbton, Chroma, Helligkeit, Tint/Shade, Artwork) verschieben keine Zellen; die Flächen nehmen einfach die neue Farbe ihrer Zelle an.

---

## Artwork: Farblehre und Shading-Harmonisierung

Professionelle 3D-Grafik und Malerei arbeiten selten mit reinen Helligkeitsabstufungen, sondern mit **Farbtemperatur-Kontrasten** (warmes Sonnenlicht erzeugt kühle Schatten). Dafür gibt es in der Box **Palette** des Settings-Dialogs zwei Regler:

* **Hue Shift (-1.0 bis +1.0)**: Simuliert atmosphärisches Shading.
  * *Positive Werte (0.3 bis 0.5)*: Highlights driften zur warmen Farbachse (Gelb/Gold), Schatten wandern zur kühlen Achse (Blau/Violett) – ideal für sonnige Außenszenen.
  * *Negative Werte (-0.3 bis -0.5)*: Kühle Lichter und wärmere Schatten – ideal für Nacht- und Mondscheinszenen.
  * *0.0*: Neutrale Farbtöne ohne Drift.
* **Warmth (-1.0 bis +1.0)**: Globaler Farbtemperatur-Bias. Verschiebt alle Farbtöne sowie das Grau subtil in Richtung Bernstein/Gold (+1.0) oder kühles Himmelblau (-1.0).

### Empfohlene Einstellungen (Rezepte)

* **Stilisiertes 3D (Outdoor / Sonne)**: `Hue Shift: 0.5`, `Warmth: 0.2` – die Werte der Vorlage *Stylized 3D*.
* **Toon-Außenszene**: `Hue Shift: 0.6`, `Warmth: 0.15`, dazu `Tint: 0.45`, `Shade: 0.55` – die Werte der Vorlage *Toon Outdoor*.
* **Karge Sci-Fi-Industriewelt**: `Hue Shift: 0.35`, `Warmth: 0.05` – die Werte der Vorlage *Industrial Planet*.
* **Nacht / Sci-Fi / Mondschein**: `Hue Shift: -0.35`, `Warmth: -0.25`.
* **Neutral**: `Hue Shift: 0.0`, `Warmth: 0.0`.

Die Grundstimmung eines Levels gehört dagegen ins Licht und Postprocessing der Engine – die Palette bleibt dieselbe.
