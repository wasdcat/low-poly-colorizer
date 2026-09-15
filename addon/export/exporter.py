# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Generic, engine-agnostic template export.

A target is a folder of `.tpl` files (see registry.py). Export renders every
`.tpl` in the chosen set into the chosen output directory: `{{key}}`
placeholders are substituted from the scene's material parameters
(`build_context`) in BOTH the body and the filename (so a template named
`{{prefix}}common.gdshaderinc.tpl` is written under the active namespace
prefix), the `.tpl` marker is dropped from the written filename, and literal
braces in the body are left intact (so shader code survives).

Alongside the rendered templates, `write_textures` writes the palette + the
preset LUT as PNGs -- binary data the `.tpl` text-substitution mechanism
can't carry, so it's a separate step in `LPC_OT_export.execute`, not another
template.

Nothing here is Godot-specific -- the only thing that knows about a particular
engine is its template folder + its registry entry. The render context is the
engine-agnostic material state; a template uses whatever subset it needs and
cross-file references (e.g. a material pointing at its shader file) use the
same `{{prefix}}` placeholder as the filenames, so they stay in sync whatever
the active namespace prefix is.
"""

import os
import re
import unicodedata

try:
    import bpy
except ModuleNotFoundError:  # plain-python tests without Blender
    bpy = None

try:
    from . import registry
    from .. import constants
    from ..model import palette as model_palette
    from ..model import presets as model_presets
    from ..picker import interface as picker_interface
    from ..ui import preview_material
except ImportError:  # plain-python tests put the addon dir on sys.path
    from export import registry
    import constants
    from model import palette as model_palette
    from model import presets as model_presets
    from picker import interface as picker_interface

# Filenames the palette + preset LUT textures are written under in the export
# folder -- the .tres templates reference them via the {{palette_image_filename}}
# / {{preset_lut_image_filename}} placeholders (build_context), so the names
# live here in one place and stay in sync between the written PNGs and the
# ExtResource paths pointing at them. Prefixed via constants.PREFIX like every
# other exported filename.
PALETTE_IMAGE_FILENAME = constants.PREFIX + "palette.png"
PRESET_LUT_IMAGE_FILENAME = constants.PREFIX + "preset_lut.png"

def _fmt(value):
    return repr(round(float(value), 6))


def _preset_legend(scene):
    """A `lpc_preset_position` value <-> preset name comment block -- list
    position is a plain int with no name attached once it's on a mesh, so
    this is the one place a human (hand-setting the singlecolor variant's
    instance uniforms in Godot) can look up which number means what.
    Re-exporting after any preset add/delete/rename regenerates it; it goes
    stale otherwise, hence the "at the time of the last export" caveat in the
    template using it."""
    presets = list(scene.lpc_presets)
    if not presets:
        return "//   (no presets)"
    return "\n".join(f"//   {i} = {p.name}" for i, p in enumerate(presets))


def _pascal(prefix):
    """`constants.PREFIX` as a PascalCase identifier fragment ("lpc_" -> "Lpc"),
    for the exported GDScript `class_name`. Derived rather than added as a
    second constant so the namespace stays the single knob constants.PREFIX
    promises to be -- a `class_name` is registered project-wide in Godot, so a
    clash between two LPC exports living in one project is resolved exactly
    like every other name clash here: by changing PREFIX.

    `str.capitalize` is deliberately not used -- it lowercases the rest of each
    part ("myGame_" -> "Mygame" instead of "MyGame")."""
    return "".join(p[:1].upper() + p[1:] for p in prefix.split("_") if p)


def _preset_identifiers(scene):
    """The preset names as GDScript enum member identifiers, index-aligned with
    `scene.lpc_presets` so a member's VALUE is the same list position the
    shader's `lpc_preset_position` takes.

    Preset names are free text and enum members are identifiers, so the mapping
    is lossy -- but it must be total, because generated code that does not parse
    breaks the whole export. Non-ASCII is folded ("Grün" -> GRUN), any run of
    other characters collapses to one underscore, and a name that folds to
    nothing or to a leading digit gets a PRESET prefix. Uppercasing is also what
    keeps a name from ever colliding with a GDScript keyword (those are all
    lowercase). Names that collide only after folding ("Red Light" /
    "Red-Light") get a numeric suffix -- two members of the same name would be a
    parse error.

    An empty preset list yields a single PRESET_0 member, mirroring
    `build_context`'s `max(len(...), 1)` preset_count: the shader always has one
    (garbage) LUT texel to address, so the enum must be able to name it."""
    idents = []
    used = set()
    for preset in scene.lpc_presets:
        folded = unicodedata.normalize("NFKD", preset.name.replace("ß", "ss"))
        ascii_only = folded.encode("ascii", "ignore").decode("ascii")
        ident = re.sub(r"[^A-Za-z0-9]+", "_", ascii_only).strip("_").upper()
        if not ident:
            ident = "PRESET"
        elif ident[0].isdigit():
            ident = "PRESET_" + ident
        base, n = ident, 1
        while ident in used:
            n += 1
            ident = f"{base}_{n}"
        used.add(ident)
        idents.append(ident)
    return idents or ["PRESET_0"]


def _preset_enum(identifiers):
    """The `enum Preset` member lines, tab-indented (GDScript style); the
    template supplies the braces around them, like `_preset_legend`'s caller
    supplies the surrounding comment."""
    return "\n".join(f"\t{ident} = {i}," for i, ident in enumerate(identifiers))


def build_context(scene):
    """The substitution values available to every template -- engine-agnostic
    material parameters from the scene. Unknown placeholders in a template are
    left untouched, unused keys here are simply ignored."""
    g = scene.lpc_globals
    params = picker_interface.params_from_scene(scene)
    cols, rows = model_palette.cell_count(params)
    preset_count = max(len(scene.lpc_presets), 1)
    preset_identifiers = _preset_identifiers(scene)
    return {
        # Namespace prefix the .tres templates prepend to their own
        # resource_name ("{{prefix}}multicolor" / "{{prefix}}singlecolor",
        # matching the exported .tres filenames) -- the variant IS the whole
        # distinguishing part after the prefix, so there is no shared
        # material base name to carry.
        "prefix": constants.PREFIX,
        # The same namespace prefix as an identifier fragment, for the one
        # exported file that needs a GDScript `class_name`
        # ({{prefix}}singlecolor_resource.gd). Same rule as the filenames: the
        # literal part after it lives in the template.
        "prefix_pascal": _pascal(constants.PREFIX),
        "emission_factor": _fmt(g.emission_factor),
        "clearcoat_roughness": _fmt(g.clearcoat_roughness),
        "preset_count": str(preset_count),
        # *_max are the highest VALID index (count - 1) -- only useful as
        # `hint_range` upper bounds on the singlecolor shader's instance
        # uniforms (lpc_preset_position, lpc_palette_cell_x/y), clamping
        # hand-typed Inspector values to what the exported LUT/palette
        # textures actually contain. Godot's hint_range only accepts
        # int/float uniforms, not vectors -- hence cell_x/y as two
        # separate placeholders rather than one vec2.
        "preset_count_max": str(preset_count - 1),
        "palette_cols": str(cols),
        "palette_rows": str(rows),
        "palette_cols_max": str(cols - 1),
        "palette_rows_max": str(rows - 1),
        # The palette PARAMETERS -- the `model/palette.color_at` inputs, so a
        # target can reproduce cell colors procedurally instead of sampling
        # the exported PNG (the Godot resource script does; the shaders do
        # not, they have the texture). Everything the palette is derived from
        # travels here, whether or not a template uses all of it yet.
        #
        # `params["cols"]` -- the number of HUE steps around the wheel -- is
        # deliberately NOT among them: palette_cols above is cell_count's
        # total, i.e. that same number plus the optional greyscale column, so
        # a target needing the hue divisor subtracts the flag below and is
        # done. One exported value less to keep consistent with the rest.
        "palette_has_greyscale": "true" if params["add_greyscale"] else "false",
        "palette_saturation": _fmt(params["saturation"]),
        "palette_brightness": _fmt(params["brightness"]),
        "palette_tint": _fmt(params["tint"]),
        "palette_shade": _fmt(params["shade"]),
        "palette_image_filename": PALETTE_IMAGE_FILENAME,
        "preset_lut_image_filename": PRESET_LUT_IMAGE_FILENAME,
        "preset_legend": _preset_legend(scene),
        # The same list-position <-> preset-name mapping as preset_legend, but
        # as real GDScript enum members instead of a comment block -- the
        # singlecolor variant's preset index is the one exported value a human
        # types by hand, and `Preset.EMISSION` beats looking the number up.
        # `_first` is only there so the resource's `preset` export can have a
        # typed default without assuming a member name.
        "preset_enum": _preset_enum(preset_identifiers),
        "preset_enum_first": preset_identifiers[0],
    }


def export_fingerprint(scene):
    """Deterministic snapshot of every value that ends up in the exported
    files -- `build_context` (covers preset names/count, globals, palette
    grid size) plus the preset LUT pixels (covers preset VALUES, which
    `build_context` only counts) plus the palette params (a stand-in for
    the palette pixels themselves -- `model_palette.build_pixels` is a pure
    function of them, so they carry the same information without hashing
    the whole pixel array)."""
    lut = tuple(round(v, 6) for v in model_presets.build_preset_lut_pixels(scene))
    palette_params = tuple(sorted(picker_interface.params_from_scene(scene).items()))
    return repr((build_context(scene), lut, palette_params))


def is_export_dirty(scene):
    """True if `scene`'s current export-relevant state no longer matches
    `scene.lpc_export_fingerprint` (set at the last successful export) --
    the Export button's red highlight. Computed live on every panel
    redraw, never toggled, so undo/redo/manual reverts are reflected
    automatically. Stored as a real Scene property (not plain Python
    state) so it persists across saves -- safe to do only because
    `LPC_OT_export` is itself undo-registered (see its bl_options), which
    gives the property write its own undo-snapshot boundary; without that,
    a later undo could jump past the export to a stale pre-export snapshot
    even though e.g. a preset's roughness on that same snapshot correctly
    reverts (the property and the data it describes would desync)."""
    try:
        return export_fingerprint(scene) != scene.lpc_export_fingerprint
    except AttributeError:
        return False  # lpc_* properties unexpectedly missing -- fail safe, not loud


def _mark_exported(scene):
    scene.lpc_export_fingerprint = export_fingerprint(scene)


def write_textures(scene, out_dir):
    """Write the palette + preset LUT images as PNGs into `out_dir`, via
    Blender's own `Image.save()` -- guarantees the exported pixels are
    byte-identical to whatever the Blender preview just sampled (no separate
    encoder to risk a rounding/gamma divergence). Returns the list of written
    filenames."""
    written = []
    for image, filename in (
        (preview_material.ensure_palette_image(scene), PALETTE_IMAGE_FILENAME),
        (preview_material.ensure_preset_lut_image(scene), PRESET_LUT_IMAGE_FILENAME),
    ):
        path = os.path.join(out_dir, filename)
        image.filepath_raw = path
        image.file_format = "PNG"
        image.save()
        written.append(filename)
    return written


def _render(text, mapping):
    return re.sub(
        r"\{\{(\w+)\}\}",
        lambda m: mapping.get(m.group(1), m.group(0)),
        text,
    )


def _strip_tpl(name):
    return name[:-4] if name.endswith(".tpl") else name


def render_set(set_id, out_dir, context):
    """Render every `.tpl` in the set's folder into `out_dir`. Returns the list
    of written filenames. Raises ValueError for an unknown set, OSError on IO."""
    tdir = registry.template_dir(set_id)
    if tdir is None or not os.path.isdir(tdir):
        raise ValueError(f"unknown export template set: {set_id!r}")
    written = []
    for entry in sorted(os.listdir(tdir)):
        if not entry.endswith(".tpl"):
            continue
        with open(os.path.join(tdir, entry), "r", encoding="utf-8") as f:
            text = f.read()
        # The template FILENAME carries the same {{prefix}} placeholder as its
        # body (e.g. "{{prefix}}common.gdshaderinc.tpl"), so the exported file
        # name honors constants.PREFIX exactly like the cross-file references
        # written inside it -- one substitution pass covers both.
        out_name = _render(_strip_tpl(entry), context)
        with open(os.path.join(out_dir, out_name), "w", encoding="utf-8") as f:
            f.write(_render(text, context))
        written.append(out_name)
    return written


def _uv_problem_count(scene):
    """Painted meshes whose param UVs are missing or out of the leading UV
    order -- a UV-transport target would mis-import them (see Fix UV Maps)."""
    seen = set()
    count = 0
    for obj in scene.objects:
        if obj.type == "MESH" and obj.data not in seen:
            seen.add(obj.data)
            if preview_material.mesh_needs_uv_fix(obj.data):
                count += 1
    return count


# EnumProperty items must outlive the registration call (Blender keeps no copy
# of the strings), so hold them at module level.
EXPORT_TARGET_ITEMS = registry.enum_items()


if bpy is not None:
    class LPC_OT_export(bpy.types.Operator):
        """Export the selected template set into a chosen folder: the shader(s), material(s), and the palette + preset LUT textures. Pick the target in the dropdown; the per-face references (palette cell + preset index) travel in the lpc UV maps, so import the .blend separately"""

        bl_idname = "lpc.export"
        bl_label = "Export"
        # UNDO (not just REGISTER): writes scene.lpc_export_fingerprint
        # (is_export_dirty), which needs its own undo-snapshot boundary so a
        # later undo can't jump past it to a stale pre-export value -- see
        # is_export_dirty's docstring.
        bl_options = {"REGISTER", "UNDO"}

        # Directory picker (every output filename is determined by the templates).
        directory: bpy.props.StringProperty(subtype="DIR_PATH")
        filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

        def invoke(self, context, event):
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}

        def execute(self, context):
            scene = context.scene
            set_id = scene.lpc_export_target
            entry = registry.get(set_id)
            if entry is None:
                self.report({"ERROR"}, "No export target selected")
                return {"CANCELLED"}
            out_dir = self.directory
            if not out_dir or not os.path.isdir(out_dir):
                self.report({"ERROR"}, "Choose an existing output folder")
                return {"CANCELLED"}

            try:
                written = render_set(set_id, out_dir, build_context(scene))
                written += write_textures(scene, out_dir)
            except (OSError, ValueError) as exc:
                self.report({"ERROR"}, f"Export failed: {exc}")
                return {"CANCELLED"}
            _mark_exported(scene)

            label = entry["label"]
            broken = _uv_problem_count(scene)
            if broken:
                self.report(
                    {"WARNING"},
                    f"Exported {label} ({len(written)} file(s)), but {broken} "
                    f"mesh(es) have the lpc UV maps missing or out of order -- run "
                    f"'Fix UV Maps' in Object Mode so the params import correctly",
                )
            else:
                self.report(
                    {"INFO"}, f"Exported {label} ({len(written)} file(s))"
                )
            return {"FINISHED"}

