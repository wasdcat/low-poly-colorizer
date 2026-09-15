# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""The one shared preview material (texture/array lookup redesign 2026-06-19).

The whole project shares ONE Godot-compatible Principled material. Per-face
variation is driven entirely by mesh data the stock glTF export carries, but
unlike the previous design, the mesh no longer carries the FINAL values --
it carries small REFERENCES, and the actual values live in two small images:

    lpc_uv0 (palette cell x, y)  -> sampled from the palette image
                                    -> Base Color AND Emission Color
    lpc_uv1.x (preset position)  -> sampled from the preset LUT image
                                    -> Roughness / Metallic / Coat Weight /
                                       (raw) Emission
    global emission_factor       -> multiplies the emission
    global clearcoat_roughness   -> Coat Roughness

This mirrors what the exported Godot shader does (texture lookups instead of
raw per-face values), so the Blender preview and the Godot render are driven
by the same two textures and stay in sync by construction. It also means a
palette-settings edit (saturation, tint, ...) or a preset value edit now only
regenerates an image -- no per-face mesh write, and (for palette edits) a
capability the old baked-value design never had: already-painted faces pick
up the new color automatically.

There is NO default-brush material: faces left unpainted carry no lpc material
(an empty slot 0 reserved by the partial paint path on material-less objects,
or the user's own material otherwise) and render the plain default. A
whole-mesh paint binds every face to the lpc slot, so it reserves no such slot.
"Painted" means the face carries a preset uid (lpc_index != 0); the shared
material on its slot just makes that visible.

The material is "lpc-managed" via the `lpc_managed` custom prop, so
`has_real_materials` can tell an object's own materials from ours. The two
images get the same treatment (their own stamp keys, not name-based lookup,
so a foreign datablock squatting the name never gets mistaken for ours).
"""

import bpy

from .. import constants
from ..model import faces as model_faces

# The single shared material datablock name. Named for the "multicolor"
# variant since the Blender preview only ever renders that one (per-face data
# via UVs) -- there is no Blender-side equivalent of the export-only
# singlecolor variant (a whole-mesh override has no per-face data to read in
# the first place).
MATERIAL_NAME = constants.PREFIX + "multicolor"

# Custom-prop stamp on the material we create.
_MANAGED_KEY = constants.PREFIX + "managed"

# Bumped when the node layout changes; ensure_* rebuilds older materials.
_NODES_VERSION = 7
_VERSION_KEY = constants.PREFIX + "nodes_version"

# Node names we look up later (Blender keeps node names unique per tree).
_EMISSION_FACTOR_NODE = constants.PREFIX + "emission_factor"
_COAT_ROUGHNESS_NODE = constants.PREFIX + "clearcoat_roughness"
_LUT_COUNT_NODE = constants.PREFIX + "preset_count"

# The two managed images (palette texture + preset LUT), identified by their
# own stamp keys -- mirrors the material's _MANAGED_KEY convention exactly.
_PALETTE_IMAGE_NAME = constants.PREFIX + "palette"
_PRESET_LUT_IMAGE_NAME = constants.PREFIX + "preset_lut"
_PALETTE_MANAGED_KEY = constants.PREFIX + "palette_managed"
_LUT_MANAGED_KEY = constants.PREFIX + "preset_lut_managed"


# --------------------------------------------------------------------------
# Node helpers
# --------------------------------------------------------------------------

def _input(node, *names):
    """First existing input socket among `names` (Blender version drift:
    4.x "Coat Weight" was 3.x "Clearcoat")."""
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            return socket
    return None


def _build_nodes(material, scene):
    """The shared Principled tree: albedo + emission colour from the palette
    image (addressed by lpc_uv0), the scalar PBR params from the preset LUT
    image (addressed by lpc_uv1.x, the preset's list position), the two
    globals from named value nodes."""
    tree = material.node_tree
    tree.nodes.clear()
    links = tree.links

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (900, 0)
    principled = tree.nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (600, 0)
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    # -- Albedo (+ emission tint) from the palette image, addressed by
    # lpc_uv0. The mesh stores (u, 1-v) (model_faces._encode_uv0's glTF V
    # pre-compensation); Blender's own UV Map node has no glTF export step to
    # undo that implicitly the way Godot's import does, so undo it here with
    # one extra Math node -- the one place Blender-preview and Godot
    # consumption genuinely differ in node count, intentionally.
    uv0 = tree.nodes.new("ShaderNodeUVMap")
    uv0.uv_map = model_faces.UV0_NAME
    uv0.location = (-900, 300)
    sep0 = tree.nodes.new("ShaderNodeSeparateXYZ")
    sep0.location = (-700, 300)
    links.new(uv0.outputs["UV"], sep0.inputs["Vector"])
    unflip = tree.nodes.new("ShaderNodeMath")
    unflip.operation = "SUBTRACT"
    unflip.inputs[0].default_value = 1.0
    unflip.location = (-500, 220)
    links.new(sep0.outputs["Y"], unflip.inputs[1])
    combine0 = tree.nodes.new("ShaderNodeCombineXYZ")
    combine0.location = (-300, 300)
    links.new(sep0.outputs["X"], combine0.inputs["X"])
    links.new(unflip.outputs["Value"], combine0.inputs["Y"])

    palette_tex = tree.nodes.new("ShaderNodeTexImage")
    palette_tex.image = ensure_palette_image(scene)
    palette_tex.interpolation = "Closest"
    palette_tex.location = (-100, 300)
    links.new(combine0.outputs["Vector"], palette_tex.inputs["Vector"])
    links.new(palette_tex.outputs["Color"], principled.inputs["Base Color"])
    emission_color = _input(principled, "Emission Color", "Emission")
    if emission_color is not None:
        links.new(palette_tex.outputs["Color"], emission_color)

    # -- Roughness / Metallic / Clearcoat / Emission from the preset LUT,
    # addressed by lpc_uv1.x (the preset's list position -- a raw integer-ish
    # float, not a pre-normalized UV, so the (position+0.5)/count division
    # happens here).
    uv1 = tree.nodes.new("ShaderNodeUVMap")
    uv1.uv_map = model_faces.UV1_NAME
    uv1.location = (-900, -120)
    sep1 = tree.nodes.new("ShaderNodeSeparateXYZ")
    sep1.location = (-700, -120)
    links.new(uv1.outputs["UV"], sep1.inputs["Vector"])

    add_half = tree.nodes.new("ShaderNodeMath")
    add_half.operation = "ADD"
    add_half.inputs[1].default_value = 0.5
    add_half.location = (-500, -120)
    links.new(sep1.outputs["X"], add_half.inputs[0])

    div_count = tree.nodes.new("ShaderNodeMath")
    div_count.operation = "DIVIDE"
    div_count.name = _LUT_COUNT_NODE
    div_count.label = "Preset Count"
    div_count.inputs[1].default_value = max(len(scene.lpc_presets), 1)
    div_count.location = (-300, -120)
    links.new(add_half.outputs["Value"], div_count.inputs[0])

    combine1 = tree.nodes.new("ShaderNodeCombineXYZ")
    combine1.inputs["Y"].default_value = 0.5
    combine1.location = (-100, -120)
    links.new(div_count.outputs["Value"], combine1.inputs["X"])

    lut_tex = tree.nodes.new("ShaderNodeTexImage")
    lut_tex.image = ensure_preset_lut_image(scene)
    lut_tex.interpolation = "Closest"
    lut_tex.location = (100, -120)
    links.new(combine1.outputs["Vector"], lut_tex.inputs["Vector"])

    sep_lut = tree.nodes.new("ShaderNodeSeparateColor")
    sep_lut.location = (300, -120)
    links.new(lut_tex.outputs["Color"], sep_lut.inputs["Color"])
    links.new(sep_lut.outputs["Red"], principled.inputs["Roughness"])
    links.new(sep_lut.outputs["Green"], principled.inputs["Metallic"])
    coat = _input(principled, "Coat Weight", "Clearcoat")
    if coat is not None:
        links.new(sep_lut.outputs["Blue"], coat)

    # Emission strength = LUT alpha (raw emission) * global emission factor.
    factor = tree.nodes.new("ShaderNodeValue")
    factor.name = _EMISSION_FACTOR_NODE
    factor.label = "Emission Factor"
    factor.location = (100, -320)
    mult = tree.nodes.new("ShaderNodeMath")
    mult.operation = "MULTIPLY"
    mult.location = (300, -320)
    links.new(lut_tex.outputs["Alpha"], mult.inputs[0])
    links.new(factor.outputs["Value"], mult.inputs[1])
    strength = _input(principled, "Emission Strength")
    if strength is not None:
        links.new(mult.outputs["Value"], strength)

    # Coat roughness from a global value node.
    coat_rough_node = tree.nodes.new("ShaderNodeValue")
    coat_rough_node.name = _COAT_ROUGHNESS_NODE
    coat_rough_node.label = "Coat Roughness"
    coat_rough_node.location = (300, -480)
    coat_rough = _input(principled, "Coat Roughness", "Clearcoat Roughness")
    if coat_rough is not None:
        links.new(coat_rough_node.outputs["Value"], coat_rough)

    material[_VERSION_KEY] = _NODES_VERSION


# --------------------------------------------------------------------------
# The two managed images (palette texture + preset LUT)
# --------------------------------------------------------------------------

def _find_managed_image(stamp_key):
    for image in bpy.data.images:
        if image.get(stamp_key) == 1:
            return image
    return None


def _refill_image(image, pixels, width, height):
    """Resize (if needed) then ALWAYS fully refill from `pixels` -- never
    rely on `scale()`'s resampled content, since adjacent palette cells /
    adjacent presets must never blend into each other.

    Finally PACK the result into the .blend. These are GENERATED images
    (bpy.data.images.new): Blender does NOT store a generated image's pixel
    data on save -- it regenerates a blank buffer from generated_type/color
    on load -- so without packing, a saved-then-reopened file (e.g. shared
    via git) shows the managed textures present but empty. Packing writes
    the current pixels into the .blend and re-runs on every refill, so the
    packed data always tracks the latest palette/preset params."""
    if (image.size[0], image.size[1]) != (width, height):
        image.scale(width, height)
    image.pixels.foreach_set(pixels)
    image.update()
    image.pack()


def ensure_palette_image(scene):
    """The palette as a texture (cols x rows, Non-Color, Closest-sampled) --
    created if missing, resized + refilled to match the current palette
    params otherwise. Shared by this module's node graph and the Godot
    export (export/exporter.py) -- both must render identical colors."""
    from ..model import palette as model_palette
    from ..picker import interface as picker_interface

    params = picker_interface.params_from_scene(scene)
    pixels, cols, rows = model_palette.build_pixels(params)
    image = _find_managed_image(_PALETTE_MANAGED_KEY)
    if image is None:
        image = bpy.data.images.new(
            _PALETTE_IMAGE_NAME, width=cols, height=rows,
            alpha=True, float_buffer=True,
        )
        image[_PALETTE_MANAGED_KEY] = 1
        image.use_fake_user = True
        image.colorspace_settings.name = "Non-Color"
    _refill_image(image, pixels, cols, rows)
    return image


def ensure_preset_lut_image(scene):
    """Every preset's PBR params as a 1-row texture, one texel per preset IN
    LIST ORDER (R=roughness, G=metallic, B=clearcoat, A=emission) -- created
    if missing, resized + refilled to match the current preset list
    otherwise."""
    from ..model import presets as model_presets

    pixels = model_presets.build_preset_lut_pixels(scene)
    width = len(pixels) // 4
    image = _find_managed_image(_LUT_MANAGED_KEY)
    if image is None:
        image = bpy.data.images.new(
            _PRESET_LUT_IMAGE_NAME, width=width, height=1,
            alpha=True, float_buffer=True,
        )
        image[_LUT_MANAGED_KEY] = 1
        image.use_fake_user = True
        image.colorspace_settings.name = "Non-Color"
    _refill_image(image, pixels, width, 1)
    return image


def update_palette_image(scene):
    """Palette params changed -> regenerate the palette image in place. No
    mesh traversal: every face's lpc_uv0 already names a (x, y) cell
    coordinate, which stays valid -- only the COLOR at that coordinate
    changes, automatically repainting every already-painted face."""
    if _find_managed_material() is None:
        return  # nothing painted yet; the image doesn't need to exist
    ensure_palette_image(scene)


def update_preset_lut(scene):
    """A preset's VALUES changed, or the preset LIST changed (add/delete/
    duplicate/import) -> regenerate the LUT image (resizing if the preset
    count changed) and resync the LUT-count divisor node. No-op if the
    material doesn't exist yet."""
    material = _find_managed_material()
    if material is None or not material.use_nodes:
        return
    ensure_preset_lut_image(scene)
    tree = material.node_tree
    count_node = tree.nodes.get(_LUT_COUNT_NODE)
    if count_node is not None:
        count_node.inputs[1].default_value = max(len(scene.lpc_presets), 1)


# --------------------------------------------------------------------------
# The shared material
# --------------------------------------------------------------------------

def is_lpc_managed(material):
    return material is not None and material.get(_MANAGED_KEY) == 1


def _find_managed_material():
    """The shared lpc material if it exists -- identified by the managed stamp,
    NOT by name (a foreign datablock may squat MATERIAL_NAME). There is only
    ever one; the first managed material wins."""
    for material in bpy.data.materials:
        if is_lpc_managed(material):
            return material
    return None


def update_globals(scene):
    """Push the scene globals onto the shared material's value nodes
    (Invariant 8). No-op if the material does not exist yet."""
    material = _find_managed_material()
    if material is None or not material.use_nodes:
        return
    g = scene.lpc_globals
    tree = material.node_tree
    factor = tree.nodes.get(_EMISSION_FACTOR_NODE)
    if factor is not None:
        factor.outputs["Value"].default_value = g.emission_factor
    coat_rough = tree.nodes.get(_COAT_ROUGHNESS_NODE)
    if coat_rough is not None:
        coat_rough.outputs["Value"].default_value = g.clearcoat_roughness


def ensure_lpc_material(scene):
    """The shared material, identified by its managed stamp (NOT by name, so a
    foreign datablock squatting MATERIAL_NAME never spawns a duplicate),
    created + stamped + fake-user + globals-synced if missing or built by an
    older version. A fresh material is named MATERIAL_NAME (Blender
    auto-suffixes if that name is already taken)."""
    material = _find_managed_material()
    if material is None:
        material = bpy.data.materials.new(MATERIAL_NAME)
    material.use_nodes = True
    if material.get(_VERSION_KEY) != _NODES_VERSION:
        _build_nodes(material, scene)
    material[_MANAGED_KEY] = 1
    material.use_fake_user = True
    update_globals(scene)
    return material


# --------------------------------------------------------------------------
# Slot management (lazy, per object) -- one shared material on a slot
# --------------------------------------------------------------------------

def has_real_materials(mesh):
    """True if the mesh has any slot holding a NON-lpc material -- the user's
    own materials, which unpainted faces keep. A mesh with only the lpc
    material (or empty slots) lets its unpainted faces fall back to slot 0."""
    return any(
        m is not None and not is_lpc_managed(m) for m in mesh.materials
    )


def mesh_is_painted(mesh):
    """True if the mesh carries the shared lpc material in any slot -- i.e. it
    has been painted by us (mode-stable, name-only signal)."""
    return any(is_lpc_managed(m) for m in mesh.materials)


def mesh_needs_uv_fix(mesh):
    """A PAINTED mesh whose param UVs are missing, incomplete, or not the
    leading two layers -- so Godot would not import them as UV/UV2. Fixed by
    the 'Fix UV Maps' operator."""
    return mesh_is_painted(mesh) and model_faces.param_uvs_status(mesh) != "ok"


def _slot_of_material(mesh, material):
    for i, m in enumerate(mesh.materials):
        if m is material:
            return i
    return -1


def ensure_lpc_slot(mesh, scene):
    """Index of the slot holding the shared lpc material on `mesh`, appending
    it if missing (lazy: an object gets the slot only when first painted)."""
    material = ensure_lpc_material(scene)
    idx = _slot_of_material(mesh, material)
    if idx == -1:
        mesh.materials.append(material)
        idx = len(mesh.materials) - 1
    return idx


def ensure_unpainted_front(obj):
    """Keep slot 0 of a material-less object EMPTY so faces left unpainted
    (material_index 0) never point at the shared material -- they render the
    plain default look instead. No-op on an object with its own materials
    (unpainted faces keep the user's material there).

    Called ONLY from the partial (Edit Mode) paint path, where genuinely
    unpainted faces exist and need this empty slot. The whole-mesh path binds
    every face to the lpc slot and deliberately does NOT reserve slot 0 (an
    empty slot 0 would be unreferenced -- clutter in Blender and a spurious
    material on Godot import). New geometry is not a reason to reserve it: an
    extrude/subdivide copies the source face's material_index (and lpc_uv0 /
    lpc_index), so it inherits the paint no matter which slot lpc occupies.

    Must run before the first ensure_lpc_slot on a fresh object, so the
    reserved empty slot lands at 0 and the lpc material goes to slot >= 1."""
    mesh = obj.data
    if has_real_materials(mesh):
        return
    if len(mesh.materials) == 0:
        mesh.materials.append(None)

