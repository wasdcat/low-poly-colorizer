# Foreword

![Low Poly Colorizer](images/lpc_logo.png)

**Low Poly Colorizer (LPC)** is a Blender extension designed for fast, intuitive, and resource-efficient color and material styling of 3D models in low-poly aesthetics. Developed for game production at **WASDCAT Games**, it bridges the gap between rapid 3D prototyping in Blender and optimal draw-call performance in modern game engines such as **Godot 4**.

## The LPC Principle: References Instead of Material Chaos

Traditional low-poly workflows often struggle with two extremes: either the number of material slots explodes through dozens of individual materials, or static albedo texture atlases prohibit flexible physical properties (PBR).

Low Poly Colorizer solves this through a consistent **reference architecture**:

* **Color Reference (Albedo)**: Each face stores discrete coordinates (X, Y) referencing a dynamically generated palette texture (`lpc_palette.png`).
* **Material Look (PBR Preset)**: Each face references a named preset (*Solid*, *Metallic*, *Emission*, *Clearcoat*), resolved via a compact lookup table (`lpc_preset_lut.png`).
* **A Single Material**: All painted faces share the `lpc_multicolor` material. In the game engine, the painted part of a mesh is **a single surface** – one draw call instead of one per color.
* **Live Propagation**: Adjusting palette saturation or preset roughness later updates **all painted surfaces across the entire project instantly**, without re-traversing meshes.

> [!NOTE] Publication Notice
> This user manual was typeset and published using the modern Markdown publishing tool [markpublish](https://github.com/fwdotcom/markpublish).
