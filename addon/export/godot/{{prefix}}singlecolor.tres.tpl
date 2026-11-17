[gd_resource type="ShaderMaterial" load_steps=4 format=3 uid="{{uid_singlecolor_tres}}"]

[ext_resource type="Shader" uid="{{uid_singlecolor_gdshader}}" path="{{prefix}}singlecolor.gdshader" id="1"]
[ext_resource type="Texture2D" uid="{{uid_palette_png}}" path="{{palette_image_filename}}" id="2"]
[ext_resource type="Texture2D" uid="{{uid_preset_lut_png}}" path="{{preset_lut_image_filename}}" id="3"]

[resource]
resource_name = "{{prefix}}singlecolor"
shader = ExtResource("1")
shader_parameter/emission_factor = {{emission_factor}}
shader_parameter/clearcoat_roughness_value = {{clearcoat_roughness}}
shader_parameter/lpc_palette_tex = ExtResource("2")
shader_parameter/lpc_preset_lut_tex = ExtResource("3")
