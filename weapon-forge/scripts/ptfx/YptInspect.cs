using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace WeaponForge
{
    public static class YptInspect
    {
        static readonly Regex Noise = new Regex("^(P\\d+|U[0-9A-F]+|VFT\\d?|Pad\\d+|Unused\\d+|RefCount|FileVersion|UIData|Evolved|InvertBiasLink|RandomIndex|Release\\d|Func\\d|PointPool|ShaderTemplate|ShaderTemplateTechniqueID|ShaderTemplateHashName|IsDataInSync|RuntimeFlags|LastEvoList|NumActiveInstances|Index|Type|Unused)$");

        static string Num(object o)
        {
            if (o is float) return Json.FloatStr((float)o);
            if (o is double) return Json.Write(o, false);
            return Convert.ToString(o, CultureInfo.InvariantCulture);
        }

        static string Keys(object v)
        {
            JObj j = v as JObj;
            List<object> keys = j != null ? j.Arr("keys") : v as List<object>;
            if (keys == null || keys.Count == 0) return null;
            StringBuilder sb = new StringBuilder();
            foreach (object ko in keys)
            {
                List<object> k = (List<object>)ko;
                int vo = k.Count >= 8 ? 4 : 1;
                int last = k.Count - 1;
                while (last > vo && DefaultsBuilder.IsZero(k[last])) last--;
                if (sb.Length > 0) sb.Append("  ");
                if (keys.Count > 1 || Json.ToDouble(k[0]) != 0) sb.Append(Num(k[0])).Append(':');
                sb.Append('(');
                for (int i = vo; i <= last; i++) { if (i > vo) sb.Append(','); sb.Append(Num(k[i])); }
                sb.Append(')');
            }
            return sb.ToString();
        }

        static bool IsKfp(string name) { return name.EndsWith("KFP"); }

        static string Scalars(JObj o, params string[] skip)
        {
            StringBuilder sb = new StringBuilder();
            foreach (KeyValuePair<string, object> kv in o.Items)
            {
                if (IsKfp(kv.Key) || kv.Value is JObj || Noise.IsMatch(kv.Key) || Array.IndexOf(skip, kv.Key) >= 0 || kv.Key.Contains("#")) continue;
                if (kv.Key == "id" || kv.Key == "type" || kv.Key == "kind" || kv.Key == "Name") continue;
                if (kv.Value is List<object>)
                {
                    List<object> l = (List<object>)kv.Value;
                    if (l.Count == 0 || l[0] is JObj || l[0] is List<object> || l.Count > 4) continue;
                    if (DefaultsBuilder.IsZero(l)) continue;
                    sb.Append(' ').Append(kv.Key).Append("=(");
                    for (int i = 0; i < l.Count; i++) { if (i > 0) sb.Append(','); sb.Append(Num(l[i])); }
                    sb.Append(')');
                    continue;
                }
                if (DefaultsBuilder.IsZero(kv.Value)) continue;
                sb.Append(' ').Append(kv.Key).Append('=').Append(Num(kv.Value));
            }
            return sb.ToString();
        }

        static void KfpLines(StringBuilder sb, JObj o, string indent)
        {
            foreach (KeyValuePair<string, object> kv in o.Items)
            {
                if (!IsKfp(kv.Key)) continue;
                string k = Keys(kv.Value);
                if (k == null) continue;
                sb.Append(indent).Append(kv.Key.Substring(0, kv.Key.Length - 3)).Append(": ").AppendLine(k);
            }
        }

        static void Domain(StringBuilder sb, JObj em, string field, string label)
        {
            JObj d = em.Obj(field);
            if (d == null) return;
            string[] types = new string[] { "box", "sphere", "cylinder", "attractor" };
            int t = (int)d.Num("DomainType", 0);
            sb.Append("    ").Append(label).Append(' ').Append(t < types.Length ? types[t] : "type" + t).AppendLine(Scalars(d, "DomainType"));
            KfpLines(sb, d, "      ");
        }

        static void Evolutions(StringBuilder sb, JObj owner, string indent)
        {
            JObj ev = owner.Obj("EvolutionList");
            if (ev == null) return;
            List<object> names = ev.Arr("Evolutions");
            if (names == null || names.Count == 0) return;
            sb.Append(indent).Append("evolutions:");
            foreach (object n in names) sb.Append(' ').Append(((JObj)n).Str("Name"));
            List<object> props = ev.Arr("EvolvedKeyframeProps");
            if (props != null && props.Count > 0)
            {
                sb.Append("  drives:");
                foreach (object p in props)
                {
                    string nm = ((JObj)p).Str("Name") ?? "?";
                    int c = nm.IndexOf(":m_");
                    sb.Append(' ').Append(c >= 0 ? nm.Substring(c + 3) : nm);
                }
            }
            sb.AppendLine();
        }

        public static string Describe(YptFile y)
        {
            Decompiler dc = new Decompiler(y, null);
            dc.Full = true;
            return Describe(dc.Run(), y);
        }

        public static string Describe(JObj spec, YptFile y)
        {
            StringBuilder sb = new StringBuilder();
            List<object> tex = spec.Arr("textures") ?? new List<object>();
            List<object> effs = spec.Arr("effects") ?? new List<object>();
            List<object> emits = spec.Arr("emitters") ?? new List<object>();
            List<object> ptxs = spec.Arr("particles") ?? new List<object>();
            sb.Append("DICT ").Append(spec.Str("name")).Append("  textures=").Append(tex.Count).Append(" effects=").Append(effs.Count).Append(" emitters=").Append(emits.Count).Append(" particles=").Append(ptxs.Count);
            if (spec.Has("drawables")) sb.Append(" models=").Append(spec.Arr("drawables").Count);
            if (y != null) sb.Append("  sys=").Append(Rsc.DescribeFlags(y.R.SysFlags)).Append(" gfx=").Append(Rsc.DescribeFlags(y.R.GfxFlags));
            sb.AppendLine();
            foreach (object o in tex)
            {
                JObj t = (JObj)o;
                sb.Append("TEX ").Append(t.Str("name")).Append(' ').Append(Num(t.Get("width"))).Append('x').Append(Num(t.Get("height"))).Append(' ').Append(t.Str("format")).Append(" mips=").AppendLine(Num(t.Get("levels")));
            }
            foreach (object o in effs)
            {
                JObj e = (JObj)o;
                List<object> evs = e.Arr("EventEmitters") ?? new List<object>();
                sb.Append("EFFECT ").Append(e.Str("Name")).Append("  events=").Append(evs.Count).AppendLine(Scalars(e, "EffectList", "EventEmitters"));
                KfpLines(sb, e, "    ");
                Evolutions(sb, e, "    ");
                int i = 0;
                foreach (object eo in evs)
                {
                    JObj ev = eo as JObj;
                    if (ev == null) { i++; continue; }
                    sb.Append("  EVENT ").Append(i++).Append("  emitter=").Append(ev.Str("EmitterRule") ?? ev.Str("EmitterRuleName")).Append("  particle=").Append(ev.Str("ParticleRule") ?? ev.Str("ParticleRuleName"));
                    sb.AppendLine(Scalars(ev, "EmitterRule", "ParticleRule", "EmitterRuleName", "ParticleRuleName"));
                    Evolutions(sb, ev, "      ");
                }
            }
            foreach (object o in emits)
            {
                JObj e = (JObj)o;
                sb.Append("EMITTER ").Append(e.Str("Name")).AppendLine(Scalars(e));
                Domain(sb, e, "CreationDomain", "creation");
                Domain(sb, e, "TargetDomain", "target");
                Domain(sb, e, "AttractorDomain", "attractor");
                KfpLines(sb, e, "    ");
            }
            foreach (object o in ptxs)
            {
                JObj p = (JObj)o;
                sb.Append("PARTICLE ").Append(p.Str("Name")).Append("  ").Append(p.Str("ShaderTemplateName")).Append('/').Append(p.Str("ShaderTemplateTechniqueName"));
                string texName = null;
                List<object> vars = p.Arr("ShaderVars") ?? new List<object>();
                foreach (object vo in vars)
                {
                    JObj v = (JObj)vo;
                    if (v.Str("kind") != "Texture" || string.IsNullOrEmpty(v.Str("TextureName"))) continue;
                    texName = (texName == null ? "" : texName + ",") + v.Str("TextureName") + (v.Num("ExternalReference", 0) != 0 ? "(external)" : "");
                }
                if (texName != null) sb.Append(" tex=").Append(texName);
                sb.AppendLine(Scalars(p, "ShaderTemplateName", "ShaderTemplateTechniqueName", "InitBehaviours", "UpdateBehaviours", "UpdateFinalizeBehaviours", "DrawBehaviours"));
                foreach (string sp in new string[] { "EffectSpawnerAtRatio", "EffectSpawnerOnCollision" })
                {
                    JObj s = p.Obj(sp);
                    if (s == null || string.IsNullOrEmpty(s.Str("EffectRuleName"))) continue;
                    sb.Append("    ").Append(sp).Append(" -> ").Append(s.Str("EffectRuleName")).AppendLine(Scalars(s, "EffectRuleName", "EffectRule"));
                }
                List<object> dr = p.Arr("Drawables");
                if (dr != null && dr.Count > 0)
                {
                    sb.Append("    models:");
                    foreach (object d in dr) sb.Append(' ').Append(((JObj)d).Str("Name"));
                    sb.AppendLine();
                }
                StringBuilder vs = new StringBuilder();
                foreach (object vo in vars)
                {
                    JObj v = (JObj)vo;
                    if (v.Str("kind") == "Vector")
                    {
                        List<object> vec = v.Arr("Vector");
                        if (vec == null || DefaultsBuilder.IsZero(vec)) continue;
                        int last = vec.Count - 1;
                        while (last > 0 && DefaultsBuilder.IsZero(vec[last])) last--;
                        vs.Append(' ').Append(v.Str("Name")).Append('=');
                        for (int i = 0; i <= last; i++) { if (i > 0) vs.Append(','); vs.Append(Num(vec[i])); }
                    }
                    else if (v.Str("kind") == "Keyframe")
                    {
                        List<object> items = v.Arr("Items");
                        if (items == null || items.Count == 0) continue;
                        vs.Append(' ').Append(v.Str("Name")).Append('=');
                        for (int i = 0; i < items.Count; i++)
                        {
                            JObj it = (JObj)items[i];
                            if (i > 0) vs.Append('/');
                            if (items.Count > 1) vs.Append(Num(it.Get("U0"))).Append(':');
                            vs.Append(Num(it.Get("U10")));
                        }
                    }
                }
                if (vs.Length > 0) sb.Append("    vars:").AppendLine(vs.ToString());
                foreach (object bo in p.Arr("AllBehaviours") ?? new List<object>())
                {
                    JObj b = bo as JObj;
                    if (b == null) continue;
                    sb.Append("    ").Append(b.Str("type")).AppendLine(Scalars(b, "KeyframeProps"));
                    KfpLines(sb, b, "      ");
                }
                List<object> bias = p.Arr("BiasLinks");
                if (bias != null && bias.Count > 0)
                {
                    sb.Append("    biasLinks:");
                    foreach (object b in bias) sb.Append(' ').Append(((JObj)b).Str("Name"));
                    sb.AppendLine();
                }
            }
            return sb.ToString();
        }

        public static string OneLine(YptFile y)
        {
            Decompiler dc = new Decompiler(y, null);
            dc.Full = true;
            JObj spec = dc.Run();
            StringBuilder sb = new StringBuilder();
            foreach (object o in spec.Arr("effects") ?? new List<object>())
            {
                JObj e = (JObj)o;
                if (sb.Length > 0) sb.Append(' ');
                sb.Append(e.Str("Name")).Append('[').Append((e.Arr("EventEmitters") ?? new List<object>()).Count).Append(e.Num("NumLoops", 0) != 0 ? "L" : "").Append(']');
            }
            return sb.ToString();
        }
    }
}
