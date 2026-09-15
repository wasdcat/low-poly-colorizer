# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""LPC Geometry Node Group (lpc_set_material).

Provides a reusable Geometry Node group for procedurally painting mesh faces
with LPC palette cell references (lpc_uv0), preset list positions (lpc_uv1),
and binding them to the shared preview material (lpc_multicolor).

Uses Blender 4.1+ `GeometryNodeMenuSwitch` and `NodeSocketMenu` to expose
the active preset list as a dynamic dropdown menu in Geometry Nodes.
"""

try:
    import bpy
except ModuleNotFoundError:  # plain-python tests without Blender
    bpy = None

try:
    from .. import constants
    from ..model import palette as model_palette
    from . import preview_material
except ImportError:  # plain-python tests put the addon dir on sys.path
    import constants
    from model import palette as model_palette

# Node group datablock name.
NODE_GROUP_NAME = constants.PREFIX + "set_material"
NODE_GROUP_LABEL = "LPC Set Material"

# Custom-prop stamp on the node group we create.
_MANAGED_KEY = constants.PREFIX + "geo_nodes_managed"

# Bumped when the internal node graph changes.
_NODES_VERSION = 1
_VERSION_KEY = constants.PREFIX + "geo_nodes_version"

# Named internal node identifiers for fast updates without rebuilding.
_MENU_SWITCH_NODE = constants.PREFIX + "menu_switch"
_DIV_COLS_NODE = constants.PREFIX + "div_cols"
_DIV_ROWS_NODE = constants.PREFIX + "div_rows"
_SET_MATERIAL_NODE = constants.PREFIX + "set_material"


def is_lpc_managed(node_group):
    return node_group is not None and node_group.get(_MANAGED_KEY) == 1


def _find_managed_node_group():
    """The shared lpc geometry node group if it exists -- identified by the
    managed stamp, not by name alone."""
    if bpy is None:
        return None
    for ng in bpy.data.node_groups:
        if ng.type == "GEOMETRY" and is_lpc_managed(ng):
            return ng
    return None


def _sync_menu_switch(menu_switch, scene):
    """Sync the Menu Switch node's enum items and default input values with
    the current scene presets."""
    menu_switch.enum_definition.enum_items.clear()
    presets = list(scene.lpc_presets)
    if not presets:
        menu_switch.enum_definition.enum_items.new("No Presets")
        menu_switch.inputs["No Presets"].default_value = 0
        return

    for i, preset in enumerate(presets):
        item_name = preset.name if preset.name else f"Preset {i + 1}"
        # Ensure item name is unique within the menu switch
        if item_name not in menu_switch.enum_definition.enum_items:
            menu_switch.enum_definition.enum_items.new(item_name)
            menu_switch.inputs[item_name].default_value = i


def _build_nodes(ng, scene):
    """Construct the geometry node tree:
    Inputs: Geometry, Selection, Palette Cell X, Palette Cell Y, Preset (Menu)
    Math: UV0 (Texel-Center + glTF V-Flip), UV1 (Preset List Position)
    Store Named Attributes: lpc_uv0 (Corner, Float2), lpc_uv1 (Corner, Float2)
    Set Material: lpc_multicolor
    Output: Geometry
    """
    from ..picker import interface as picker_interface

    params = picker_interface.params_from_scene(scene)
    cols, rows = model_palette.cell_count(params)

    ng.nodes.clear()
    ng.interface.clear()

    # -- Interface sockets --
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")

    sock_sel = ng.interface.new_socket("Selection", in_out="INPUT", socket_type="NodeSocketBool")
    sock_sel.default_value = True

    sock_x = ng.interface.new_socket("Palette Cell X", in_out="INPUT", socket_type="NodeSocketInt")
    sock_x.default_value = 0
    sock_x.min_value = 0
    sock_x.max_value = max(cols - 1, 0)

    sock_y = ng.interface.new_socket("Palette Cell Y", in_out="INPUT", socket_type="NodeSocketInt")
    sock_y.default_value = 0
    sock_y.min_value = 0
    sock_y.max_value = max(rows - 1, 0)

    ng.interface.new_socket("Preset", in_out="INPUT", socket_type="NodeSocketMenu")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    links = ng.links

    in_node = ng.nodes.new("NodeGroupInput")
    in_node.location = (-700, 0)

    out_node = ng.nodes.new("NodeGroupOutput")
    out_node.location = (1100, 0)

    # -- Preset Resolution via Menu Switch --
    menu_switch = ng.nodes.new("GeometryNodeMenuSwitch")
    menu_switch.name = _MENU_SWITCH_NODE
    menu_switch.label = "Preset Menu Switch"
    menu_switch.data_type = "INT"
    menu_switch.location = (-200, -300)
    _sync_menu_switch(menu_switch, scene)
    links.new(in_node.outputs["Preset"], menu_switch.inputs["Menu"])

    # -- UV0 Math: U = (X + 0.5) / cols, V = 1.0 - (Y + 0.5) / rows --
    add_half_x = ng.nodes.new("ShaderNodeMath")
    add_half_x.operation = "ADD"
    add_half_x.inputs[1].default_value = 0.5
    add_half_x.location = (-400, 250)
    links.new(in_node.outputs["Palette Cell X"], add_half_x.inputs[0])

    div_cols = ng.nodes.new("ShaderNodeMath")
    div_cols.operation = "DIVIDE"
    div_cols.name = _DIV_COLS_NODE
    div_cols.label = "Palette Columns"
    div_cols.inputs[1].default_value = float(cols)
    div_cols.location = (-200, 250)
    links.new(add_half_x.outputs["Value"], div_cols.inputs[0])

    add_half_y = ng.nodes.new("ShaderNodeMath")
    add_half_y.operation = "ADD"
    add_half_y.inputs[1].default_value = 0.5
    add_half_y.location = (-400, 50)
    links.new(in_node.outputs["Palette Cell Y"], add_half_y.inputs[0])

    div_rows = ng.nodes.new("ShaderNodeMath")
    div_rows.operation = "DIVIDE"
    div_rows.name = _DIV_ROWS_NODE
    div_rows.label = "Palette Rows"
    div_rows.inputs[1].default_value = float(rows)
    div_rows.location = (-200, 50)
    links.new(add_half_y.outputs["Value"], div_rows.inputs[0])

    sub_v = ng.nodes.new("ShaderNodeMath")
    sub_v.operation = "SUBTRACT"
    sub_v.inputs[0].default_value = 1.0
    sub_v.location = (0, 50)
    links.new(div_rows.outputs["Value"], sub_v.inputs[1])

    combine_uv0 = ng.nodes.new("ShaderNodeCombineXYZ")
    combine_uv0.location = (200, 150)
    links.new(div_cols.outputs["Value"], combine_uv0.inputs["X"])
    links.new(sub_v.outputs["Value"], combine_uv0.inputs["Y"])

    # -- Store lpc_uv0 --
    store_uv0 = ng.nodes.new("GeometryNodeStoreNamedAttribute")
    store_uv0.domain = "CORNER"
    store_uv0.data_type = "FLOAT2"
    store_uv0.inputs["Name"].default_value = constants.PREFIX + "uv0"
    store_uv0.location = (450, 250)
    links.new(in_node.outputs["Geometry"], store_uv0.inputs["Geometry"])
    links.new(in_node.outputs["Selection"], store_uv0.inputs["Selection"])
    links.new(combine_uv0.outputs["Vector"], store_uv0.inputs["Value"])

    # -- UV1 Math: Vector(PresetPosition, 0.0, 0.0) --
    combine_uv1 = ng.nodes.new("ShaderNodeCombineXYZ")
    combine_uv1.location = (200, -200)
    links.new(menu_switch.outputs["Output"], combine_uv1.inputs["X"])

    # -- Store lpc_uv1 --
    store_uv1 = ng.nodes.new("GeometryNodeStoreNamedAttribute")
    store_uv1.domain = "CORNER"
    store_uv1.data_type = "FLOAT2"
    store_uv1.inputs["Name"].default_value = constants.PREFIX + "uv1"
    store_uv1.location = (680, 250)
    links.new(store_uv0.outputs["Geometry"], store_uv1.inputs["Geometry"])
    links.new(in_node.outputs["Selection"], store_uv1.inputs["Selection"])
    links.new(combine_uv1.outputs["Vector"], store_uv1.inputs["Value"])

    # -- Set Material --
    set_mat = ng.nodes.new("GeometryNodeSetMaterial")
    set_mat.name = _SET_MATERIAL_NODE
    set_mat.inputs["Material"].default_value = preview_material.ensure_lpc_material(scene)
    set_mat.location = (900, 250)
    links.new(store_uv1.outputs["Geometry"], set_mat.inputs["Geometry"])
    links.new(in_node.outputs["Selection"], set_mat.inputs["Selection"])

    links.new(set_mat.outputs["Geometry"], out_node.inputs["Geometry"])

    ng[_VERSION_KEY] = _NODES_VERSION


def ensure_lpc_geo_node_group(scene):
    """The shared LPC Geometry Node group, created and stamped if missing or
    rebuilt if an older version."""
    if bpy is None:
        return None
    ng = _find_managed_node_group()
    if ng is None:
        ng = bpy.data.node_groups.new(NODE_GROUP_NAME, "GeometryNodeTree")
    if ng.get(_VERSION_KEY) != _NODES_VERSION:
        _build_nodes(ng, scene)
    ng[_MANAGED_KEY] = 1
    ng.use_fake_user = True
    update_lpc_geo_node_group(scene)
    return ng


def update_lpc_geo_node_group(scene):
    """Sync the Menu Switch options, divisor nodes, socket ranges and material
    in the Geometry Node group with the current scene."""
    if bpy is None:
        return
    ng = _find_managed_node_group()
    if ng is None or ng.get(_VERSION_KEY) != _NODES_VERSION:
        return

    from ..picker import interface as picker_interface

    params = picker_interface.params_from_scene(scene)
    cols, rows = model_palette.cell_count(params)

    # 1. Update Menu Switch
    menu_switch = ng.nodes.get(_MENU_SWITCH_NODE)
    if menu_switch is not None:
        _sync_menu_switch(menu_switch, scene)

    # 2. Update Divisors
    div_cols = ng.nodes.get(_DIV_COLS_NODE)
    if div_cols is not None:
        div_cols.inputs[1].default_value = float(cols)

    div_rows = ng.nodes.get(_DIV_ROWS_NODE)
    if div_rows is not None:
        div_rows.inputs[1].default_value = float(rows)

    # 3. Update Interface Socket bounds
    for item in ng.interface.items_tree:
        if item.name == "Palette Cell X":
            item.max_value = max(cols - 1, 0)
        elif item.name == "Palette Cell Y":
            item.max_value = max(rows - 1, 0)

    # 4. Update Set Material node
    set_mat = ng.nodes.get(_SET_MATERIAL_NODE)
    if set_mat is not None:
        set_mat.inputs["Material"].default_value = preview_material.ensure_lpc_material(scene)


if bpy is not None:
    class LPC_OT_add_geo_node_group(bpy.types.Operator):
        """Create or add the 'LPC Set Material' Geometry Node group to the active object"""

        bl_idname = "lpc.add_geo_node_group"
        bl_label = "Create Geometry Node Group"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            scene = context.scene
            ng = ensure_lpc_geo_node_group(scene)

            obj = context.active_object
            if obj is not None and obj.type == "MESH":
                # If active object doesn't already have this modifier, add it
                mod = next(
                    (m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng),
                    None,
                )
                if mod is None:
                    mod = obj.modifiers.new(NODE_GROUP_LABEL, "NODES")
                    mod.node_group = ng
                    self.report({"INFO"}, f"Added '{NODE_GROUP_LABEL}' modifier to {obj.name}")
                else:
                    self.report({"INFO"}, f"'{NODE_GROUP_LABEL}' already present on {obj.name}")
            else:
                self.report({"INFO"}, f"Created / updated '{NODE_GROUP_LABEL}' node group")
            return {"FINISHED"}

