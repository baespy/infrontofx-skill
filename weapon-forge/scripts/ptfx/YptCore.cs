using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Text;

namespace WeaponForge
{
    public static class Jenkins
    {
        public static uint Hash(string s)
        {
            uint h = 0;
            string l = s.ToLowerInvariant();
            for (int i = 0; i < l.Length; i++)
            {
                h += (byte)l[i];
                h += h << 10;
                h ^= h >> 6;
            }
            h += h << 3;
            h ^= h >> 11;
            h += h << 15;
            return h;
        }
    }

    public class Rsc
    {
        public uint Version;
        public uint SysFlags;
        public uint GfxFlags;
        public byte[] Sys;
        public byte[] Gfx;

        public static readonly int[] BucketShift = new int[] { 8, 7, 6, 5, 4, 3, 2, 1, 0 };

        public static int[] PageCounts(uint f)
        {
            return new int[] {
                (int)((f >> 4) & 0x1), (int)((f >> 5) & 0x3), (int)((f >> 7) & 0xF), (int)((f >> 11) & 0x3F),
                (int)((f >> 17) & 0x7F), (int)((f >> 24) & 0x1), (int)((f >> 25) & 0x1), (int)((f >> 26) & 0x1), (int)((f >> 27) & 0x1)
            };
        }

        public static long SizeFromFlags(uint f)
        {
            long baseSize = 0x200L << (int)(f & 0xF);
            int[] c = PageCounts(f);
            long total = 0;
            for (int i = 0; i < 9; i++) total += (long)c[i] * (baseSize << BucketShift[i]);
            return total;
        }

        public static int PageTotal(uint f)
        {
            int[] c = PageCounts(f);
            int n = 0;
            for (int i = 0; i < 9; i++) n += c[i];
            return n;
        }

        public static string DescribeFlags(uint f)
        {
            long baseSize = 0x200L << (int)(f & 0xF);
            int[] c = PageCounts(f);
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 9; i++)
            {
                if (c[i] == 0) continue;
                if (sb.Length > 0) sb.Append(" + ");
                sb.Append(c[i]).Append("x0x").Append((baseSize << BucketShift[i]).ToString("x"));
            }
            return sb.Length == 0 ? "empty" : sb.ToString();
        }

        public static Rsc Load(string path)
        {
            byte[] b = File.ReadAllBytes(path);
            if (b.Length < 16 || b[0] != (byte)'R' || b[1] != (byte)'S' || b[2] != (byte)'C' || b[3] != (byte)'7')
                throw new InvalidDataException("not an RSC7 resource (encrypted or wrong type): " + path);
            Rsc r = new Rsc();
            r.Version = BitConverter.ToUInt32(b, 4);
            r.SysFlags = BitConverter.ToUInt32(b, 8);
            r.GfxFlags = BitConverter.ToUInt32(b, 12);
            byte[] all;
            using (MemoryStream ms = new MemoryStream(b, 16, b.Length - 16))
            using (DeflateStream ds = new DeflateStream(ms, CompressionMode.Decompress))
            using (MemoryStream o = new MemoryStream())
            {
                ds.CopyTo(o);
                all = o.ToArray();
            }
            long ss = SizeFromFlags(r.SysFlags);
            long gs = SizeFromFlags(r.GfxFlags);
            if (ss > all.Length) ss = all.Length;
            r.Sys = new byte[ss];
            Buffer.BlockCopy(all, 0, r.Sys, 0, (int)ss);
            long rest = Math.Min(gs, all.Length - ss);
            r.Gfx = new byte[rest < 0 ? 0 : rest];
            if (rest > 0) Buffer.BlockCopy(all, (int)ss, r.Gfx, 0, (int)rest);
            return r;
        }

        public void Save(string path)
        {
            using (FileStream fs = new FileStream(path, FileMode.Create, FileAccess.Write))
            {
                fs.Write(new byte[] { (byte)'R', (byte)'S', (byte)'C', (byte)'7' }, 0, 4);
                fs.Write(BitConverter.GetBytes(Version), 0, 4);
                fs.Write(BitConverter.GetBytes(SysFlags), 0, 4);
                fs.Write(BitConverter.GetBytes(GfxFlags), 0, 4);
                using (DeflateStream ds = new DeflateStream(fs, CompressionLevel.Optimal, true))
                {
                    ds.Write(Sys, 0, Sys.Length);
                    if (Gfx != null && Gfx.Length > 0) ds.Write(Gfx, 0, Gfx.Length);
                }
            }
        }
    }

    public class Field
    {
        public string Type;
        public string Name;
        public string Arg;
        public int Off;
        public int Size;
    }

    public class StructDef
    {
        public string Name;
        public int Size;
        public List<Field> Fields = new List<Field>();
        public Dictionary<string, Field> ByName = new Dictionary<string, Field>();
    }

    public static class Schema
    {
        public static Dictionary<string, StructDef> Defs = new Dictionary<string, StructDef>();
        public static Dictionary<uint, string> BehaviourByHash = new Dictionary<uint, string>();
        public static Dictionary<string, uint> BehaviourHash = new Dictionary<string, uint>();
        public static Dictionary<uint, string> KfpNames = new Dictionary<uint, string>();
        public static Dictionary<uint, string> VarNames = new Dictionary<uint, string>();

        const string BehBase = "u32 VFT; u32 U4; h32 Type; u32 UC; kplist KeyframeProps; u64 U20; u64 U28; ";
        const string VarBase = "u32 VFT; u32 U4; u64 U8; h32 Name; u8 Type; u8 U15; u16 U16; ";

        static int TypeSize(string t, string arg)
        {
            switch (t)
            {
                case "u8": return 1;
                case "u16": return 2;
                case "u32": case "i32": case "f32": case "h32": case "rgba": return 4;
                case "u64": case "str": case "ptr": case "iptr": case "gptr": return 8;
                case "v3": return 12;
                case "v4": return 16;
                case "c32": return 32;
                case "kfp": return 0x90;
                case "list": case "plist": case "kplist": case "hlist": return 16;
                case "sub": return Defs[arg].Size;
            }
            throw new InvalidOperationException("unknown field type " + t);
        }

        static void Def(string name, int size, string dsl)
        {
            StructDef d = new StructDef();
            d.Name = name;
            d.Size = size;
            int off = 0;
            foreach (string raw in dsl.Split(';'))
            {
                string s = raw.Trim();
                if (s.Length == 0) continue;
                string[] p = s.Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                Field f = new Field();
                f.Type = p[0];
                f.Name = p[1];
                f.Arg = p.Length > 2 ? p[2] : null;
                f.Off = off;
                f.Size = TypeSize(f.Type, f.Arg);
                off += f.Size;
                d.Fields.Add(f);
                d.ByName[f.Name] = f;
            }
            if (off != size) throw new InvalidOperationException("schema size mismatch for " + name + ": 0x" + off.ToString("x") + " vs 0x" + size.ToString("x"));
            Defs[name] = d;
        }

        static void Beh(string name, uint hash, int size, string extra)
        {
            Def("Beh_" + name, size, BehBase + extra);
            BehaviourByHash[hash] = name;
            BehaviourHash[name] = hash;
        }

        static Schema()
        {
            Def("Keyframe", 0x20, "v4 Time; v4 Value");
            Def("KFP", 0x90, "u32 VFT; u32 P0; u64 Evolved; u64 P1; u64 P2; u64 P3; u64 P4; u64 P5; u64 P6; u64 P7; u64 P8; u64 P9; u64 P10; u64 P11; h32 Name; u8 InvertBiasLink; u8 RandomIndex; u16 Unused; list Values Keyframe; u64 P12; u64 P13");
            Def("Root", 0x60, "u32 VFT; u32 U4; ptr PageMap PageMap; str Name; u64 U18; ptr TextureDictionary TexDict; u64 U28; ptr DrawableDictionary DrawDict; ptr ParticleRuleDictionary Dict_ParticleRule; u64 U40; ptr DictA DictAuto; ptr DictB DictAuto; u64 U58");
            Def("PageMap", 0x10, "u64 U0; u8 SysPages; u8 GfxPages; u16 UA; u32 UC");
            Def("TexDict", 0x40, "u32 VFT; u32 U4; u64 U8; u64 U10; u64 U18; hlist Hashes; plist Items Texture");
            Def("DrawDict", 0x40, "u32 VFT; u32 U4; u64 U8; u64 U10; u64 U18; hlist Hashes; plist Items Opaque");
            Def("Dict_ParticleRule", 0x40, "u32 VFT; u32 U4; u64 U8; u64 U10; u64 U18; hlist Hashes; plist Items ParticleRule");
            Def("Dict_EffectRule", 0x40, "u32 VFT; u32 U4; u64 U8; u64 U10; u64 U18; hlist Hashes; plist Items EffectRule");
            Def("Dict_EmitterRule", 0x40, "u32 VFT; u32 U4; u64 U8; u64 U10; u64 U18; hlist Hashes; plist Items EmitterRule");
            Def("Texture", 0x90, "u32 VFT; u32 U4; u64 U8; u64 U10; u64 U18; u64 U20; str Name; u16 U30; u16 U32; u32 U34; u64 U38; u32 UsageData; u32 U44; u32 ExtraFlags; u32 U4C; u16 Width; u16 Height; u16 Depth; u16 Stride; u32 Format; u8 U5C; u8 Levels; u16 U5E; u64 U60; u64 U68; gptr Data; u64 U78; u64 U80; u64 U88");
            Def("Spawner", 0x70, "u32 VFT; u32 P0; u64 P1; u64 P2; f32 DurationScalarMin; f32 PlaybackRateScalarMin; rgba ColourTintScalarMin; f32 ZoomScalarMin; u32 FlagsMin; u32 P3; u64 P4; f32 DurationScalarMax; f32 PlaybackRateScalarMax; rgba ColourTintScalarMax; f32 ZoomScalarMax; u32 FlagsMax; u32 P5; u64 P6; ptr EffectRule EffectRule; str EffectRuleName; f32 TriggerInfo; u8 InheritsPointLife; u8 TracksPointPos; u8 TracksPointDir; u8 TracksPointNegDir");
            Def("BiasLink", 0x58, "c32 Name; u64 P0; u64 P1; u64 P2; u64 P3; hlist KeyframePropIDs; u8 RandomIndex; u8 P5; u16 P6; u32 P7");
            Def("PDrawable", 0x30, "f32 BoundBoxWidth; f32 BoundBoxHeight; f32 BoundBoxDepth; f32 BoundingSphereRadius; str Name; ptr Drawable Opaque; h32 NameHash; u32 P0; u64 P1");
            Def("ParticleRule", 0x240, "u32 VFT; u32 P0; u64 P1; u32 RefCount; u32 P3; u64 UIData; sub EffectSpawnerAtRatio Spawner; sub EffectSpawnerOnCollision Spawner; i32 CullMode; i32 BlendSet; i32 LightingMode; u8 DepthWrite; u8 DepthTest; u8 AlphaBlend; u8 P4; u32 P5; f32 FileVersion; u32 TexFrameIDMin; u32 TexFrameIDMax; str Name; plist AllBehaviours Behaviour; plist InitBehaviours Behaviour; plist UpdateBehaviours Behaviour; plist UpdateFinalizeBehaviours Behaviour; plist DrawBehaviours Behaviour; u64 Release1; u64 Release2; list BiasLinks BiasLink; u64 PointPool; u64 Func1; u64 Func2; u32 VFT2; u32 P6; str ShaderTemplateName; str ShaderTemplateTechniqueName; u64 ShaderTemplate; u32 ShaderTemplateTechniqueID; u32 P7; u32 VFT3; u32 P8; u32 DiffuseMode; u32 ProjectionMode; u8 IsLit; u8 IsSoft; u8 IsScreenSpace; u8 IsRefract; u8 IsNormalSpec; u8 P9; u16 P10; plist ShaderVars ShaderVar; u8 IsDataInSync; u8 P11; u16 P12; u32 P13; h32 ShaderTemplateHashName; u32 P14; list Drawables PDrawable; u8 SortType; u8 DrawType; u8 Flags; u8 RuntimeFlags; u32 P15; u64 Unused00; u64 WindBehaviour; u64 P16");
            Def("EffectRule", 0x3C0, "u32 VFT; u32 U4; u64 U8; u64 RefCount; f32 FileVersion; u32 P0; str Name; ptr EffectList Root; u32 VFT2; u32 Unused00; plist EventEmitters EventEmitter; ptr EvolutionList EvolutionList; i32 NumLoops; u8 SortEventsByDistance; u8 DrawListID; u8 IsShortLived; u8 HasNoShadows; u64 Pad00; v3 VRandomOffsetPos; u32 Pad01; f32 PreUpdateTime; f32 PreUpdateTimeInterval; f32 DurationMin; f32 DurationMax; f32 PlaybackRateScalarMin; f32 PlaybackRateScalarMax; u8 ViewportCullingMode; u8 RenderWhenViewportCulled; u8 UpdateWhenViewportCulled; u8 EmitWhenViewportCulled; u8 DistanceCullingMode; u8 RenderWhenDistanceCulled; u8 UpdateWhenDistanceCulled; u8 EmitWhenDistanceCulled; v3 ViewportCullingSphereOffset; u32 Pad02; f32 ViewportCullingSphereRadius; f32 DistanceCullingFadeDist; f32 DistanceCullingCullDist; f32 LodEvoDistanceMin; f32 LodEvoDistanceMax; f32 CollisionRange; f32 CollisionProbeDistance; u8 CollisionType; u8 ShareEntityCollisions; u8 OnlyUseBVHCollisions; u8 GameFlags; kfp ColourTintMinKFP; kfp ColourTintMaxKFP; kfp ZoomScalarKFP; kfp DataSphereKFP; kfp DataCapsuleKFP; kplist KeyframeProps; u8 ColourTintMaxEnable; u8 UseDataVolume; u8 DataVolumeType; u8 Pad03; u32 NumActiveInstances; f32 ZoomLevel; u32 Pad04; u64 Pad05; u64 Pad06");
            Def("EventEmitter", 0x70, "u32 VFT; u32 P0; u32 Index; u32 EventType; f32 StartRatio; f32 EndRatio; ptr EvolutionList EvolutionList; u64 U20; u64 U28; str EmitterRuleName; str ParticleRuleName; ptr EmitterRule EmitterRule; ptr ParticleRule ParticleRule; f32 PlaybackRateScalarMin; f32 PlaybackRateScalarMax; f32 ZoomScalarMin; f32 ZoomScalarMax; rgba ColourTintMin; rgba ColourTintMax; u64 P4");
            Def("Evolution", 24, "str Name; u64 P0; u64 P1");
            Def("EvoKF", 0x30, "list Keyframes Keyframe; u64 P0; u64 P1; i32 EvolutionID; u8 IsLodEvolution; u8 P2; u16 P3; u64 P4");
            Def("EvoKFProps", 24, "list EvolvedKeyframes EvoKF; h32 Name; u32 BlendMode");
            Def("EvoMap", 0x10, "h32 Name; u32 U4; iptr Item");
            Def("EvolutionList", 0x40, "list Evolutions Evolution; list EvolvedKeyframeProps EvoKFProps; u64 U20; list EvolvedKeyframePropMap EvoMap; u64 U38");
            Def("EmitterRule", 0x630, "u32 VFT; u32 U4; u64 U8; u32 RefCount; u32 U14; f32 FileVersion; u32 P2; str Name; u64 LastEvoList; u64 UIData; ptr CreationDomain Domain; u64 P3; ptr TargetDomain Domain; u64 P4; ptr AttractorDomain Domain; u64 P5; u64 P6; u64 P7; kfp SpawnRateOverTimeKFP; kfp SpawnRateOverDistKFP; kfp ParticleLifeKFP; kfp PlaybackRateScalarKFP; kfp SpeedScalarKFP; kfp SizeScalarKFP; kfp AccnScalarKFP; kfp DampeningScalarKFP; kfp MatrixWeightScalarKFP; kfp InheritVelocityKFP; kplist KeyframeProps; u8 IsOneShot; u8 P9; u16 P10; u32 P11");
            Def("Domain", 0x280, "u32 VFT; u32 P0; u32 Index; u8 DomainType; u8 P1; u16 P2; u8 IsWorldSpace; u8 IsPointRelative; u8 IsCreationRelative; u8 IsTargetRelative; u32 P3; kfp PositionKFP; kfp RotationKFP; kfp SizeOuterKFP; kfp SizeInnerKFP; f32 FileVersion; u32 P4; kplist KeyframeProps; u64 P5; u64 P6");

            Beh("Age", 0xF5B33BAA, 0x30, "");
            Beh("Acceleration", 0xD63D9F1B, 0x170, "kfp XYZMinKFP; kfp XYZMaxKFP; u64 Unused00; i32 ReferenceSpace; u8 IsAffectedByZoom; u8 EnableGravity; u16 P0; u64 P1; u64 P2");
            Beh("Velocity", 0x6C0719BC, 0x30, "");
            Beh("Rotation", 0x1EE64552, 0x280, "kfp InitialAngleMinKFP; kfp InitialAngleMaxKFP; kfp AngleMinKFP; kfp AngleMaxKFP; i32 InitRotationMode; i32 UpdateRotationMode; u8 AccumulateAngle; u8 RotateAngleAxes; u8 RotateInitAngleAxes; u8 P0; f32 SpeedFadeThreshold");
            Beh("Size", 0x38B60240, 0x280, "kfp WhdMinKFP; kfp WhdMaxKFP; kfp TblrScalarKFP; kfp TblrVelScalarKFP; i32 KeyframeMode; u8 IsProportional; u8 P0; u16 P1; u64 P2");
            Beh("Dampening", 0x052B1293, 0x170, "kfp XYZMinKFP; kfp XYZMaxKFP; u64 Unused00; i32 ReferenceSpace; u8 EnableAirResistance; u8 P0; u16 P1; u64 P2; u64 P3");
            Beh("MatrixWeight", 0x64E5D702, 0xD0, "kfp MtxWeightKFP; i32 ReferenceSpace; u32 P0; u64 P1");
            Beh("Collision", 0x928A1C45, 0x170, "kfp BouncinessKFP; kfp BounceDirVarKFP; f32 RadiusMult; f32 RestSpeed; i32 CollisionChance; i32 KillChance; u8 DebugDraw; u8 P0; u16 P1; f32 OverrideMinRadius; u64 P2");
            Beh("AnimateTexture", 0xECA84C1E, 0xD0, "kfp AnimRateKFP; i32 KeyframeMode; i32 LastFrameID; i32 LoopMode; u8 IsRandomised; u8 IsScaledOverParticleLife; u8 IsHeldOnLastFrame; u8 DoFrameBlending");
            Beh("Colour", 0x164AEA72, 0x1F0, "kfp RGBAMinKFP; kfp RGBAMaxKFP; kfp EmissiveIntensityKFP; i32 KeyframeMode; u8 RGBAMaxEnable; u8 RGBAProportional; u8 RGBCanTint; u8 P0; u64 P1");
            Beh("Sprite", 0x68FA73F5, 0x70, "v3 AlignAxis; u32 P0; i32 AlignmentMode; f32 FlipChanceU; f32 FlipChanceV; f32 NearClipDist; f32 FarClipDist; f32 ProjectionDepth; f32 ShadowCastIntensity; u8 IsScreenSpace; u8 IsHighRes; u8 NearClip; u8 FarClip; u8 UVClip; u8 DisableDraw; u16 P1; u32 P2; u64 P3");
            Beh("Wind", 0x38B63978, 0xF0, "kfp InfluenceKFP; u64 Unused00; u64 Unused01; f32 HighLodRange; f32 LowLodRange; i32 HighLodDisturbanceMode; i32 LowLodDisturbanceMode; u8 IgnoreMtxWeight; u8 P0; u16 P1; u32 P2; u64 P3");
            Beh("Light", 0x0544C710, 0x550, "kfp RGBMinKFP; kfp RGBMaxKFP; kfp IntensityKFP; kfp RangeKFP; kfp CoronaRGBMinKFP; kfp CoronaRGBMaxKFP; kfp CoronaIntensityKFP; kfp CoronaSizeKFP; kfp CoronaFlareKFP; f32 CoronaZBias; u8 CoronaUseLightColour; u8 ColourFromParticle; u8 ColourPerFrame; u8 IntensityPerFrame; u8 RangePerFrame; u8 CastsShadows; u8 CoronaNotInReflection; u8 CoronaOnlyInReflection; i32 LightType");
            Beh("Model", 0x6232E25A, 0x40, "u32 ColourControlShaderID; f32 CameraShrink; f32 ShadowCastIntensity; u8 DisableDraw; u8 P0; u16 P1");
            Beh("Decal", 0x8F3B6036, 0x180, "kfp DimensionsKFP; kfp AlphaKFP; i32 DecalID; f32 VelocityThreshold; f32 TotalLife; f32 FadeInTime; f32 UVMultStart; f32 UVMultEnd; f32 UVMultTime; f32 DuplicateRejectDist; u8 FlipU; u8 FlipV; u8 ProportionalSize; u8 UseComplexCollision; f32 ProjectionDepth; f32 DistanceScale; u8 IsDirectional; u8 P0; u16 P1");
            Beh("ZCull", 0xA35C721F, 0x170, "kfp HeightKFP; kfp FadeDistKFP; u64 Unused00; i32 CullMode; i32 ReferenceSpace; u64 P0; u64 P1");
            Beh("Noise", 0xB77FED19, 0x280, "kfp PosNoiseMinKFP; kfp PosNoiseMaxKFP; kfp VelNoiseMinKFP; kfp VelNoiseMaxKFP; u32 ReferenceSpace; u8 KeepConstantSpeed; u8 P0; u16 P1; u64 P2");
            Beh("Attractor", 0x25AC9437, 0xC0, "kfp StrengthKFP");
            Beh("Trail", 0xC57377F8, 0xF0, "kfp TexInfoKFP; v3 AlignAxis; u32 P0; i32 AlignmentMode; i32 TessellationU; i32 TessellationV; f32 SmoothnessX; f32 SmoothnessY; f32 ProjectionDepth; f32 ShadowCastIntensity; u8 FlipU; u8 FlipV; u8 WrapTextureOverParticleLife; u8 DisableDraw");
            Beh("FogVolume", 0xA05DA63E, 0x430, "kfp RGBTintMinKFP; kfp RGBTintMaxKFP; kfp DensityRangeKFP; kfp ScaleMinKFP; kfp ScaleMaxKFP; kfp RotationMinKFP; kfp RotationMaxKFP; f32 Falloff; f32 HDRMult; i32 LightingType; u8 ColourTintFromParticle; u8 SortWithParticles; u8 UseGroundFogColour; u8 UseEffectEvoValues");
            Beh("River", 0xD4594BEF, 0x40, "f32 VelocityMult; f32 Influence; u64 P0");
            Beh("DecalPool", 0xA2D6DC3F, 0x50, "f32 VelocityThreshold; i32 LiquidType; i32 DecalID; f32 StartSize; f32 EndSize; f32 GrowthRate; u64 P0");
            Beh("Liquid", 0xDF229542, 0x50, "f32 VelocityThreshold; i32 LiquidType; f32 PoolStartSize; f32 PoolEndSize; f32 PoolGrowthRate; f32 TrailWidthMin; f32 TrailWidthMax; u32 P0");

            Def("SVKItem", 0x20, "f32 U0; f32 U4; u64 U8; f32 U10; u32 U14; u64 U18");
            Def("Var_Vector", 0x40, VarBase + "u32 ShaderVarID; u8 IsKeyframeable; u8 OwnsInfo; u16 P0; u32 U20; u32 U24; u32 U28; u32 U2C; v4 Vector");
            Def("Var_Texture", 0x40, VarBase + "u32 ShaderVarID; u8 IsKeyframeable; u8 OwnsInfo; u16 P0; u32 P1; u32 P2; ptr Texture Texture; str TextureName; h32 TextureNameHash; u8 ExternalReference; u8 P5; u16 P6");
            Def("Var_Keyframe", 0x50, VarBase + "u32 ShaderVarID; u8 IsKeyframeable; u8 OwnsInfo; u16 P0; u64 P1; list Items SVKItem; u64 P2; u64 P3; u64 P4");

            string[] kn = new string[] {
                "ptxu_Acceleration:m_xyzMinKFP", "ptxu_Acceleration:m_xyzMaxKFP", "ptxu_Size:m_whdMinKFP", "ptxu_Size:m_whdMaxKFP", "ptxu_Size:m_tblrScalarKFP",
                "ptxu_Size:m_tblrVelScalarKFP", "ptxu_MatrixWeight:m_mtxWeightKFP", "ptxu_Colour:m_rgbaMinKFP", "ptxu_Colour:m_rgbaMaxKFP", "ptxu_Colour:m_emissiveIntensityKFP",
                "ptxu_Rotation:m_initialAngleMinKFP", "ptxu_Rotation:m_initialAngleMaxKFP", "ptxu_Rotation:m_angleMinKFP", "ptxu_Rotation:m_angleMaxKFP", "ptxu_Collision:m_bouncinessKFP",
                "ptxu_Collision:m_bounceDirVarKFP", "ptxu_AnimateTexture:m_animRateKFP", "ptxu_Dampening:m_xyzMinKFP", "ptxu_Dampening:m_xyzMaxKFP", "ptxu_Wind:m_influenceKFP",
                "ptxu_Decal:m_dimensionsKFP", "ptxu_Decal:m_alphaKFP", "ptxEffectRule:m_colourTintMinKFP", "ptxEffectRule:m_colourTintMaxKFP", "ptxEffectRule:m_zoomScalarKFP",
                "ptxEffectRule:m_dataSphereKFP", "ptxEffectRule:m_dataCapsuleKFP", "ptxEmitterRule:m_spawnRateOverTimeKFP", "ptxEmitterRule:m_spawnRateOverDistKFP", "ptxEmitterRule:m_particleLifeKFP",
                "ptxEmitterRule:m_playbackRateScalarKFP", "ptxEmitterRule:m_speedScalarKFP", "ptxEmitterRule:m_sizeScalarKFP", "ptxEmitterRule:m_accnScalarKFP", "ptxEmitterRule:m_dampeningScalarKFP",
                "ptxEmitterRule:m_matrixWeightScalarKFP", "ptxEmitterRule:m_inheritVelocityKFP", "ptxCreationDomain:m_positionKFP", "ptxCreationDomain:m_rotationKFP", "ptxCreationDomain:m_sizeOuterKFP",
                "ptxCreationDomain:m_sizeInnerKFP", "ptxTargetDomain:m_positionKFP", "ptxTargetDomain:m_rotationKFP", "ptxTargetDomain:m_sizeOuterKFP", "ptxTargetDomain:m_sizeInnerKFP",
                "ptxu_Light:m_rgbMinKFP", "ptxu_Light:m_rgbMaxKFP", "ptxu_Light:m_intensityKFP", "ptxu_Light:m_rangeKFP", "ptxu_Light:m_coronaRgbMinKFP", "ptxu_Light:m_coronaRgbMaxKFP",
                "ptxu_Light:m_coronaIntensityKFP", "ptxu_Light:m_coronaSizeKFP", "ptxu_Light:m_coronaFlareKFP", "ptxu_ZCull:m_heightKFP", "ptxu_ZCull:m_fadeDistKFP",
                "ptxu_Noise:m_posNoiseMinKFP", "ptxu_Noise:m_posNoiseMaxKFP", "ptxu_Noise:m_velNoiseMinKFP", "ptxu_Noise:m_velNoiseMaxKFP", "ptxu_Acceleration:m_strengthKFP",
                "ptxd_Trail:m_texInfoKFP", "ptxu_FogVolume:m_rgbTintMinKFP", "ptxu_FogVolume:m_rgbTintMaxKFP", "ptxu_FogVolume:m_densityRangeKFP", "ptxu_FogVolume:m_scaleMinKFP",
                "ptxu_FogVolume:m_scaleMaxKFP", "ptxu_FogVolume:m_rotationMinKFP", "ptxu_FogVolume:m_rotationMaxKFP", "ptxAttractorDomain:m_positionKFP", "ptxAttractorDomain:m_rotationKFP",
                "ptxAttractorDomain:m_sizeOuterKFP", "ptxAttractorDomain:m_sizeInnerKFP", "ptxu_Attractor:m_strengthKFP"
            };
            foreach (string n in kn) KfpNames[Jenkins.Hash(n)] = n;

            string[] vn = new string[] {
                "DiffuseTex2", "DiffuseTex", "DiffuseTexSampler", "FrameMap", "RefractionMap", "NormalSpecMap", "gSuperAlpha", "gDirectionalMult", "gAmbientMult",
                "gShadowAmount", "gExtraLightMult", "gCameraBias", "gCameraShrink", "gNormalArc", "gDirNormalBias", "gSoftnessCurve", "gSoftnessShadowMult",
                "gSoftnessShadowOffset", "gNormalMapMult", "gAlphaCutoffMinMax", "gRG_BlendStartDistance", "gRG_BlendEndDistance", "RefractionFilter",
                "gRefractionMult", "gBlurAmount", "DirectionalMult", "AmbientMult", "ShadowAmount", "ExtraLightMult", "CameraBias", "CameraShrink", "NormalArc",
                "DirNormalBias", "SoftnessCurve", "SoftnessShadowMult", "SoftnessShadowOffset", "NormalMapMult", "AlphaCutoffMinMax", "RG_BlendStartDistance",
                "RG_BlendEndDistance", "SuperAlpha", "WrapLightingTerm", "gWrapLightingTerm", "gSoftness", "Softness", "gHDRMult", "HDRMult", "gDepthBias", "DepthBias",
                "gNearFadeDist", "gFarFadeDist", "gRefractionStrength", "RefractionStrength", "gNormalScale", "gTextureAnimRate", "gBlendMode", "DiffuseSampler",
                "BumpSampler", "NormalMap", "SpecularMap", "gSpecularIntensity", "gSpecularFalloff", "gBumpiness", "gUVOffset", "gUVScale", "gClipRegion",
                "gChannelMask", "gBackLighting", "gFogMult", "gNaturalAmbientMult", "gArtificialAmbientMult", "gInteriorAmbientMult", "gEmissiveMult",
                "gDirectionalZOffsetMinRange", "gAlphaCutoff", "gRefractionMapMult", "gWaterFogMult", "gColourTint", "NoiseTexture", "NoiseTexSampler"
            };
            foreach (string n in vn) VarNames[Jenkins.Hash(n)] = n;
        }

        public static string KfpName(uint h)
        {
            string s;
            if (KfpNames.TryGetValue(h, out s)) return s;
            return "0x" + h.ToString("x8");
        }

        public static string VarName(uint h)
        {
            string s;
            if (VarNames.TryGetValue(h, out s)) return s;
            return "0x" + h.ToString("x8");
        }
    }

    public class Ref
    {
        public int At;
        public Node To;
        public int Add;
    }

    public class Node
    {
        public string Kind;
        public long Off = -1;
        public byte[] Data;
        public bool Gfx;
        public List<Ref> Refs = new List<Ref>();
        public long NewOff = -1;
        public string Label;
        public int ElemCount;
        public HashSet<int> HashAts;

        public Node(string kind, int size)
        {
            Kind = kind;
            Data = new byte[size];
        }

        public uint U32(int o) { return BitConverter.ToUInt32(Data, o); }
        public int I32(int o) { return BitConverter.ToInt32(Data, o); }
        public ushort U16(int o) { return BitConverter.ToUInt16(Data, o); }
        public ulong U64(int o) { return BitConverter.ToUInt64(Data, o); }
        public float F32(int o) { return BitConverter.ToSingle(Data, o); }
        public void W32(int o, uint v) { Buffer.BlockCopy(BitConverter.GetBytes(v), 0, Data, o, 4); }
        public void W16(int o, ushort v) { Buffer.BlockCopy(BitConverter.GetBytes(v), 0, Data, o, 2); }
        public void W64(int o, ulong v) { Buffer.BlockCopy(BitConverter.GetBytes(v), 0, Data, o, 8); }
        public void WF(int o, float v) { Buffer.BlockCopy(BitConverter.GetBytes(v), 0, Data, o, 4); }

        public Node Target(int at)
        {
            for (int i = 0; i < Refs.Count; i++) if (Refs[i].At == at) return Refs[i].To;
            return null;
        }

        public void SetRef(int at, Node to, int add)
        {
            for (int i = Refs.Count - 1; i >= 0; i--) if (Refs[i].At == at) Refs.RemoveAt(i);
            W64(at, 0);
            if (to == null) return;
            Ref r = new Ref();
            r.At = at;
            r.To = to;
            r.Add = add;
            Refs.Add(r);
        }

        public string Str()
        {
            int e = 0;
            while (e < Data.Length && Data[e] != 0) e++;
            return Encoding.ASCII.GetString(Data, 0, e);
        }

        public static Node MakeString(string s)
        {
            byte[] b = Encoding.ASCII.GetBytes(s);
            Node n = new Node("String", b.Length + 1);
            Buffer.BlockCopy(b, 0, n.Data, 0, b.Length);
            n.Label = s;
            return n;
        }
    }

    public class YptFile
    {
        public string Path;
        public Rsc R;
        public Node Root;
        public List<Node> Nodes = new List<Node>();
        public List<string> Warnings = new List<string>();
        public bool HasOpaque;
        public int Overlaps, Stray, Trimmed;
        public long UnparsedNonZero;
        Dictionary<long, Node> byOff = new Dictionary<long, Node>();
        Dictionary<long, Node> byGfx = new Dictionary<long, Node>();
        List<object[]> deferred = new List<object[]>();

        const ulong VBase = 0x50000000UL;
        const ulong PBase = 0x60000000UL;

        public static YptFile Parse(string path)
        {
            YptFile y = new YptFile();
            y.Path = path;
            y.R = Rsc.Load(path);
            if (y.R.Version != 68) throw new InvalidDataException("not a particle resource (RSC7 version " + y.R.Version + ")");
            y.Root = y.Struct("Root", 0);
            y.TrimPointerArrays();
            y.ResolveDeferred();
            return y;
        }

        void Warn(string s)
        {
            if (Warnings.Count < 200) Warnings.Add(s);
        }

        long SysOff(ulong p)
        {
            if (p == 0) return -1;
            if ((p >> 28) == 5 && (long)(p - VBase) < R.Sys.Length) return (long)(p - VBase);
            return -2;
        }

        ulong RawU64(long off) { return BitConverter.ToUInt64(R.Sys, (int)off); }

        Node NewNode(string kind, long off, int size)
        {
            if (off < 0 || off + size > R.Sys.Length)
            {
                Warn(kind + " at 0x" + off.ToString("x") + " size 0x" + size.ToString("x") + " runs past the system segment");
                size = (int)Math.Max(0, Math.Min(size, R.Sys.Length - off));
            }
            Node n = new Node(kind, size);
            n.Off = off;
            Buffer.BlockCopy(R.Sys, (int)off, n.Data, 0, size);
            byOff[off] = n;
            Nodes.Add(n);
            return n;
        }

        string ResolveKind(string kind, long off)
        {
            if (kind == "Behaviour")
            {
                uint h = BitConverter.ToUInt32(R.Sys, (int)off + 8);
                string nm;
                if (!Schema.BehaviourByHash.TryGetValue(h, out nm)) { Warn("unknown behaviour type 0x" + h.ToString("x8") + " at 0x" + off.ToString("x")); return null; }
                return "Beh_" + nm;
            }
            if (kind == "ShaderVar")
            {
                byte t = R.Sys[off + 0x14];
                if (t == 2 || t == 4) return "Var_Vector";
                if (t == 6) return "Var_Texture";
                if (t == 7) return "Var_Keyframe";
                Warn("unknown shader var type " + t + " at 0x" + off.ToString("x"));
                return null;
            }
            if (kind == "DictAuto")
            {
                long items = SysOff(RawU64(off + 0x30));
                int count = BitConverter.ToUInt16(R.Sys, (int)off + 0x38);
                if (items >= 0 && count > 0)
                {
                    long first = SysOff(RawU64(items));
                    if (first >= 0 && RawU64(first + 0x28) == VBase) return "Dict_EffectRule";
                    return "Dict_EmitterRule";
                }
                return null;
            }
            return kind;
        }

        public Node Struct(string kind, long off)
        {
            Node ex;
            if (byOff.TryGetValue(off, out ex)) return ex;
            string k = ResolveKind(kind, off);
            if (k == null)
            {
                if (kind == "DictAuto") k = "Dict_Empty";
                else return null;
            }
            if (k == "Dict_Empty")
            {
                Node e = NewNode("Dict_Empty", off, 0x40);
                return e;
            }
            if (k == "Opaque")
            {
                HasOpaque = true;
                Node o = NewNode("Opaque", off, 0);
                return o;
            }
            StructDef d = Schema.Defs[k];
            Node n = NewNode(k, off, d.Size);
            Walk(n, 0, d);
            if (k == "Texture") n.Label = n.Target(0x28) != null ? n.Target(0x28).Str() : null;
            return n;
        }

        Node StringAt(long off)
        {
            Node ex;
            if (byOff.TryGetValue(off, out ex)) return ex;
            long e = off;
            while (e < R.Sys.Length && R.Sys[e] != 0) e++;
            Node n = NewNode("String", off, (int)(e - off) + 1);
            n.Label = n.Str();
            return n;
        }

        void AddRef(Node n, int at, Node to, int add)
        {
            if (to == null) return;
            Ref r = new Ref();
            r.At = at;
            r.To = to;
            r.Add = add;
            n.Refs.Add(r);
        }

        void Walk(Node n, int b, StructDef d)
        {
            foreach (Field f in d.Fields)
            {
                int at = b + f.Off;
                if (at + f.Size > n.Data.Length) return;
                switch (f.Type)
                {
                    case "h32":
                    case "rgba":
                        if (n.HashAts == null) n.HashAts = new HashSet<int>();
                        n.HashAts.Add(at & ~7);
                        break;
                    case "str":
                    {
                        ulong p = n.U64(at);
                        long o = SysOff(p);
                        if (o >= 0) AddRef(n, at, StringAt(o), 0);
                        else if (o == -2) Warn(d.Name + "." + f.Name + " bad string pointer 0x" + p.ToString("x"));
                        break;
                    }
                    case "ptr":
                    {
                        ulong p = n.U64(at);
                        long o = SysOff(p);
                        if (o >= 0) AddRef(n, at, Struct(f.Arg, o), 0);
                        else if (o == -2) Warn(d.Name + "." + f.Name + " bad pointer 0x" + p.ToString("x"));
                        break;
                    }
                    case "iptr":
                    {
                        ulong p = n.U64(at);
                        if (p != 0) deferred.Add(new object[] { n, at, p });
                        break;
                    }
                    case "gptr":
                    {
                        ulong p = n.U64(at);
                        if (p == 0) break;
                        if ((p >> 28) != 6) { Warn(d.Name + "." + f.Name + " is not a graphics pointer 0x" + p.ToString("x")); break; }
                        long go = (long)(p - PBase);
                        Node g;
                        if (!byGfx.TryGetValue(go, out g))
                        {
                            int size = TexDataSize(n, b);
                            if (go + size > R.Gfx.Length)
                            {
                                Warn("texture data at 0x" + go.ToString("x") + " size 0x" + size.ToString("x") + " runs past the graphics segment");
                                size = (int)Math.Max(0, R.Gfx.Length - go);
                            }
                            g = new Node("TexData", size);
                            g.Gfx = true;
                            g.Off = go;
                            Buffer.BlockCopy(R.Gfx, (int)go, g.Data, 0, size);
                            byGfx[go] = g;
                            Nodes.Add(g);
                        }
                        AddRef(n, at, g, 0);
                        break;
                    }
                    case "kfp":
                        Walk(n, at, Schema.Defs["KFP"]);
                        break;
                    case "sub":
                        Walk(n, at, Schema.Defs[f.Arg]);
                        break;
                    case "list":
                    {
                        long o = SysOff(n.U64(at));
                        int count = n.U16(at + 8);
                        int cap = n.U16(at + 10);
                        if (o < 0) break;
                        StructDef ed = Schema.Defs[f.Arg];
                        Node a;
                        if (!byOff.TryGetValue(o, out a))
                        {
                            a = NewNode("Array_" + f.Arg, o, Math.Max(count, cap) * ed.Size);
                            a.ElemCount = count;
                            for (int i = 0; i < count; i++) Walk(a, i * ed.Size, ed);
                        }
                        AddRef(n, at, a, 0);
                        break;
                    }
                    case "hlist":
                    {
                        long o = SysOff(n.U64(at));
                        int count = n.U16(at + 8);
                        int cap = n.U16(at + 10);
                        if (o < 0) break;
                        Node a;
                        if (!byOff.TryGetValue(o, out a))
                        {
                            a = NewNode("HashArray", o, Math.Max(count, cap) * 4);
                            a.ElemCount = count;
                        }
                        AddRef(n, at, a, 0);
                        break;
                    }
                    case "plist":
                    case "kplist":
                    {
                        long o = SysOff(n.U64(at));
                        int count = n.U16(at + 8);
                        int cap = n.U16(at + 10);
                        if (o < 0) break;
                        Node a;
                        if (!byOff.TryGetValue(o, out a))
                        {
                            a = NewNode("PtrArray", o, Math.Max(count, cap) * 8);
                            a.ElemCount = count;
                            for (int i = 0; i < count; i++)
                            {
                                ulong p = a.U64(i * 8);
                                if (p == 0) continue;
                                if (f.Type == "kplist") { deferred.Add(new object[] { a, i * 8, p }); continue; }
                                long t = SysOff(p);
                                if (t >= 0) AddRef(a, i * 8, Struct(f.Arg, t), 0);
                                else Warn(d.Name + "." + f.Name + "[" + i + "] bad pointer 0x" + p.ToString("x"));
                            }
                        }
                        AddRef(n, at, a, 0);
                        break;
                    }
                }
            }
        }

        public static int TexDataSize(Node tex, int b)
        {
            int w = tex.U16(b + 0x50), h = tex.U16(b + 0x52), levels = tex.Data[b + 0x5D];
            uint fmt = tex.U32(b + 0x58);
            int total = 0;
            if (levels < 1) levels = 1;
            for (int i = 0; i < levels; i++)
            {
                int mw = Math.Max(1, w >> i), mh = Math.Max(1, h >> i);
                total += MipSize(fmt, mw, mh);
            }
            return total;
        }

        public static int MipSize(uint fmt, int w, int h)
        {
            int bw = Math.Max(1, (w + 3) / 4), bh = Math.Max(1, (h + 3) / 4);
            switch (fmt)
            {
                case 0x31545844: case 0x31495441: return bw * bh * 8;
                case 0x33545844: case 0x35545844: case 0x32495441: case 0x20374342: return bw * bh * 16;
                case 21: case 22: case 32: case 33: return w * h * 4;
                case 50: case 28: return w * h;
                case 51: case 25: case 26: case 23: return w * h * 2;
            }
            return w * h * 4;
        }

        public static string FormatName(uint f)
        {
            switch (f)
            {
                case 0x31545844: return "DXT1";
                case 0x33545844: return "DXT3";
                case 0x35545844: return "DXT5";
                case 0x32495441: return "ATI2";
                case 0x31495441: return "ATI1";
                case 0x20374342: return "BC7";
                case 21: return "A8R8G8B8";
                case 22: return "X8R8G8B8";
                case 32: return "A8B8G8R8";
                case 50: return "L8";
                case 28: return "A8";
                case 51: return "A8L8";
            }
            return "fmt" + f;
        }

        void TrimPointerArrays()
        {
            List<Node> sys = new List<Node>();
            foreach (Node n in Nodes) if (!n.Gfx && n.Data.Length > 0) sys.Add(n);
            sys.Sort(delegate (Node a, Node c) { return a.Off.CompareTo(c.Off); });
            for (int i = 0; i + 1 < sys.Count; i++)
            {
                Node n = sys[i];
                if (n.Kind != "PtrArray" && n.Kind != "HashArray") continue;
                long end = n.Off + n.Data.Length;
                long next = sys[i + 1].Off;
                if (next >= end) continue;
                int unit = n.Kind == "PtrArray" ? 8 : 4;
                int keep = (int)Math.Max(n.ElemCount * unit, ((next - n.Off) / unit) * unit);
                if (keep >= n.Data.Length) continue;
                byte[] d = new byte[keep];
                Buffer.BlockCopy(n.Data, 0, d, 0, keep);
                n.Data = d;
                Trimmed++;
            }
        }

        void ResolveDeferred()
        {
            List<Node> sys = new List<Node>();
            foreach (Node n in Nodes) if (!n.Gfx && n.Data.Length > 0) sys.Add(n);
            sys.Sort(delegate (Node a, Node c) { return a.Off.CompareTo(c.Off); });
            long[] starts = new long[sys.Count];
            for (int i = 0; i < sys.Count; i++) starts[i] = sys[i].Off;
            foreach (object[] d in deferred)
            {
                Node n = (Node)d[0];
                int at = (int)d[1];
                ulong p = (ulong)d[2];
                long o = SysOff(p);
                if (o < 0) { Warn("interior pointer 0x" + p.ToString("x") + " is outside the system segment"); continue; }
                int idx = Array.BinarySearch(starts, o);
                if (idx < 0) idx = ~idx - 1;
                if (idx < 0 || o >= sys[idx].Off + sys[idx].Data.Length) { Warn("interior pointer 0x" + p.ToString("x") + " (from " + n.Kind + ") hits no parsed block"); continue; }
                AddRef(n, at, sys[idx], (int)(o - sys[idx].Off));
            }
            deferred.Clear();
        }

        public string Census()
        {
            StringBuilder sb = new StringBuilder();
            List<Node> sys = new List<Node>();
            foreach (Node n in Nodes) if (!n.Gfx && n.Data.Length > 0) sys.Add(n);
            sys.Sort(delegate (Node a, Node c) { return a.Off.CompareTo(c.Off); });
            int overlaps = 0, stray = 0;
            long covered = 0, uncoveredNonZero = 0;
            long pos = 0;
            List<string> gaps = new List<string>();
            for (int i = 0; i <= sys.Count; i++)
            {
                long start = i < sys.Count ? sys[i].Off : R.Sys.Length;
                if (start < pos)
                {
                    overlaps++;
                    if (overlaps <= 5) sb.AppendLine("OVERLAP " + sys[i].Kind + " at 0x" + start.ToString("x") + " begins before 0x" + pos.ToString("x") + " (previous " + sys[i - 1].Kind + ")");
                }
                else if (start > pos)
                {
                    long nz = 0, first = -1;
                    for (long q = pos; q < start; q++) if (R.Sys[q] != 0) { nz++; if (first < 0) first = q; }
                    if (nz > 0)
                    {
                        uncoveredNonZero += nz;
                        if (gaps.Count < 8) gaps.Add("0x" + first.ToString("x") + " (" + nz + " bytes, after " + (i > 0 ? sys[i - 1].Kind : "start") + ")");
                    }
                }
                if (i < sys.Count)
                {
                    covered += sys[i].Data.Length;
                    pos = Math.Max(pos, start + sys[i].Data.Length);
                }
            }
            foreach (Node n in sys)
            {
                HashSet<int> known = new HashSet<int>();
                foreach (Ref r in n.Refs) known.Add(r.At);
                if (n.Kind == "String" || n.Kind == "HashArray") continue;
                for (int o = 0; o + 8 <= n.Data.Length; o += 8)
                {
                    if (known.Contains(o)) continue;
                    if (n.HashAts != null && n.HashAts.Contains(o)) continue;
                    ulong v = n.U64(o);
                    if (v == 0) continue;
                    bool looks = ((v >> 28) == 5 && (long)(v - VBase) < R.Sys.Length) || ((v >> 28) == 6 && (long)(v - PBase) < R.Gfx.Length);
                    if (!looks) continue;
                    stray++;
                    if (stray <= 8) sb.AppendLine("STRAY pointer 0x" + v.ToString("x") + " in " + n.Kind + "+0x" + o.ToString("x") + " (block at 0x" + n.Off.ToString("x") + ")");
                }
            }
            Overlaps = overlaps;
            Stray = stray;
            UnparsedNonZero = uncoveredNonZero;
            foreach (string g in gaps) sb.AppendLine("UNPARSED data at " + g);
            foreach (string w in Warnings) sb.AppendLine("WARN " + w);
            sb.AppendLine("census blocks=" + Nodes.Count + " covered=" + covered + " unparsedNonZero=" + uncoveredNonZero + " overlaps=" + overlaps + " strayPointers=" + stray + " warnings=" + Warnings.Count + " opaque=" + (HasOpaque ? 1 : 0));
            return sb.ToString();
        }

        public string Status()
        {
            Census();
            if (Overlaps > 0 || Stray > 0 || Warnings.Count > 0) return "issues";
            if (HasOpaque) return "models";
            if (UnparsedNonZero > 0) return "orphans";
            return "clean";
        }

        public bool Clean()
        {
            string s = Status();
            return s == "clean" || s == "orphans";
        }
    }

    public static class YptWriter
    {
        public static List<Node> Reachable(Node root)
        {
            List<Node> order = new List<Node>();
            HashSet<Node> seen = new HashSet<Node>();
            Stack<Node> st = new Stack<Node>();
            st.Push(root);
            seen.Add(root);
            while (st.Count > 0)
            {
                Node n = st.Pop();
                order.Add(n);
                for (int i = n.Refs.Count - 1; i >= 0; i--)
                {
                    Node t = n.Refs[i].To;
                    if (t != null && seen.Add(t)) st.Push(t);
                }
            }
            return order;
        }

        static long Layout(List<Node> nodes, long minPage, out uint flags, out int pages)
        {
            flags = 0;
            pages = 0;
            if (nodes.Count == 0) return 0;
            long page = minPage;
            foreach (Node n in nodes) while (page < n.Data.Length) page *= 2;
            while (true)
            {
                long pos = 0;
                foreach (Node n in nodes)
                {
                    long size = (n.Data.Length + 15) & ~15L;
                    if (n.Kind == "PageMap") size += 0x1010;
                    if (size == 0) size = 16;
                    long room = page - (pos % page);
                    if (size > room) pos += room;
                    n.NewOff = pos;
                    pos += size;
                }
                long count = (pos + page - 1) / page;
                if (count <= 127)
                {
                    long baseSize = page >> 4;
                    int shift = 0;
                    while ((0x200L << shift) < baseSize) shift++;
                    flags = (uint)shift | ((uint)count << 17);
                    pages = (int)count;
                    return count * page;
                }
                page *= 2;
            }
        }

        public static Rsc Build(Node root)
        {
            List<Node> all = Reachable(root);
            List<Node> sys = new List<Node>();
            List<Node> gfx = new List<Node>();
            foreach (Node n in all)
            {
                if (n.Kind == "Opaque") throw new InvalidOperationException("this graph still references a model drawable, which the writer cannot relocate");
                if (n.Gfx) gfx.Add(n); else sys.Add(n);
            }
            uint sf, gf;
            int sp, gp;
            long sysSize = Layout(sys, 0x2000, out sf, out sp);
            long gfxSize = Layout(gfx, 0x2000, out gf, out gp);
            Rsc r = new Rsc();
            r.Version = 68;
            r.SysFlags = sf | 0x40000000u;
            r.GfxFlags = gf | 0x40000000u;
            r.Sys = new byte[sysSize];
            r.Gfx = new byte[gfxSize];
            foreach (Node n in all)
            {
                byte[] dst = n.Gfx ? r.Gfx : r.Sys;
                byte[] data = (byte[])n.Data.Clone();
                foreach (Ref rf in n.Refs)
                {
                    ulong v = (rf.To.Gfx ? 0x60000000UL : 0x50000000UL) + (ulong)rf.To.NewOff + (ulong)rf.Add;
                    Buffer.BlockCopy(BitConverter.GetBytes(v), 0, data, rf.At, 8);
                }
                if (n.Kind == "PageMap")
                {
                    data[8] = (byte)sp;
                    data[9] = (byte)gp;
                }
                Buffer.BlockCopy(data, 0, dst, (int)n.NewOff, data.Length);
            }
            return r;
        }
    }
}
