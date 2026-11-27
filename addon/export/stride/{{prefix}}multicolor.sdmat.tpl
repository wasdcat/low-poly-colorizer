!MaterialAsset
Id: {{uid_multicolor_sdmat}}
SerializedVersion: {Stride: 2.0.0.0}
Tags: []
Attributes:
    MicroSurface: !MaterialGlossinessMapFeature
        GlossinessMap: !ComputeTextureScalar
            Texture: {{uid_preset_lut_sdtex}}:{{prefix}}preset_lut
            FallbackValue:
                Value: 0.5
            Filtering: Point
            AddressModeU: Clamp
            AddressModeV: Clamp
            TexcoordIndex: Texcoord1
            Scale: {X: {{preset_texel_scale}}, Y: 0.0}
            Offset: {X: {{preset_texel_offset}}, Y: 0.5}
            Channel: R
        Invert: true
    Diffuse: !MaterialDiffuseMapFeature
        DiffuseMap: !ComputeTextureColor
            Texture: {{uid_palette_sdtex}}:{{prefix}}palette
            FallbackValue:
                Value: {R: 1.0, G: 1.0, B: 1.0, A: 1.0}
            Filtering: Point
            AddressModeU: Clamp
            AddressModeV: Clamp
            TexcoordIndex: Texcoord0
            Scale: {X: 1.0, Y: -1.0}
            Offset: {X: 0.0, Y: 1.0}
            Swizzle: null
    DiffuseModel: !MaterialDiffuseLambertModelFeature {}
    Specular: !MaterialMetalnessMapFeature
        MetalnessMap: !ComputeTextureScalar
            Texture: {{uid_preset_lut_sdtex}}:{{prefix}}preset_lut
            FallbackValue:
                Value: 0.0
            Filtering: Point
            AddressModeU: Clamp
            AddressModeV: Clamp
            TexcoordIndex: Texcoord1
            Scale: {X: {{preset_texel_scale}}, Y: 0.0}
            Offset: {X: {{preset_texel_offset}}, Y: 0.5}
            Channel: G
    SpecularModel: !MaterialSpecularMicrofacetModelFeature
        Fresnel: !MaterialSpecularMicrofacetFresnelSchlick {}
        Visibility: !MaterialSpecularMicrofacetVisibilitySmithSchlickGGX {}
        NormalDistribution: !MaterialSpecularMicrofacetNormalDistributionGGX {}
        Environment: !MaterialSpecularMicrofacetEnvironmentGGXLUT {}
    Emissive: !MaterialEmissiveMapFeature
        EmissiveMap: !ComputeTextureColor
            Texture: {{uid_palette_sdtex}}:{{prefix}}palette
            FallbackValue:
                Value: {R: 1.0, G: 1.0, B: 1.0, A: 1.0}
            Filtering: Point
            AddressModeU: Clamp
            AddressModeV: Clamp
            TexcoordIndex: Texcoord0
            Scale: {X: 1.0, Y: -1.0}
            Offset: {X: 0.0, Y: 1.0}
            Swizzle: null
        Intensity: !ComputeBinaryScalar
            Operator: Multiply
            LeftChild: !ComputeTextureScalar
                Texture: {{uid_preset_lut_sdtex}}:{{prefix}}preset_lut
                FallbackValue:
                    Value: 0.0
                Filtering: Point
                AddressModeU: Clamp
                AddressModeV: Clamp
                TexcoordIndex: Texcoord1
                Scale: {X: {{preset_texel_scale}}, Y: 0.0}
                Offset: {X: {{preset_texel_offset}}, Y: 0.5}
                Channel: A
            RightChild: !ComputeFloat
                Value: {{emission_factor}}
        UseAlpha: false
    Overrides:
        UVScale: {X: 1.0, Y: 1.0}
Layers: {}
