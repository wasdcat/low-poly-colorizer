# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-09-12

### Changed
- **Manifest tags** reduced to `Material` and `Import-Export`, following review
  feedback from the Blender Extensions Platform.
- Clarified in `addon/export/registry.py` that further export template sets are
  added in the source repository and shipped as a new add-on version -- the
  installed add-on directory is owned by Blender and is never written to.

## [1.0.0] - 2026-09-11

### Added
- **Interactive Palette Picker**: GPU overlay in the Blender 3D Viewport with zoom and pan; clicking a cell paints the selection immediately.
- **Single-Material Architecture**: All painted faces share one material. Each face references its palette cell and PBR preset via two UV channels – one surface per mesh instead of one material per color.
- **PBR Preset Management**: Named presets for roughness, metallic, emission, and clearcoat with reference-count protection and JSON import/export.
- **Painting Tools**: Assign, Sample, Select/Deselect by color and preset, and Fix UV Maps.
- **Geometry Nodes Integration**: `LPC Set Material` node group to set palette cell and preset procedurally in Geometry Nodes modifiers.
- **Engine Export**: Template-based export for Godot 4.x (shaders, materials, palette and preset textures, GDScript look resource); the Export button turns red when the export is out of date. Further engines can be added as template sets.
- **User Documentation**: User manuals in English and German (`manual/`).

