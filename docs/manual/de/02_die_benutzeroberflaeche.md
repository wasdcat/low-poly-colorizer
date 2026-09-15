# Die Benutzeroberfläche

Die gesamte Bedienung von Low Poly Colorizer findet in einem kompakten Bedienfeld in der 3D-Viewport-Seitenleiste (**N-Panel ▸ LPC**) statt.

---

## Das N-Panel im Überblick

![Das Low Poly Colorizer N-Panel mit Legende](images/n_panel_annotated.png)

| Nr. | Bereich | Beschreibung |
|:---:|:---|:---|
| **①** | **Farbauswahl & Picker** | Zeigt die Farbe und die Koordinaten $(X, Y)$ der aktiven Palettenzelle. Ein Klick auf den **Paletten-Button** (Farbwähler) öffnet den interaktiven Modal-Picker im Viewport. Die Koordinaten können auch direkt numerisch editiert werden – das bemalt die aktuelle Auswahl sofort, genau wie ein Klick im Picker. |
| **②** | **Selektions-Status** | Informiert dynamisch über die Zielauswahl (*„14 faces in 1 object selected“* bzw. *„1 object selected“*). Warnt mit einem Warnhinweis, falls kein Preset ausgewählt ist. |
| **③** | **Preset-Liste & Aktionen** | Listet alle Material-Presets. Die Zahl rechts ist der **Refcount** (wie viele Flächen dieses Preset nutzen). Enthält Buttons für neues Preset (`+`), Löschen (`-`) und das Menü für erweiterte Aktionen (`▾`). |
| **④** | **PBR-Eigenschaften** | Steuert die physikalischen Materialwerte (*Roughness*, *Metallic*, *Emission*, *Clearcoat*) des **aktuell aktiven Presets**. Änderungen wirken sofort auf alle Flächen, die dieses Preset nutzen. |
| **⑤** | **Werkzeuge (Tools)** | **Assign**: Weist den aktuellen Pinsel (Farbe + Preset) der Auswahl zu – im Edit Mode den selektierten Flächen, im Object Mode ganzen Objekten.<br>**Sample**: *(Nur Edit Mode)* Übernimmt Farbe und Preset der selektierten Flächen ins Panel. Alle selektierten Flächen müssen dieselbe Farbe und dasselbe Preset haben.<br>**Select / Deselect**: *(Nur Edit Mode)* Fügt alle Flächen mit aktueller Farbe und aktuellem Preset zur Auswahl hinzu bzw. entfernt sie daraus. |
| **⑥** | **Export & Einstellungen** | Auswahl des templatebasierten Ziel-Formats (Standard: *Godot Materials*), **Export-Button** mit automatischer Schmutzerkennung (färbt sich rot, sobald der letzte Export veraltet ist) und Aufruf des Dialogs **Settings…**. |

---

## Wichtige Schutz- und Feedback-Mechanismen

* **Refcount-Schutz**: Ein Preset kann nicht gelöscht werden, solange sein Zähler größer als 0 ist. Das verhindert versehentlich zerstörte Mesh-Referenzen.
* **Visuelle Schmutzerkennung**: Sobald Sie Presets, Paletten-Einstellungen oder globale Werte ändern, färbt sich der Export-Button leuchtend **rot**. Nach erfolgreichem Export wird er wieder neutral. Das Bemalen von Flächen zählt nicht dazu: Die Flächendaten gelangen mit dem Modell (`.blend`/glTF) in die Engine, nicht über den Export.
* **Farb- & Preset-Gleichheit**: *Select* und *Deselect* arbeiten strikt mit logischem UND: Es werden nur jene Flächen gefiltert, die **sowohl dieselbe Palettenzelle als auch dasselbe Preset** besitzen.

---

## Schnelltasten & Workflow-Shortcuts

| Taste | Kontext | Funktion |
|:---|:---|:---|
| `N` | 3D-Viewport | Seitenleiste mit LPC-Panel ein- oder ausblenden |
| `Tab` | 3D-Viewport | Umschalten zwischen Object Mode (ganzes Objekt bemalen) und Edit Mode |
| `1` / `2` / `3` | Edit Mode | Vertex- / Edge- / Face-Selektionsmodus wählen |
| `L` | Edit Mode (Cursor über Face) | Zusammenhängende Insel (Linked Geometry) selektieren |
| `A` / `Alt + A` | 3D-Viewport | Alles auswählen bzw. gesamte Auswahl aufheben |
