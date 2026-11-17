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

The palette and the presets reach a target as images, as text, or both.
Images: `write_textures` writes the palette and/or the preset LUT as PNGs --
binary data the `.tpl` text-substitution mechanism can't carry, so it's a
separate step in `LPC_OT_export.execute`, not another template; which of the
two a set gets is its registry entry's call (`palette_texture` /
`preset_texture`). Text: `build_context` always carries both as ready-made
array bodies (`palette_colors_gdscript`, `preset_values_glsl`), so a template
can bake them into its source. The Godot set ships both textures and uses
the palette array for GDScript only (its resource script's color_at).

Every exported file can carry a STABLE ID (`stable_uid`): derived from its
output filename alone, so re-exporting -- into the same project or a fresh
one, from any machine -- always writes the same ID for the same file and
references by ID keep resolving. `render_set` puts one `uid_<name>`
placeholder per file of the set into the context; a sidecar template
(`<file>.import.tpl`, `<file>.uid.tpl`) shares the ID of the file it
describes, which is how a texture written by `write_textures` gets one too.

Nothing here is Godot-specific -- the only thing that knows about a particular
engine is its template folder + its registry entry. The render context is the
engine-agnostic material state; a template uses whatever subset it needs and
cross-file references (e.g. a material pointing at its shader file) use the
same `{{prefix}}` placeholder as the filenames, so they stay in sync whatever
the active namespace prefix is.
"""

import json
import hashlib
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
# other exported filename. A shipped texture's `.import` sidecar template is
# named after it ({{prefix}}palette.png.import.tpl), so a rename must touch
# both.
PALETTE_IMAGE_FILENAME = constants.PREFIX + "palette.png"
PRESET_LUT_IMAGE_FILENAME = constants.PREFIX + "preset_lut.png"

def _fmt(value):
    return repr(round(float(value), 6))


def _lit(value):
    """A float literal any C-like target parses (GDScript, GLSL, ...):
    fixed-point, never scientific notation (`repr` would turn 1e-7 into
    "1e-07"), at most 6 decimals, but always with a decimal point so it reads
    as a float, not an int ("1.0", not "1")."""
    text = f"{float(value):.6f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return "0.0" if text == "-0.0" else text


def _palette_rows(params):
    """`model_palette.color_at` for every cell, as one list of (r, g, b) per
    palette row, row 0 first -- the SAME (x, y) cell numbering the picker,
    the per-face UVs (`model/faces.palette_uv`) and the singlecolor instance
    uniforms use, so a target indexes it as `[y * cols + x]` with no flip.
    Alpha is dropped: the palette is always opaque.

    Values are the raw `color_at` output, with no sRGB<->linear conversion --
    the same numbers `build_pixels` writes into the "Non-Color" palette PNG
    the shaders sample, so both agree up to the PNG's 8-bit rounding."""
    cols, rows = model_palette.cell_count(params)
    return [
        [model_palette.color_at(x, y, params)[:3] for x in range(cols)]
        for y in range(rows)
    ]


def _palette_colors_gdscript(params):
    """The palette as the body of a GDScript `PackedColorArray` literal, one
    palette row per line, so the generated file reads like the picker grid.
    Index `y * cols + x`, see `_palette_rows`."""
    return ",\n".join(
        "\t" + ", ".join(f"Color({_lit(r)}, {_lit(g)}, {_lit(b)})" for r, g, b in row)
        for row in _palette_rows(params)
    )


def _preset_values(scene):
    """(roughness, metallic, clearcoat, emission) per preset IN LIST ORDER --
    the same layout and order as `model_presets.build_preset_lut_pixels`, one
    entry per LUT texel, so the list position on a face indexes it directly.
    Read straight off the scene (not via that function) because it lives in
    presets.py's bpy-only layer, and this must stay testable without Blender.

    An empty preset list still yields one all-zero entry, mirroring the LUT's
    1x1 minimum and `build_context`'s `max(len(...), 1)` preset_count: a
    shader array cannot have zero elements."""
    values = [
        (p.roughness, p.metallic, p.clearcoat, p.emission)
        for p in scene.lpc_presets
    ]
    return values or [(0.0, 0.0, 0.0, 0.0)]


def _preset_values_glsl(scene):
    """The presets as the body of a GLSL-style `vec4` array initializer, one
    preset per line with its list position and name as a comment -- the
    shader-side twin of `_preset_legend`. The last entry has no comma: GLSL
    does not allow a trailing one."""
    names = [p.name for p in scene.lpc_presets] or ["(no presets)"]
    values = _preset_values(scene)
    lines = []
    for i, (value, name) in enumerate(zip(values, names)):
        comma = "," if i < len(values) - 1 else ""
        vec = ", ".join(_lit(v) for v in value)
        # Collapse whitespace: a newline in a preset name would end the
        # comment and turn the rest of the name into shader code.
        safe_name = " ".join(str(name).split())
        lines.append(f"\tvec4({vec}){comma} // {i} = {safe_name}")
    return "\n".join(lines)


def _gd_string(text):
    """A GDScript string literal for free text (JSON's escaping is valid
    GDScript: quotes, backslashes, control characters, non-ASCII kept)."""
    return json.dumps(str(text), ensure_ascii=False)


def _palette_groups_gdscript(params):
    """The palette groups as the body of a GDScript Array[Dictionary]
    literal, one per line: name, first grid column, grid column count."""
    lines = [
        f'\t{{"name": {_gd_string(name)}, "first": {first}, "count": {count}}},'
        for name, first, count in model_palette.group_ranges(params)
    ]
    return "\n".join(lines)


def _palette_column_names_gdscript(params):
    """"Group · Column" per grid column, as the body of a GDScript
    PackedStringArray literal, one per line."""
    return "\n".join(f"\t{_gd_string(label)},"
                     for label in model_palette.grid_column_labels(params))


def _palette_cell_x_enum(params):
    """The argument list of `@export_enum` for palette_cell_x: one
    "Group · Column:x" per grid column, x being the stored number. `,` and
    `:` separate entries / values in Godot's enum hint, so they become
    spaces inside labels."""
    entries = []
    for x, label in enumerate(model_palette.grid_column_labels(params)):
        clean = label.replace(",", " ").replace(":", " ")
        entries.append(_gd_string(f"{clean}:{x}"))
    return ",\n\t\t".join(entries)


def _shader_hint_enum(labels):
    """The argument list of a shader `hint_enum` (Godot 4.4+): one string
    per label, in order -- hint_enum numbers its entries 0, 1, ...
    `,` and `:` separate entries / values in Godot's enum hint and become
    spaces, as in _palette_cell_x_enum. Godot's shader tokenizer knows no
    escape sequences, so a `"` (which would end the string) becomes `'`
    and a backslash `/`."""
    entries = []
    for label in labels:
        clean = (" ".join(str(label).split())
                 .replace(",", " ").replace(":", " ")
                 .replace('"', "'").replace("\\", "/"))
        entries.append(f'"{clean}"')
    return ",\n    ".join(entries)


def _palette_cell_x_hint_enum(params):
    """`hint_enum` arguments for the singlecolor shader's instance uniform
    lpc_palette_cell_x: one "Group · Column" per grid column, in x order."""
    return _shader_hint_enum(model_palette.grid_column_labels(params))


def _preset_hint_enum(scene):
    """`hint_enum` arguments for the singlecolor shader's instance uniform
    lpc_preset_position: the preset names in list order, so entry i is list
    position i. An unnamed preset shows as "Preset <n>"; with no presets at
    all there is one placeholder entry (position 0, like preset_count)."""
    names = [p.name or f"Preset {i + 1}" for i, p in enumerate(scene.lpc_presets)]
    return _shader_hint_enum(names or ["(no presets)"])


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
        # uniforms (now only lpc_palette_cell_y; cell_x and the preset
        # position are hint_enum drop-downs, see *_hint_enum), clamping
        # hand-typed Inspector values to what the exported LUT/palette
        # textures actually contain. Godot's hint_range only accepts
        # int/float uniforms, not vectors -- hence cell_x/y as two
        # separate placeholders rather than one vec2.
        "preset_count_max": str(preset_count - 1),
        "palette_cols": str(cols),
        "palette_rows": str(rows),
        "palette_cols_max": str(cols - 1),
        "palette_rows_max": str(rows - 1),
        # The global palette values, for targets that want to reason about
        # the palette. The colors themselves travel as palette_colors_gdscript
        # (and the PNG); groups/columns are not exported yet.
        "palette_tint": _fmt(params["tint"]),
        "palette_shade": _fmt(params["shade"]),
        "palette_hue_shift": _fmt(params.get("hue_shift", 0.0)),
        "palette_warmth": _fmt(params.get("warmth", 0.0)),
        # Every cell's color as the body of a GDScript PackedColorArray
        # literal, index y * palette_cols + x (y in the picker's numbering,
        # row 0 = lightest) -- for code that needs a cell's color without the
        # shader (the exported resource script's color_at). Straight from
        # model_palette.color_at, so it follows every palette parameter
        # (groups, columns, hue shift, warmth, ...) with nothing to port.
        "palette_colors_gdscript": _palette_colors_gdscript(params),
        # The palette's structure (groups, column labels), so Godot code and
        # the Inspector can name a cell instead of showing bare numbers.
        # Labels describe the palette at export time: reordering columns
        # shifts which column a stored x names (like presets).
        "palette_groups_gdscript": _palette_groups_gdscript(params),
        "palette_column_names_gdscript": _palette_column_names_gdscript(params),
        "palette_cell_x_enum": _palette_cell_x_enum(params),
        # The same column names for the singlecolor shader's instance uniform
        # lpc_palette_cell_x, an Inspector drop-down via `hint_enum`
        # (Godot 4.4+).
        "palette_cell_x_hint_enum": _palette_cell_x_hint_enum(params),
        # The preset names for the singlecolor shader's instance uniform
        # lpc_preset_position, likewise a `hint_enum` drop-down.
        "preset_hint_enum": _preset_hint_enum(scene),
        # The presets as the body of a shader vec4 array initializer, one per
        # line, in list order: (roughness, metallic, clearcoat, emission),
        # emission raw (before emission_factor). For sets that ship no preset
        # LUT (registry "preset_texture": False) -- exact values, no 8-bit
        # rounding, nothing for a texture import to alter.
        "preset_values_glsl": _preset_values_glsl(scene),
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
    palette_params = json.dumps(picker_interface.params_from_scene(scene), sort_keys=True)
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


def write_textures(scene, out_dir, set_id):
    """Write the palette and/or preset LUT images as PNGs into `out_dir` --
    whichever `set_id`'s registry entry asks for (`palette_texture` /
    `preset_texture`) -- via Blender's own `Image.save()`, which guarantees
    the exported pixels are byte-identical to whatever the Blender preview
    just sampled (no separate encoder to risk a rounding/gamma divergence).
    Returns the list of written filenames."""
    wanted = []
    if registry.writes_palette_texture(set_id):
        wanted.append((preview_material.ensure_palette_image, PALETTE_IMAGE_FILENAME))
    if registry.writes_preset_texture(set_id):
        wanted.append((preview_material.ensure_preset_lut_image, PRESET_LUT_IMAGE_FILENAME))
    written = []
    for ensure_image, filename in wanted:
        image = ensure_image(scene)
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


# Text form of a stable ID: Godot's ResourceUID encoding -- a non-negative
# 63-bit integer in base 34, digits 'a'..'y' then '0'..'8' (no 'z', no '9'),
# most significant first, prefixed "uid://". Verified against
# ResourceUID.id_to_text in Godot 4.8 (0 -> uid://a, 34 -> uid://ba,
# 2**63 - 1 -> uid://d4n4ub6itg400).
_UID_ALPHABET = "abcdefghijklmnopqrstuvwxy012345678"

# A template whose output name ends in one of these describes ANOTHER file
# (Godot: texture.png.import, script.gd.uid) and carries that file's ID.
SIDECAR_SUFFIXES = (".import", ".uid")


def stable_uid(filename):
    """The stable ID of the exported file `filename` ("lpc_palette.png"), in
    Godot's `uid://...` text form.

    A pure function of the output filename -- which already includes the
    namespace prefix -- so every export writes the same ID for the same file,
    on any machine, into any project: re-exporting never orphans a reference,
    and two LPC exports with different prefixes never collide. Two with the
    SAME prefix in one project would; they cannot coexist anyway (their
    GDScript class_names clash first, see constants.PREFIX)."""
    digest = hashlib.sha256(("lpc-export:" + filename).encode("utf-8")).digest()
    n = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    text = ""
    while True:
        n, digit = divmod(n, len(_UID_ALPHABET))
        text = _UID_ALPHABET[digit] + text
        if n == 0:
            return "uid://" + text


def _uid_subject(name):
    """The file a (template or output) name is about: itself, or -- for a
    sidecar -- the file it sits next to."""
    for suffix in SIDECAR_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def uid_context(template_entries, context):
    """One `uid_<name>` placeholder per file the set exports, keyed by the
    template's own name with the prefix placeholder and punctuation folded
    out ("{{prefix}}palette.png.import.tpl" -> uid_palette_png), so the key a
    template refers to does not depend on the active prefix -- while the ID
    itself does, being the `stable_uid` of the real output filename.

    Sidecars map onto their subject, so a texture that `write_textures`
    writes outside the template mechanism gets its key as soon as the set has
    an `.import` template for it."""
    uids = {}
    for entry in template_entries:
        subject = _uid_subject(_strip_tpl(entry))
        key = "uid_" + re.sub(r"\W+", "_", subject.replace("{{prefix}}", "")).strip("_")
        uids[key] = stable_uid(_render(subject, context))
    return uids


def render_set(set_id, out_dir, context):
    """Render every `.tpl` in the set's folder into `out_dir`. Returns the list
    of written filenames. Raises ValueError for an unknown set, OSError on IO.

    `context` is extended by `uid_context` for the set's own files before
    rendering, so templates can refer to each other by stable ID."""
    tdir = registry.template_dir(set_id)
    if tdir is None or not os.path.isdir(tdir):
        raise ValueError(f"unknown export template set: {set_id!r}")
    entries = sorted(e for e in os.listdir(tdir) if e.endswith(".tpl"))
    context = {**context, **uid_context(entries, context)}
    written = []
    for entry in entries:
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
        """Export the selected template set into a chosen folder: the shader(s), material(s), and the data textures the target uses. Pick the target in the dropdown; the per-face references (palette cell + preset index) travel in the lpc UV maps, so import the .blend separately"""

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
                written += write_textures(scene, out_dir, set_id)
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

