# Color Palette and PBR Presets

In Low Poly Colorizer, color values (albedo) and surface characteristics (PBR parameters) are managed independently and combined during rendering and shading.

---

## The Interactive Modal Palette Picker

Clicking the **Palette button** (color picker) in the N-Panel opens the color palette as a hardware-accelerated GPU overlay directly within the 3D Viewport.

![The interactive GPU palette picker](../common/images/palette_picker_annotated.png)

| Area | Description |
|:---:|:---|
| **Ⓐ** | **Greyscale Column (Column 0)**: Neutral greys from pure black (top) to pure white (bottom) for monochrome surfaces or neutral shading. |
| **Ⓑ** | **Hue Spectrum (Columns 1–16)**: Full HSV color wheel from red through yellow, green, cyan, blue, to magenta laid out horizontally. |
| **Ⓒ** | **Brightness & Saturation Gradient (Rows 0–8)**: Vertical progression from deep shadow tones (top) through rich saturated colors to pale pastels (bottom). Row 0 is the bottom row. |
| **Ⓓ** | **Active Cell & Selection Frame**: Two-tone highlight frame indicating the currently selected cell $(X, Y)$ with instant assignment on click. |

The column and row numbers refer to the default grid (greyscale column + 16 hues × 9 rows); both can be changed under *Settings…*.

### Navigation within the Picker Overlay

* **Select & Assign**: Click with the **left mouse button (LMB)** on any cell. The coordinates are stored, assigned to the current selection, and the overlay closes.
* **Zoom**: Scroll the **mouse wheel** to zoom continuously into or out of the palette grid (0.25× to 4.0×).
* **Pan**: Hold the **middle mouse button (MMB)** and drag to reposition the palette window anywhere in the viewport.
* **Cancel**: Press **Right-Click**, **Escape**, or click outside the palette to close the overlay without changing the current color selection.

---

## PBR Presets: Managing Material Looks

Each preset combines four standardized physical material parameters:

* **Roughness (0.0 – 1.0)**: Surface micro-roughness. Lower values yield sharp mirror reflections; higher values produce a soft, diffuse matte look.
* **Metallic (0.0 – 1.0)**: Metallic proportion. 0.0 corresponds to dielectrics (plastic, wood, stone); 1.0 corresponds to true conductive metals.
* **Emission (0.0 – 1.0)**: Surface self-illumination strength, scaled by the global *Emission Factor* (*Settings…*). The cell's albedo color serves as the emission tint.
* **Clearcoat (0.0 – 1.0)**: Secondary protective clear lacquer layer (e.g. automotive paints, varnished surfaces, or wet finishes).

> [!IMPORTANT]
> **Live Update:** Preset sliders do not modify individual mesh vertices or face loops; they update the central lookup table. Adjusting the *Roughness* of the *Solid* preset updates **every face using *Solid* instantaneously**.

### Extended Preset Menu (`▾`)

* **Duplicate**: Creates a 1:1 duplicate of the active preset to quickly iterate on material variations.
* **Import / Export JSON**: Saves and loads preset definitions as portable JSON files—ideal for sharing material sets across projects. On import, presets with an existing name are updated and new ones are appended.
* **Load Default Presets**: Adds the four bundled factory presets (*Solid*, *Metallic*, *Clearcoat*, *Emission*) if missing and resets existing presets of the same name to the factory values.
* **Create Geometry Node Group**: See chapter *Engine Export and Integration*.

---

## Global Settings (*Settings…*)

Clicking **Settings…** in the N-Panel opens the configuration dialog for project-wide palette generation and shader parameters. Changes are previewed live; *Cancel* reverts them.

![Global LPC Settings](../common/images/settings_annotated.png)

| Area | Description |
|:---:|:---|
| **①** | **Grid**: Number of hue columns (*Columns*, excluding the greyscale column) and rows (*Rows*), plus a toggle for the monochrome greyscale column (*Add Greyscale Column*). |
| **②** | **Base Color**: Base saturation (*Saturation*) and base brightness (*Brightness*) for all hues in the color wheel. |
| **③** | **Tint / Shade**: Strength of the vertical gradation steps (highlighting via *Tint*, darkening via *Shade*). |
| **④** | **Artwork**: Color space (**Color Mode**: *HSV* or *OKLCH*), vertical temperature drift (**Hue Shift**), and global temperature bias (**Warmth**). |
| **⑤** | **Globals**: Project-wide parameters including the global emission multiplier (*Emission Factor*) and base clearcoat roughness (*Clearcoat Roughness*). |

---

## Artwork: Color Theory and Shading Harmony

Standard color palettes generated purely in HSV color space often produce jarring artifacts in 3D shading: yellow highlights blow out into blinding white, and dark shadows turn muddy or dirty grey. In stylized 3D art and traditional painting, lighting is rarely a pure value ramp—artists use **temperature contrast** (warm sunlight produces cool ambient shadows).

The **Artwork** section provides controls for pleasing, painterly palettes:

### Color Spaces: HSV vs. OKLCH

* **HSV (Standard / Legacy)**: Purely mathematical color space (`V = max(R, G, B)`). Ensures 100% backward compatibility with existing scenes and provides vibrant 90s-style arcade colors.
* **OKLCH (Perceptually Uniform)**: Modeled after the human visual cortex. Equal lightness (*L*) corresponds to equal perceived brightness across all hues. Yellows stay rich and luminous without blinding, blues remain vibrant, and shading transitions feel natural.

### Temperature Controls

* **Hue Shift (-1.0 to +1.0)**: Simulates atmospheric shading across the vertical ramp.
  * *Positive values (0.3 to 0.5)*: Highlights shift warm (sunlight / amber) while shadows drift cool (skylight / violet-blue)—the staple of stylized low-poly art.
  * *Negative values (-0.3 to -0.5)*: Cool highlights and warm shadows—ideal for moonlight or nocturnal scenes.
  * *0.0*: Neutral gradient without hue drift.
* **Warmth (-1.0 to +1.0)**: Global color temperature bias. Gently warms (amber) or cools (sky blue) the entire palette, including the greyscale column.

### Recommended Settings (Recipes)

* **Modern Stylized Low-Poly (Sunlight / Outdoor)**: `OKLCH`, `Hue Shift: 0.35`, `Warmth: 0.15`.
* **Nocturnal / Sci-Fi / Moonlight**: `OKLCH`, `Hue Shift: -0.35`, `Warmth: -0.25`.
* **Classic Retro Arcade**: `HSV`, `Hue Shift: 0.0`, `Warmth: 0.0`.

