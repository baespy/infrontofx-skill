using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace WeaponForge
{
    public class YptStats
    {
        Dictionary<string, Dictionary<string, int>> counts = new Dictionary<string, Dictionary<string, int>>();
        Dictionary<string, List<float>> samples = new Dictionary<string, List<float>>();
        Dictionary<string, int[]> tex = new Dictionary<string, int[]>(StringComparer.OrdinalIgnoreCase);
        Dictionary<string, string> texInfo = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public List<string> FileLines = new List<string>();
        public int Files, Effects, Looped, Emitters, Particles, WithModels;

        void Count(string group, string value)
        {
            Dictionary<string, int> g;
            if (!counts.TryGetValue(group, out g)) { g = new Dictionary<string, int>(); counts[group] = g; }
            int c;
            g.TryGetValue(value, out c);
            g[value] = c + 1;
        }

        void Sample(string group, double v)
        {
            List<float> l;
            if (!samples.TryGetValue(group, out l)) { l = new List<float>(); samples[group] = l; }
            l.Add((float)v);
        }

        static List<object> KeysOf(object v)
        {
            JObj j = v as JObj;
            return j != null ? j.Arr("keys") : v as List<object>;
        }

        static double KeyVal(List<object> key, int comp)
        {
            int vo = key.Count >= 8 ? 4 : 1;
            return vo + comp < key.Count ? Json.ToDouble(key[vo + comp]) : 0;
        }

        void SampleKfp(string group, JObj owner, string field, int comps)
        {
            List<object> keys = KeysOf(owner.Get(field));
            if (keys == null || keys.Count == 0) { Count("kfp-empty", group); return; }
            Count("kfp-keycount " + group, keys.Count > 4 ? "5+" : keys.Count.ToString());
            double peak = 0;
            foreach (object k in keys) for (int c = 0; c < comps; c++) peak = Math.Max(peak, Math.Abs(KeyVal((List<object>)k, c)));
            Sample(group + " peak", peak);
        }

        public void Add(YptFile y, string label)
        {
            Decompiler dc = new Decompiler(y, null);
            dc.Full = true;
            JObj spec = dc.Run();
            Files++;
            if (y.HasOpaque) WithModels++;
            StringBuilder line = new StringBuilder();
            line.Append(label).Append(" | ");
            foreach (object o in spec.Arr("textures") ?? new List<object>())
            {
                JObj t = (JObj)o;
                texInfo[t.Str("name")] = t.Num("width", 0) + "x" + t.Num("height", 0) + " " + t.Str("format");
            }
            bool first = true;
            foreach (object o in spec.Arr("effects") ?? new List<object>())
            {
                JObj e = (JObj)o;
                Effects++;
                List<object> evs = e.Arr("EventEmitters") ?? new List<object>();
                bool loop = e.Num("NumLoops", 0) != 0;
                if (loop) Looped++;
                Count("effect NumLoops", Json.Write(e.Get("NumLoops"), false));
                Count("effect events", evs.Count > 12 ? "13+" : evs.Count.ToString());
                Sample("effect DurationMax" + (loop ? " (looped)" : " (one-shot)"), e.Num("DurationMax", 0));
                Sample("effect DistanceCullingCullDist", e.Num("DistanceCullingCullDist", 0));
                foreach (string f in new string[] { "DrawListID", "IsShortLived", "HasNoShadows", "ViewportCullingMode", "DistanceCullingMode", "CollisionType", "GameFlags", "ColourTintMaxEnable", "UseDataVolume", "SortEventsByDistance" })
                    Count("effect " + f, Json.Write(e.Get(f), false));
                SampleKfp("effect ZoomScalar", e, "ZoomScalarKFP", 2);
                foreach (object eo in evs)
                {
                    JObj ev = eo as JObj;
                    if (ev == null) continue;
                    Count("event EventType", Json.Write(ev.Get("EventType"), false));
                    Sample("event StartRatio", ev.Num("StartRatio", 0));
                    Sample("event EndRatio", ev.Num("EndRatio", 0));
                }
                if (!first) line.Append(", ");
                first = false;
                line.Append(e.Str("Name")).Append('[').Append(evs.Count).Append(loop ? " loop" : "").Append(']');
            }
            FileLines.Add(line.ToString());
            string[] dom = new string[] { "box", "sphere", "cylinder", "attractor" };
            foreach (object o in spec.Arr("emitters") ?? new List<object>())
            {
                JObj e = (JObj)o;
                Emitters++;
                Count("emitter IsOneShot", Json.Write(e.Get("IsOneShot"), false));
                foreach (string role in new string[] { "CreationDomain", "TargetDomain", "AttractorDomain" })
                {
                    JObj d = e.Obj(role);
                    if (d == null) { Count(role + " type", "none"); continue; }
                    int t = (int)d.Num("DomainType", 0);
                    Count(role + " type", t < dom.Length ? dom[t] : "type" + t);
                    Count(role + " flags", "world=" + d.Num("IsWorldSpace", 0) + " pointRel=" + d.Num("IsPointRelative", 0) + " creationRel=" + d.Num("IsCreationRelative", 0) + " targetRel=" + d.Num("IsTargetRelative", 0));
                    SampleKfp(role + " SizeOuter", d, "SizeOuterKFP", 3);
                }
                bool one = e.Num("IsOneShot", 0) != 0;
                SampleKfp("emitter SpawnRateOverTime" + (one ? " (one-shot)" : " (continuous)"), e, "SpawnRateOverTimeKFP", 2);
                SampleKfp("emitter ParticleLife", e, "ParticleLifeKFP", 2);
                SampleKfp("emitter SpeedScalar", e, "SpeedScalarKFP", 2);
                SampleKfp("emitter SizeScalar", e, "SizeScalarKFP", 3);
                SampleKfp("emitter PlaybackRateScalar", e, "PlaybackRateScalarKFP", 1);
                SampleKfp("emitter SpawnRateOverDist", e, "SpawnRateOverDistKFP", 2);
                SampleKfp("emitter InheritVelocity", e, "InheritVelocityKFP", 2);
            }
            foreach (object o in spec.Arr("particles") ?? new List<object>())
            {
                JObj p = (JObj)o;
                Particles++;
                string tech = p.Str("ShaderTemplateName") + "/" + p.Str("ShaderTemplateTechniqueName");
                Count("technique", tech);
                Count("technique -> BlendSet", tech + " blend=" + Json.Write(p.Get("BlendSet"), false));
                Count("technique -> flags", tech + " lit=" + p.Num("IsLit", 0) + " soft=" + p.Num("IsSoft", 0) + " diffuseMode=" + p.Num("DiffuseMode", 0) + " lighting=" + p.Num("LightingMode", 0) + " drawType=" + p.Num("DrawType", 0));
                foreach (string f in new string[] { "CullMode", "DepthWrite", "DepthTest", "AlphaBlend", "SortType", "DrawType", "Flags", "ProjectionMode", "IsScreenSpace", "IsRefract", "IsNormalSpec" })
                    Count("particle " + f, Json.Write(p.Get(f), false));
                StringBuilder combo = new StringBuilder();
                foreach (object bo in p.Arr("AllBehaviours") ?? new List<object>())
                {
                    JObj b = bo as JObj;
                    if (b == null) continue;
                    string t = b.Str("type");
                    Count("behaviour", t);
                    if (combo.Length > 0) combo.Append(' ');
                    combo.Append(t);
                    foreach (KeyValuePair<string, object> kv in b.Items)
                    {
                        if (kv.Key.EndsWith("KFP")) { SampleKfp(t + "." + kv.Key.Substring(0, kv.Key.Length - 3), b, kv.Key, kv.Key.StartsWith("RGBA") ? 4 : 3); continue; }
                        if (kv.Value is JObj || kv.Value is List<object> || kv.Key == "type" || kv.Key.Contains("#")) continue;
                        if (System.Text.RegularExpressions.Regex.IsMatch(kv.Key, "^(P\\d+|U[0-9A-F]+|VFT|Unused\\d+)$")) continue;
                        if (kv.Value is float && kv.Key != "FlipChanceU" && kv.Key != "FlipChanceV") { Sample(t + "." + kv.Key, (float)kv.Value); continue; }
                        Count(t + "." + kv.Key, Json.Write(kv.Value, false));
                    }
                    if (t == "Sprite" || t == "Trail") Count(t + " AlignmentMode+Axis", "mode=" + b.Num("AlignmentMode", 0) + " axis=" + Json.Write(b.Get("AlignAxis"), false));
                }
                Count("behaviour set", combo.ToString());
                foreach (object vo in p.Arr("ShaderVars") ?? new List<object>())
                {
                    JObj v = (JObj)vo;
                    if (v.Str("kind") == "Texture")
                    {
                        string tn = v.Str("TextureName");
                        if (string.IsNullOrEmpty(tn) || v.Str("Name") != "DiffuseTex2") continue;
                        int[] c;
                        if (!tex.TryGetValue(tn, out c)) { c = new int[4]; tex[tn] = c; }
                        if (v.Num("ExternalReference", 0) != 0 || !v.Has("Texture")) c[0]++; else c[1]++;
                        c[2] = Math.Max(c[2], (int)p.Num("TexFrameIDMax", 0));
                        foreach (object bo in p.Arr("AllBehaviours") ?? new List<object>())
                        {
                            JObj b = bo as JObj;
                            if (b != null && b.Str("type") == "AnimateTexture") c[3] = Math.Max(c[3], (int)b.Num("LastFrameID", 0));
                        }
                    }
                    else if (v.Str("kind") == "Vector")
                    {
                        List<object> vec = v.Arr("Vector");
                        if (vec != null && vec.Count > 0) Sample("var " + v.Str("Name"), Json.ToDouble(vec[0]));
                    }
                    else if (v.Str("kind") == "Keyframe")
                    {
                        List<object> items = v.Arr("Items");
                        if (items != null && items.Count > 0) Sample("var " + v.Str("Name"), ((JObj)items[0]).Num("U10", 0));
                    }
                }
            }
        }

        static string F(double v)
        {
            double a = Math.Abs(v);
            if (a != 0 && a < 0.01) return v.ToString("0.####", CultureInfo.InvariantCulture);
            if (a < 10) return v.ToString("0.##", CultureInfo.InvariantCulture);
            return v.ToString("0.#", CultureInfo.InvariantCulture);
        }

        public string Report(int top)
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("files=" + Files + " withModels=" + WithModels + " effects=" + Effects + " looped=" + Looped + " emitters=" + Emitters + " particleRules=" + Particles);
            sb.AppendLine();
            sb.AppendLine("## Counted fields");
            List<string> groups = new List<string>(counts.Keys);
            groups.Sort(StringComparer.Ordinal);
            foreach (string g in groups)
            {
                List<KeyValuePair<string, int>> l = new List<KeyValuePair<string, int>>(counts[g]);
                l.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b) { return b.Value.CompareTo(a.Value); });
                sb.Append(g).Append(": ");
                int lim = g == "behaviour set" || g.StartsWith("technique") ? top * 2 : top;
                for (int i = 0; i < l.Count && i < lim; i++) { if (i > 0) sb.Append("; "); sb.Append(l[i].Key).Append(" x").Append(l[i].Value); }
                if (l.Count > lim) sb.Append("; ... +").Append(l.Count - lim).Append(" more");
                sb.AppendLine();
            }
            sb.AppendLine();
            sb.AppendLine("## Sampled numbers (n, min, p10, median, p90, max)");
            groups = new List<string>(samples.Keys);
            groups.Sort(StringComparer.Ordinal);
            foreach (string g in groups)
            {
                List<float> l = samples[g];
                l.Sort();
                int n = l.Count;
                sb.Append(g).Append(": n=").Append(n).Append(" min=").Append(F(l[0])).Append(" p10=").Append(F(l[(int)(n * 0.1)])).Append(" med=").Append(F(l[n / 2])).Append(" p90=").Append(F(l[Math.Min(n - 1, (int)(n * 0.9))])).Append(" max=").AppendLine(F(l[n - 1]));
            }
            sb.AppendLine();
            sb.AppendLine("## Diffuse textures (external uses, embedded uses, max TexFrameIDMax, max LastFrameID, embedded size)");
            List<KeyValuePair<string, int[]>> tl = new List<KeyValuePair<string, int[]>>(tex);
            tl.Sort(delegate (KeyValuePair<string, int[]> a, KeyValuePair<string, int[]> b) { return (b.Value[0] + b.Value[1]).CompareTo(a.Value[0] + a.Value[1]); });
            foreach (KeyValuePair<string, int[]> t in tl)
            {
                string info;
                texInfo.TryGetValue(t.Key, out info);
                sb.Append(t.Key).Append(" | ").Append(t.Value[0]).Append(" | ").Append(t.Value[1]).Append(" | ").Append(t.Value[2]).Append(" | ").Append(t.Value[3]).Append(" | ").AppendLine(info ?? "");
            }
            return sb.ToString();
        }
    }
}
