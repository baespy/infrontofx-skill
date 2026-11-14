using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace WeaponForge
{
    public class Defaults
    {
        public Dictionary<string, Dictionary<string, object>> Map = new Dictionary<string, Dictionary<string, object>>();
        public JObj VarSets = new JObj();

        public bool TryGet(string[] keys, string path, out object v)
        {
            v = null;
            if (keys == null) return false;
            for (int i = 0; i < keys.Length; i++)
            {
                Dictionary<string, object> m;
                if (keys[i] != null && Map.TryGetValue(keys[i], out m) && m.TryGetValue(path, out v)) return true;
            }
            return false;
        }

        public static Defaults Load(string path)
        {
            Defaults d = new Defaults();
            JObj root = (JObj)Json.Parse(File.ReadAllText(path));
            JObj structs = root.Obj("structs");
            if (structs != null)
                foreach (KeyValuePair<string, object> kv in structs.Items)
                {
                    Dictionary<string, object> m = new Dictionary<string, object>();
                    foreach (KeyValuePair<string, object> f in ((JObj)kv.Value).Items) m[f.Key] = f.Value;
                    d.Map[kv.Key] = m;
                }
            if (root.Obj("varSets") != null) d.VarSets = root.Obj("varSets");
            return d;
        }
    }

    public class DefaultsBuilder
    {
        Dictionary<string, Dictionary<string, Dictionary<string, int>>> counts = new Dictionary<string, Dictionary<string, Dictionary<string, int>>>();
        Dictionary<string, Dictionary<string, int>> varSetCounts = new Dictionary<string, Dictionary<string, int>>();
        Dictionary<string, int> instances = new Dictionary<string, int>();
        public int Files;

        public void Tap(string key, string path, object value)
        {
            Dictionary<string, Dictionary<string, int>> k;
            if (!counts.TryGetValue(key, out k)) { k = new Dictionary<string, Dictionary<string, int>>(); counts[key] = k; }
            Dictionary<string, int> p;
            if (!k.TryGetValue(path, out p)) { p = new Dictionary<string, int>(); k[path] = p; }
            string s = Json.Write(value, false);
            int c;
            p.TryGetValue(s, out c);
            p[s] = c + 1;
        }

        public void Add(YptFile y)
        {
            Decompiler dc = new Decompiler(y, null);
            dc.Full = true;
            dc.Tap = Tap;
            JObj spec = dc.Run();
            Files++;
            List<object> ps = spec.Arr("particles");
            if (ps == null) return;
            foreach (object o in ps)
            {
                JObj p = (JObj)o;
                List<object> vars = p.Arr("ShaderVars");
                if (vars == null) continue;
                List<object> clean = new List<object>();
                foreach (object vo in vars)
                {
                    JObj v = ((JObj)vo).Clone();
                    v.Remove("Texture");
                    v.Remove("TextureName");
                    v.Remove("TextureNameHash");
                    v.Remove("ExternalReference");
                    clean.Add(v);
                }
                string key = p.Str("ShaderTemplateName") + "|" + p.Str("ShaderTemplateTechniqueName");
                Dictionary<string, int> m;
                if (!varSetCounts.TryGetValue(key, out m)) { m = new Dictionary<string, int>(); varSetCounts[key] = m; }
                string s = Json.Write(clean, false);
                int c;
                m.TryGetValue(s, out c);
                m[s] = c + 1;
            }
        }

        public string Finish()
        {
            JObj root = new JObj();
            root.Add("format", "weapon-forge-ptfx-defaults/1");
            root.Add("files", (double)Files);
            JObj structs = new JObj();
            List<string> keys = new List<string>(counts.Keys);
            keys.Sort(StringComparer.Ordinal);
            foreach (string key in keys)
            {
                JObj o = new JObj();
                foreach (KeyValuePair<string, Dictionary<string, int>> p in counts[key])
                {
                    string best = null;
                    int bc = -1;
                    foreach (KeyValuePair<string, int> v in p.Value)
                        if (v.Value > bc || (v.Value == bc && string.CompareOrdinal(v.Key, best) < 0)) { best = v.Key; bc = v.Value; }
                    object val = Json.Parse(best);
                    if (p.Key.Contains("#key")) continue;
                    if (IsZero(val) && key.IndexOf('|') < 0 && key.IndexOf('@') < 0) continue;
                    o.Add(p.Key, val);
                }
                structs.Add(key, o);
            }
            root.Add("structs", structs);
            JObj vs = new JObj();
            List<string> vkeys = new List<string>(varSetCounts.Keys);
            vkeys.Sort(StringComparer.Ordinal);
            foreach (string key in vkeys)
            {
                string best = null;
                int bc = -1, total = 0;
                foreach (KeyValuePair<string, int> v in varSetCounts[key])
                {
                    total += v.Value;
                    if (v.Value > bc) { best = v.Key; bc = v.Value; }
                }
                JObj e = new JObj();
                e.Add("seen", (double)total);
                e.Add("vars", Json.Parse(best));
                vs.Add(key, e);
            }
            root.Add("varSets", vs);
            return Json.Write(root, true);
        }

        public static bool IsZero(object v)
        {
            if (v == null) return true;
            if (v is double) return (double)v == 0;
            if (v is float) return (float)v == 0f && BitConverter.ToInt32(BitConverter.GetBytes((float)v), 0) == 0;
            string s = v as string;
            if (s != null) return s.Length == 0 || s == "0x00000000";
            List<object> l = v as List<object>;
            if (l != null) { foreach (object x in l) if (!IsZero(x)) return false; return true; }
            return false;
        }
    }

    public class Decompiler
    {
        public YptFile Y;
        public Defaults D;
        public bool Full;
        public Action<string, string, object> Tap;
        public List<string> Notes = new List<string>();
        Dictionary<Node, string> ids = new Dictionary<Node, string>();
        List<Node> extraEmit = new List<Node>(), extraPtx = new List<Node>();
        HashSet<Node> inDict = new HashSet<Node>();

        public Decompiler(YptFile y, Defaults d)
        {
            Y = y;
            D = d;
        }

        public static string Hex(uint v) { return "0x" + v.ToString("x8"); }

        public static string HashName(uint h)
        {
            string s;
            if (Schema.KfpNames.TryGetValue(h, out s)) return s;
            if (Schema.VarNames.TryGetValue(h, out s)) return s;
            return Hex(h);
        }

        static object ReadScalar(Node n, int at, Field f)
        {
            switch (f.Type)
            {
                case "u8": return (double)n.Data[at];
                case "u16": return (double)n.U16(at);
                case "u32": return (double)n.U32(at);
                case "i32": return (double)n.I32(at);
                case "f32": return n.F32(at);
                case "h32": return HashName(n.U32(at));
                case "rgba": return Hex(n.U32(at));
                case "u64":
                {
                    ulong v = n.U64(at);
                    if (v <= 9007199254740992UL) return (double)v;
                    return "0x" + v.ToString("x16");
                }
                case "v3": return new List<object> { n.F32(at), n.F32(at + 4), n.F32(at + 8) };
                case "v4": return new List<object> { n.F32(at), n.F32(at + 4), n.F32(at + 8), n.F32(at + 12) };
                case "c32":
                {
                    int e = 0;
                    while (e < 32 && n.Data[at + e] != 0) e++;
                    return Encoding.ASCII.GetString(n.Data, at, e);
                }
            }
            return null;
        }

        public static bool IsScalar(string t)
        {
            return t == "u8" || t == "u16" || t == "u32" || t == "i32" || t == "f32" || t == "h32" || t == "rgba" || t == "u64" || t == "v3" || t == "v4" || t == "c32";
        }

        void Put(JObj o, string[] keys, string path, string name, object val)
        {
            if (Tap != null && keys != null) for (int i = 0; i < keys.Length; i++) if (keys[i] != null) Tap(keys[i], path, val);
            if (Full) { o.Add(name, val); return; }
            object dv;
            if (D != null && D.TryGet(keys, path, out dv))
            {
                if (Json.Write(dv, false) == Json.Write(val, false)) return;
            }
            else if (DefaultsBuilder.IsZero(val)) return;
            o.Add(name, val);
        }

        public static List<int> AutoKfpOffsets(StructDef d)
        {
            List<int> l = new List<int>();
            foreach (Field f in d.Fields) if (f.Type == "kfp") l.Add(f.Off);
            return l;
        }

        public static void DeriveBehaviourLists(List<string> types, List<int> init, List<int> update, List<int> finalize, List<int> draw)
        {
            for (int i = 0; i < types.Count; i++)
            {
                string t = types[i];
                bool render = t == "Sprite" || t == "Model" || t == "Trail";
                bool extra = t == "Collision" || t == "Light" || t == "Decal" || t == "ZCull" || t == "Trail" || t == "FogVolume" || t == "River" || t == "DecalPool" || t == "Liquid";
                bool extra2 = t == "Sprite" || t == "Model" || t == "Trail" || t == "FogVolume";
                if (!render) { init.Add(i); update.Add(i); }
                if (extra) finalize.Add(i);
                if (extra2) draw.Add(i);
            }
        }

        static bool SameInts(List<int> a, List<int> b)
        {
            if (a.Count != b.Count) return false;
            for (int i = 0; i < a.Count; i++) if (a[i] != b[i]) return false;
            return true;
        }

        static List<object> IntList(List<int> a)
        {
            List<object> l = new List<object>();
            foreach (int i in a) l.Add((double)i);
            return l;
        }

        object Keys(Node arr, int count)
        {
            List<object> keys = new List<object>();
            float prev = 0;
            for (int i = 0; i < count; i++)
            {
                int b = i * 0x20;
                float t = arr.F32(b), ty = arr.F32(b + 4), tz = arr.F32(b + 8), tw = arr.F32(b + 12);
                float exp = i == 0 ? 0f : 1.0f / (t - prev);
                bool plain = BitConverter.ToInt32(BitConverter.GetBytes(exp), 0) == BitConverter.ToInt32(BitConverter.GetBytes(ty), 0) && tz == 0f && tw == 0f;
                List<object> k = new List<object>();
                k.Add(t);
                if (!plain) { k.Add(ty); k.Add(tz); k.Add(tw); }
                k.Add(arr.F32(b + 16)); k.Add(arr.F32(b + 20)); k.Add(arr.F32(b + 24)); k.Add(arr.F32(b + 28));
                keys.Add(k);
                prev = t;
            }
            return keys;
        }

        JObj Emit(Node n, int b, StructDef d, string[] keys, string prefix)
        {
            JObj o = new JObj();
            foreach (Field f in d.Fields)
            {
                int at = b + f.Off;
                string path = prefix + f.Name;
                if (IsScalar(f.Type))
                {
                    if (f.Name == "Type" && d.Name.StartsWith("Beh_")) continue;
                    if (b == 0 && d.Name.StartsWith("Var_") && (f.Name == "Name" || f.Name == "ShaderVarID"))
                    {
                        object sv = ReadScalar(n, at, f);
                        if (Tap != null && keys != null) Tap(keys[0], path, sv);
                        o.Add(f.Name, sv);
                        continue;
                    }
                    Put(o, keys, path, f.Name, ReadScalar(n, at, f));
                    continue;
                }
                Node t = n.Target(at);
                if ((f.Type == "plist" || f.Type == "hlist") && (d.Name.StartsWith("Dict") || d.Name == "TexDict" || d.Name == "DrawDict")) continue;
                switch (f.Type)
                {
                    case "str":
                        if (t != null) o.Add(f.Name, t.Str());
                        break;
                    case "kfp":
                    {
                        JObj k = Emit(n, at, Schema.Defs["KFP"], keys, path + ".");
                        if (k.Count == 1 && k.Has("keys") && !Full) o.Add(f.Name, k.Get("keys"));
                        else if (k.Count > 0) o.Add(f.Name, k);
                        break;
                    }
                    case "sub":
                    {
                        JObj k = Emit(n, at, Schema.Defs[f.Arg], keys, path + ".");
                        if (k.Count > 0) o.Add(f.Name, k);
                        break;
                    }
                    case "gptr":
                        break;
                    case "iptr":
                    {
                        Ref r = null;
                        foreach (Ref x in n.Refs) if (x.At == at) r = x;
                        if (r != null) o.Add(f.Name, (double)(r.Add / 24));
                        break;
                    }
                    case "ptr":
                        EmitPtr(o, n, f, t, keys, path);
                        break;
                    case "hlist":
                    {
                        if (d.Name.StartsWith("Dict") || d.Name == "TexDict" || d.Name == "DrawDict") break;
                        int count = n.U16(at + 8), cap = n.U16(at + 10);
                        if (t != null)
                        {
                            List<object> l = new List<object>();
                            for (int i = 0; i < count; i++) l.Add(HashName(t.U32(i * 4)));
                            o.Add(f.Name, l);
                        }
                        if (cap != count) o.Add(f.Name + "#cap", (double)cap);
                        break;
                    }
                    case "list":
                    {
                        int count = n.U16(at + 8), cap = n.U16(at + 10);
                        if (t != null)
                        {
                            if (f.Arg == "Keyframe") o.Add(f.Name == "Values" ? "keys" : f.Name, Keys(t, count));
                            else
                            {
                                StructDef ed = Schema.Defs[f.Arg];
                                List<object> l = new List<object>();
                                for (int i = 0; i < count; i++) l.Add(Emit(t, i * ed.Size, ed, new string[] { f.Arg }, ""));
                                o.Add(f.Name, l);
                            }
                        }
                        if (cap != count) o.Add((f.Name == "Values" ? "keys" : f.Name) + "#cap", (double)cap);
                        break;
                    }
                    case "kplist":
                    {
                        int count = n.U16(at + 8), cap = n.U16(at + 10);
                        if (Tap != null && keys != null) Tap(keys[keys.Length - 1], path + "#cap", (double)cap);
                        List<int> actual = new List<int>();
                        bool foreign = false;
                        if (t != null)
                            for (int i = 0; i < count; i++)
                            {
                                Ref r = null;
                                foreach (Ref x in t.Refs) if (x.At == i * 8) r = x;
                                if (r == null) { actual.Add(-1); continue; }
                                if (r.To != n) foreign = true;
                                actual.Add(r.Add - b);
                            }
                        if (foreign) Notes.Add(d.Name + "." + f.Name + " points at keyframe props outside its own block");
                        if (Tap != null && keys != null && !foreign) Tap(keys[keys.Length - 1], path + "#offsets", IntList(actual));
                        List<int> auto = AutoKfpOffsets(d);
                        object doffs;
                        if (D != null && D.TryGet(keys, path + "#offsets", out doffs) && doffs is List<object>)
                        {
                            auto = new List<int>();
                            foreach (object x in (List<object>)doffs) auto.Add((int)Json.ToDouble(x));
                        }
                        object dcap;
                        int expCap = auto.Count;
                        if (D != null && D.TryGet(keys, path + "#cap", out dcap)) expCap = Math.Max(auto.Count, (int)Json.ToDouble(dcap));
                        if (auto.Count == 0) expCap = 0;
                        if (!SameInts(actual, auto) || cap != expCap || Full)
                        {
                            JObj k = new JObj();
                            k.Add("offsets", IntList(actual));
                            k.Add("cap", (double)cap);
                            if (t == null) k.Add("null", true);
                            o.Add(f.Name, k);
                        }
                        break;
                    }
                    case "plist":
                        EmitPList(o, n, at, f, t, keys, path, d);
                        break;
                }
            }
            return o;
        }

        void EmitPtr(JObj o, Node n, Field f, Node t, string[] keys, string path)
        {
            switch (f.Arg)
            {
                case "Root":
                    if (t == null) o.Add(f.Name, null);
                    break;
                case "EmitterRule":
                case "ParticleRule":
                case "EffectRule":
                    if (t != null) o.Add(f.Name, IdOf(t));
                    break;
                case "Domain":
                    if (t != null) o.Add(f.Name, Emit(t, 0, Schema.Defs["Domain"], new string[] { "Domain@" + f.Name, "Domain" }, ""));
                    break;
                case "EvolutionList":
                    if (t != null) o.Add(f.Name, Emit(t, 0, Schema.Defs["EvolutionList"], new string[] { "EvolutionList" }, ""));
                    break;
                case "Texture":
                    if (t != null) o.Add(f.Name, t.Label);
                    break;
                case "Opaque":
                    if (t != null) o.Add(f.Name, "opaque");
                    break;
            }
        }

        string IdOf(Node t)
        {
            string id;
            if (ids.TryGetValue(t, out id)) return id;
            Node nm = t.Target(t.Kind == "ParticleRule" ? 0x120 : 0x20);
            id = Unique(nm != null ? nm.Str() : "unnamed");
            ids[t] = id;
            if (t.Kind == "EmitterRule") extraEmit.Add(t);
            else if (t.Kind == "ParticleRule") extraPtx.Add(t);
            return id;
        }

        HashSet<string> usedIds = new HashSet<string>();

        string Unique(string name)
        {
            string id = name;
            int k = 2;
            while (!usedIds.Add(id)) id = name + "#" + (k++);
            return id;
        }

        void EmitPList(JObj o, Node n, int at, Field f, Node arr, string[] keys, string path, StructDef d)
        {
            int count = n.U16(at + 8), cap = n.U16(at + 10);
            if (Tap != null && keys != null && f.Name == "EventEmitters") Tap(keys[keys.Length - 1], path + "#cap", (double)cap);
            List<Node> items = new List<Node>();
            if (arr != null) for (int i = 0; i < count; i++) items.Add(arr.Target(i * 8));
            if (f.Arg == "Behaviour" && f.Name != "AllBehaviours")
            {
                Node all = n.Target(d.ByName["AllBehaviours"].Off);
                int allCount = n.U16(d.ByName["AllBehaviours"].Off + 8);
                List<Node> allItems = new List<Node>();
                List<string> types = new List<string>();
                if (all != null) for (int i = 0; i < allCount; i++) { Node x = all.Target(i * 8); allItems.Add(x); types.Add(x == null ? "?" : x.Kind.Substring(4)); }
                List<int> actual = new List<int>();
                foreach (Node x in items) actual.Add(allItems.IndexOf(x));
                List<int> init = new List<int>(), update = new List<int>(), fin = new List<int>(), draw = new List<int>();
                DeriveBehaviourLists(types, init, update, fin, draw);
                List<int> exp = f.Name == "InitBehaviours" ? init : f.Name == "UpdateBehaviours" ? update : f.Name == "UpdateFinalizeBehaviours" ? fin : draw;
                if (!SameInts(actual, exp) || cap != count) { o.Add(f.Name, IntList(actual)); if (cap != count) o.Add(f.Name + "#cap", (double)cap); }
                return;
            }
            List<object> l = new List<object>();
            foreach (Node x in items)
            {
                if (x == null) { l.Add(null); continue; }
                if (f.Arg == "Behaviour")
                {
                    JObj b = new JObj();
                    b.Add("type", x.Kind.Substring(4));
                    foreach (KeyValuePair<string, object> kv in Emit(x, 0, Schema.Defs[x.Kind], new string[] { x.Kind }, "").Items) b.Add(kv.Key, kv.Value);
                    l.Add(b);
                }
                else if (f.Arg == "ShaderVar")
                {
                    JObj v = new JObj();
                    v.Add("kind", x.Kind.Substring(4));
                    foreach (KeyValuePair<string, object> kv in Emit(x, 0, Schema.Defs[x.Kind], new string[] { x.Kind }, "").Items) v.Add(kv.Key, kv.Value);
                    l.Add(v);
                }
                else
                {
                    JObj e = Emit(x, 0, Schema.Defs[x.Kind], new string[] { x.Kind }, "");
                    if (x.Kind == "EventEmitter" && !Full)
                    {
                        e.Remove("Index");
                        if (x.U32(8) != (uint)l.Count) e.Add("Index", (double)x.U32(8));
                    }
                    l.Add(e);
                }
            }
            if (arr != null || Full) o.Add(f.Name, l);
            int expCap = count;
            object dcap;
            if (f.Name == "EventEmitters" && D != null && D.TryGet(keys, path + "#cap", out dcap)) expCap = Math.Max(count, (int)Json.ToDouble(dcap));
            if (cap != expCap || (Full && cap != count)) o.Add(f.Name + "#cap", (double)cap);
        }

        List<Node> DictItems(Node dict, out bool sorted, out bool hashesMatch, int nameOff)
        {
            sorted = true;
            hashesMatch = true;
            List<Node> items = new List<Node>();
            if (dict == null || dict.Kind == "Dict_Empty") return items;
            Node hashes = dict.Target(0x20), arr = dict.Target(0x30);
            int count = dict.U16(0x38);
            uint prev = 0;
            for (int i = 0; i < count; i++)
            {
                Node x = arr == null ? null : arr.Target(i * 8);
                items.Add(x);
                if (hashes == null) continue;
                uint h = hashes.U32(i * 4);
                if (i > 0 && h < prev) sorted = false;
                prev = h;
                if (x != null && nameOff >= 0)
                {
                    Node nm = x.Target(nameOff);
                    if (nm == null || Jenkins.Hash(nm.Str()) != h) hashesMatch = false;
                }
            }
            return items;
        }

        public JObj Run()
        {
            JObj spec = new JObj();
            spec.Add("format", "weapon-forge-ptfx/1");
            Node root = Y.Root;
            Node nm = root.Target(0x10);
            spec.Add("name", nm == null ? "" : nm.Str());
            spec.Add("_source", Y.Path);
            JObj rf = Emit(root, 0, Schema.Defs["Root"], new string[] { "Root" }, "");
            rf.Remove("Name");
            if (rf.Count > 0) spec.Add("root", rf);
            Node pm = root.Target(0x08);
            if (pm != null)
            {
                JObj pj = Emit(pm, 0, Schema.Defs["PageMap"], new string[] { "PageMap" }, "");
                pj.Remove("SysPages");
                pj.Remove("GfxPages");
                if (pj.Count > 0 && !Full) spec.Add("pageMap", pj);
            }

            Node texDict = root.Target(0x20), drawDict = root.Target(0x30), ptxDict = root.Target(0x38), dictA = root.Target(0x48), dictB = root.Target(0x50);
            Node effDict = null, emitDict = null;
            if (dictA != null && dictA.Kind == "Dict_EffectRule") effDict = dictA; else if (dictA != null && dictA.Kind == "Dict_EmitterRule") emitDict = dictA;
            if (dictB != null && dictB.Kind == "Dict_EffectRule") effDict = dictB; else if (dictB != null && dictB.Kind == "Dict_EmitterRule") emitDict = dictB;
            if (dictA != null && dictA.Kind == "Dict_EmitterRule") spec.Add("effectSlot", "B");
            if (dictA != null && dictA.Kind == "Dict_Empty" && dictB != null && dictB.Kind == "Dict_Empty") { }
            else
            {
                if (effDict == null && dictA != null && dictA.Kind == "Dict_Empty") effDict = dictA;
                if (emitDict == null && dictB != null && dictB.Kind == "Dict_Empty") emitDict = dictB;
            }

            JObj dj = new JObj();
            Node[] dicts = new Node[] { texDict, drawDict, ptxDict, effDict, emitDict };
            string[] dnames = new string[] { "TexDict", "DrawDict", "Dict_ParticleRule", "Dict_EffectRule", "Dict_EmitterRule" };
            for (int i = 0; i < dicts.Length; i++)
            {
                if (dicts[i] == null) { dj.Add(dnames[i], null); continue; }
                JObj e = Emit(dicts[i], 0, Schema.Defs["Dict_ParticleRule"], new string[] { "Dict" }, "");
                e.Remove("Items");
                if (e.Count > 0) dj.Add(dnames[i], e);
            }
            if (dj.Count > 0) spec.Add("dicts", dj);

            bool sorted, match;
            List<Node> texs = DictItems(texDict, out sorted, out match, 0x28);
            if (!sorted) Notes.Add("texture dictionary is not sorted by hash");
            if (!match) Notes.Add("texture dictionary hashes do not match texture names");
            List<Node> ptxs = DictItems(ptxDict, out sorted, out match, 0x120);
            if (!sorted) Notes.Add("particle rule dictionary is not sorted by hash");
            if (!match) Notes.Add("particle rule dictionary hashes do not match names");
            List<Node> effs = DictItems(effDict, out sorted, out match, 0x20);
            if (!sorted) Notes.Add("effect rule dictionary is not sorted by hash");
            if (!match) Notes.Add("effect rule dictionary hashes do not match names");
            List<Node> emits = DictItems(emitDict, out sorted, out match, 0x20);
            if (!sorted) Notes.Add("emitter rule dictionary is not sorted by hash");
            if (!match) Notes.Add("emitter rule dictionary hashes do not match names");

            foreach (Node x in ptxs) if (x != null) { inDict.Add(x); ids[x] = Unique(x.Target(0x120) != null ? x.Target(0x120).Str() : "unnamed"); }
            usedIds.Clear();
            foreach (Node x in emits) if (x != null) { inDict.Add(x); ids[x] = Unique(x.Target(0x20) != null ? x.Target(0x20).Str() : "unnamed"); }
            usedIds.Clear();
            foreach (Node x in effs) if (x != null) { inDict.Add(x); ids[x] = Unique(x.Target(0x20) != null ? x.Target(0x20).Str() : "unnamed"); }
            usedIds.Clear();

            List<object> tl = new List<object>();
            foreach (Node t in texs)
            {
                if (t == null) continue;
                JObj tj = new JObj();
                tj.Add("name", t.Label);
                tj.Add("width", (double)t.U16(0x50));
                tj.Add("height", (double)t.U16(0x52));
                tj.Add("format", YptFile.FormatName(t.U32(0x58)));
                tj.Add("levels", (double)t.Data[0x5D]);
                JObj f = Emit(t, 0, Schema.Defs["Texture"], new string[] { "Texture" }, "");
                foreach (string k in new string[] { "Name", "Width", "Height", "Stride", "Format", "Levels" }) if (!Full) f.Remove(k);
                if (f.Count > 0) tj.Add("fields", f);
                JObj src = new JObj();
                src.Add("from", Y.Path);
                tj.Add("data", src);
                tl.Add(tj);
            }
            spec.Add("textures", tl);
            if (drawDict != null && drawDict.U16(0x38) > 0)
            {
                List<object> dn = new List<object>();
                Node hashes = drawDict.Target(0x20);
                for (int i = 0; i < drawDict.U16(0x38); i++) dn.Add(hashes == null ? "?" : Hex(hashes.U32(i * 4)));
                spec.Add("drawables", dn);
            }

            List<object> el = new List<object>();
            foreach (Node e in effs) if (e != null) el.Add(Rule(e, "EffectRule", null));
            List<object> ml = new List<object>();
            foreach (Node e in emits) if (e != null) ml.Add(Rule(e, "EmitterRule", null));
            List<object> pl = new List<object>();
            foreach (Node e in ptxs) if (e != null) pl.Add(ParticleRule(e));
            int guard = 0;
            while ((extraEmit.Count > 0 || extraPtx.Count > 0) && guard++ < 10000)
            {
                if (extraEmit.Count > 0) { Node e = extraEmit[0]; extraEmit.RemoveAt(0); JObj j = Rule(e, "EmitterRule", null); j.Add("inDict", false); ml.Add(j); }
                else { Node e = extraPtx[0]; extraPtx.RemoveAt(0); JObj j = ParticleRule(e); j.Add("inDict", false); pl.Add(j); }
            }
            spec.Add("effects", el);
            spec.Add("emitters", ml);
            spec.Add("particles", pl);
            if (Notes.Count > 0)
            {
                List<object> nl = new List<object>();
                foreach (string s in Notes) if (!nl.Contains(s)) nl.Add(s);
                spec.Add("_notes", nl);
            }
            return spec;
        }

        JObj Rule(Node n, string kind, string[] keys)
        {
            JObj o = new JObj();
            o.Add("id", ids.ContainsKey(n) ? ids[n] : IdOf(n));
            foreach (KeyValuePair<string, object> kv in Emit(n, 0, Schema.Defs[kind], keys ?? new string[] { kind }, "").Items) o.Add(kv.Key, kv.Value);
            return o;
        }

        JObj ParticleRule(Node n)
        {
            Node sh = n.Target(0x1B8), te = n.Target(0x1C0);
            string key = "ParticleRule|" + (sh == null ? "" : sh.Str()) + "|" + (te == null ? "" : te.Str());
            return Rule(n, "ParticleRule", new string[] { key, "ParticleRule" });
        }
    }

    public class TexPayload
    {
        public int Width, Height, Levels, Stride;
        public uint Format;
        public byte[] Data;
    }

    public class Compiler
    {
        public Defaults D;
        public List<string> Warnings = new List<string>();
        public Func<JObj, string, TexPayload> TextureProvider;
        public bool DropModels = true;
        Node root;
        Dictionary<string, Node> tex = new Dictionary<string, Node>(StringComparer.OrdinalIgnoreCase);
        Dictionary<string, Node> emit = new Dictionary<string, Node>(), ptx = new Dictionary<string, Node>(), eff = new Dictionary<string, Node>();
        List<object[]> pending = new List<object[]>();
        Dictionary<string, YptFile> sourceCache = new Dictionary<string, YptFile>(StringComparer.OrdinalIgnoreCase);

        public Compiler(Defaults d) { D = d; }

        void Warn(string s) { if (!Warnings.Contains(s)) Warnings.Add(s); }

        static uint ParseHash(object v)
        {
            if (v is double) return (uint)(double)v;
            string s = Convert.ToString(v, CultureInfo.InvariantCulture);
            if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) return Convert.ToUInt32(s.Substring(2), 16);
            return Jenkins.Hash(s);
        }

        static void WriteScalar(Node n, int at, Field f, object v)
        {
            switch (f.Type)
            {
                case "u8": n.Data[at] = (byte)Json.ToDouble(v); break;
                case "u16": n.W16(at, (ushort)Json.ToDouble(v)); break;
                case "u32": n.W32(at, (uint)Json.ToDouble(v)); break;
                case "i32": n.W32(at, (uint)(int)Json.ToDouble(v)); break;
                case "f32": n.WF(at, Json.ToFloat(v)); break;
                case "h32": n.W32(at, ParseHash(v)); break;
                case "rgba": n.W32(at, ParseHash(v)); break;
                case "u64":
                {
                    string s = v as string;
                    if (s != null && s.StartsWith("0x")) n.W64(at, Convert.ToUInt64(s.Substring(2), 16));
                    else n.W64(at, (ulong)Json.ToDouble(v));
                    break;
                }
                case "v3":
                case "v4":
                {
                    List<object> l = (List<object>)v;
                    int c = f.Type == "v3" ? 3 : 4;
                    for (int i = 0; i < c && i < l.Count; i++) n.WF(at + i * 4, Json.ToFloat(l[i]));
                    break;
                }
                case "c32":
                {
                    byte[] b = Encoding.ASCII.GetBytes(Convert.ToString(v));
                    for (int i = 0; i < 32; i++) n.Data[at + i] = i < b.Length && i < 31 ? b[i] : (byte)0;
                    break;
                }
            }
        }

        void ApplyDefaults(Node n, int b, StructDef d, string[] keys, string prefix)
        {
            foreach (Field f in d.Fields)
            {
                int at = b + f.Off;
                string path = prefix + f.Name;
                if (Decompiler.IsScalar(f.Type))
                {
                    object v;
                    if (D != null && D.TryGet(keys, path, out v)) WriteScalar(n, at, f, v);
                }
                else if (f.Type == "kfp") ApplyDefaults(n, at, Schema.Defs["KFP"], keys, path + ".");
                else if (f.Type == "sub") ApplyDefaults(n, at, Schema.Defs[f.Arg], keys, path + ".");
            }
        }

        Node New(string kind, string[] keys)
        {
            StructDef d = Schema.Defs[kind];
            Node n = new Node(kind, d.Size);
            ApplyDefaults(n, 0, d, keys, "");
            return n;
        }

        void SetList(Node n, int at, Node arr, int count, int cap)
        {
            n.SetRef(at, arr, 0);
            n.W16(at + 8, (ushort)count);
            n.W16(at + 10, (ushort)cap);
        }

        Node BuildKeys(List<object> keys, int cap)
        {
            int count = keys.Count;
            if (cap < count) cap = count;
            if (cap == 0) return null;
            Node a = new Node("Array_Keyframe", cap * 0x20);
            a.ElemCount = count;
            float prev = 0;
            for (int i = 0; i < count; i++)
            {
                List<object> k = (List<object>)keys[i];
                int b = i * 0x20;
                float t = Json.ToFloat(k[0]);
                a.WF(b, t);
                int vo;
                if (k.Count >= 8)
                {
                    a.WF(b + 4, Json.ToFloat(k[1])); a.WF(b + 8, Json.ToFloat(k[2])); a.WF(b + 12, Json.ToFloat(k[3]));
                    vo = 4;
                }
                else
                {
                    a.WF(b + 4, i == 0 ? 0f : 1.0f / (t - prev));
                    vo = 1;
                }
                for (int c = 0; c < 4; c++) a.WF(b + 16 + c * 4, vo + c < k.Count ? Json.ToFloat(k[vo + c]) : 0f);
                prev = t;
            }
            return a;
        }

        void Apply(Node n, int b, StructDef d, JObj js, string[] keys, string prefix, HashSet<string> used)
        {
            bool top = used == null;
            if (top) used = new HashSet<string>();
            foreach (Field f in d.Fields)
            {
                int at = b + f.Off;
                string path = prefix + f.Name;
                object v = js.Get(f.Name);
                bool has = js.Has(f.Name);
                if (has) used.Add(f.Name);
                if (Decompiler.IsScalar(f.Type))
                {
                    if (has && v != null) WriteScalar(n, at, f, v);
                    continue;
                }
                switch (f.Type)
                {
                    case "str":
                        if (has) n.SetRef(at, v == null ? null : Node.MakeString(Convert.ToString(v)), 0);
                        break;
                    case "kfp":
                    {
                        if (!has) break;
                        JObj k = v as JObj;
                        if (k == null) { k = new JObj(); k.Add("keys", v); }
                        Apply(n, at, Schema.Defs["KFP"], k, keys, path + ".", null);
                        break;
                    }
                    case "sub":
                        if (has && v is JObj) Apply(n, at, Schema.Defs[f.Arg], (JObj)v, keys, path + ".", null);
                        break;
                    case "iptr":
                        if (has && v != null) pending.Add(new object[] { "iptr", n, at, (int)Json.ToDouble(v) });
                        break;
                    case "ptr":
                        ApplyPtr(n, at, f, js, has, v);
                        break;
                    case "hlist":
                    {
                        if (!has || v == null) break;
                        List<object> l = (List<object>)v;
                        used.Add(f.Name + "#cap");
                        int cap = js.Has(f.Name + "#cap") ? (int)js.Num(f.Name + "#cap", 0) : l.Count;
                        if (cap < l.Count) cap = l.Count;
                        Node a = new Node("HashArray", cap * 4);
                        a.ElemCount = l.Count;
                        for (int i = 0; i < l.Count; i++) a.W32(i * 4, ParseHash(l[i]));
                        SetList(n, at, cap == 0 ? null : a, l.Count, cap);
                        break;
                    }
                    case "list":
                    {
                        string key = f.Arg == "Keyframe" && f.Name == "Values" ? "keys" : f.Name;
                        used.Add(key);
                        used.Add(key + "#cap");
                        if (!js.Has(key)) { if (js.Has(key + "#cap")) n.W16(at + 10, (ushort)js.Num(key + "#cap", 0)); break; }
                        List<object> l = js.Arr(key) ?? new List<object>();
                        int cap = js.Has(key + "#cap") ? (int)js.Num(key + "#cap", 0) : l.Count;
                        if (cap < l.Count) cap = l.Count;
                        if (f.Arg == "Keyframe") { SetList(n, at, BuildKeys(l, cap), l.Count, cap); break; }
                        StructDef ed = Schema.Defs[f.Arg];
                        Node a = cap == 0 ? null : new Node("Array_" + f.Arg, cap * ed.Size);
                        for (int i = 0; i < l.Count; i++)
                        {
                            ApplyDefaults(a, i * ed.Size, ed, new string[] { f.Arg }, "");
                            Apply(a, i * ed.Size, ed, (JObj)l[i], new string[] { f.Arg }, "", null);
                        }
                        if (a != null) a.ElemCount = l.Count;
                        SetList(n, at, a, l.Count, cap);
                        break;
                    }
                    case "kplist":
                    {
                        List<int> offs = Decompiler.AutoKfpOffsets(d);
                        object doffs;
                        if (D != null && D.TryGet(keys, path + "#offsets", out doffs) && doffs is List<object>)
                        {
                            offs = new List<int>();
                            foreach (object x in (List<object>)doffs) offs.Add((int)Json.ToDouble(x));
                        }
                        int cap = offs.Count;
                        object dcap;
                        if (offs.Count > 0 && D != null && D.TryGet(keys, path + "#cap", out dcap)) cap = Math.Max(cap, (int)Json.ToDouble(dcap));
                        bool isNull = false;
                        if (has && v is JObj)
                        {
                            JObj k = (JObj)v;
                            offs = new List<int>();
                            foreach (object x in k.Arr("offsets")) offs.Add((int)Json.ToDouble(x));
                            cap = (int)k.Num("cap", offs.Count);
                            isNull = k.Has("null");
                        }
                        if (cap < offs.Count) cap = offs.Count;
                        if (cap == 0 || isNull) { SetList(n, at, null, offs.Count, cap); break; }
                        Node a = new Node("PtrArray", cap * 8);
                        a.ElemCount = offs.Count;
                        for (int i = 0; i < offs.Count; i++) if (offs[i] >= 0) a.SetRef(i * 8, n, b + offs[i]);
                        SetList(n, at, a, offs.Count, cap);
                        break;
                    }
                    case "plist":
                        ApplyPList(n, at, f, d, js, keys, path, used);
                        break;
                }
            }
            if (top)
                foreach (KeyValuePair<string, object> kv in js.Items)
                    if (!used.Contains(kv.Key) && kv.Key != "id" && kv.Key != "type" && kv.Key != "kind" && kv.Key != "inDict" && !kv.Key.StartsWith("_") && !kv.Key.StartsWith("$"))
                        Warn("unknown field '" + kv.Key + "' in " + d.Name);
        }

        void ApplyPtr(Node n, int at, Field f, JObj js, bool has, object v)
        {
            switch (f.Arg)
            {
                case "Root":
                    if (has && v == null) n.SetRef(at, null, 0); else n.SetRef(at, root, 0);
                    break;
                case "EmitterRule":
                case "ParticleRule":
                case "EffectRule":
                    if (has && v != null) pending.Add(new object[] { f.Arg, n, at, Convert.ToString(v) });
                    break;
                case "Domain":
                    if (has && v is JObj)
                    {
                        string[] keys = new string[] { "Domain@" + f.Name, "Domain" };
                        Node dn = New("Domain", keys);
                        Apply(dn, 0, Schema.Defs["Domain"], (JObj)v, keys, "", null);
                        n.SetRef(at, dn, 0);
                    }
                    break;
                case "EvolutionList":
                    if (has && v is JObj)
                    {
                        string[] keys = new string[] { "EvolutionList" };
                        Node en = New("EvolutionList", keys);
                        Apply(en, 0, Schema.Defs["EvolutionList"], (JObj)v, keys, "", null);
                        n.SetRef(at, en, 0);
                    }
                    break;
                case "Texture":
                    if (has && v != null)
                    {
                        Node t;
                        if (tex.TryGetValue(Convert.ToString(v), out t)) n.SetRef(at, t, 0);
                        else Warn("texture '" + v + "' is referenced but not declared in textures; left as an external reference");
                    }
                    break;
                case "Opaque":
                    if (has && v != null) Warn("model drawables are not rebuilt; a ptfx_model particle rule will draw nothing");
                    break;
            }
        }

        void ApplyPList(Node n, int at, Field f, StructDef d, JObj js, string[] keys, string path, HashSet<string> used)
        {
            used.Add(f.Name + "#cap");
            if (f.Arg == "Behaviour" && f.Name != "AllBehaviours")
            {
                Node all = n.Target(d.ByName["AllBehaviours"].Off);
                int allCount = n.U16(d.ByName["AllBehaviours"].Off + 8);
                List<int> idx;
                if (js.Has(f.Name))
                {
                    idx = new List<int>();
                    foreach (object x in js.Arr(f.Name)) idx.Add((int)Json.ToDouble(x));
                }
                else
                {
                    List<string> types = new List<string>();
                    for (int i = 0; i < allCount; i++) { Node x = all.Target(i * 8); types.Add(x == null ? "?" : x.Kind.Substring(4)); }
                    List<int> init = new List<int>(), update = new List<int>(), fin = new List<int>(), draw = new List<int>();
                    Decompiler.DeriveBehaviourLists(types, init, update, fin, draw);
                    idx = f.Name == "InitBehaviours" ? init : f.Name == "UpdateBehaviours" ? update : f.Name == "UpdateFinalizeBehaviours" ? fin : draw;
                }
                int bcap = js.Has(f.Name + "#cap") ? (int)js.Num(f.Name + "#cap", 0) : idx.Count;
                if (bcap < idx.Count) bcap = idx.Count;
                if (bcap == 0) { SetList(n, at, null, 0, 0); return; }
                Node arr = new Node("PtrArray", bcap * 8);
                arr.ElemCount = idx.Count;
                for (int i = 0; i < idx.Count; i++) if (idx[i] >= 0 && all != null) arr.SetRef(i * 8, all.Target(idx[i] * 8), 0);
                SetList(n, at, arr, idx.Count, bcap);
                return;
            }
            List<object> l = js.Arr(f.Name);
            if (f.Arg == "ShaderVar" && l == null) l = AutoVars(js);
            if (l == null)
            {
                if (js.Has(f.Name + "#cap")) n.W16(at + 10, (ushort)js.Num(f.Name + "#cap", 0));
                return;
            }
            int cap = l.Count;
            object dcap;
            if (f.Name == "EventEmitters" && D != null && D.TryGet(keys, path + "#cap", out dcap)) cap = Math.Max(cap, (int)Json.ToDouble(dcap));
            if (js.Has(f.Name + "#cap")) cap = Math.Max(l.Count, (int)js.Num(f.Name + "#cap", 0));
            Node a = cap == 0 ? null : new Node("PtrArray", cap * 8);
            if (a != null) a.ElemCount = l.Count;
            for (int i = 0; i < l.Count; i++)
            {
                JObj e = l[i] as JObj;
                if (e == null) continue;
                string kind = f.Arg;
                if (f.Arg == "Behaviour")
                {
                    kind = "Beh_" + e.Str("type");
                    if (!Schema.Defs.ContainsKey(kind)) throw new InvalidDataException("unknown behaviour type '" + e.Str("type") + "'");
                }
                else if (f.Arg == "ShaderVar")
                {
                    kind = "Var_" + e.Str("kind");
                    if (!Schema.Defs.ContainsKey(kind)) throw new InvalidDataException("unknown shader var kind '" + e.Str("kind") + "'");
                }
                string[] ck = new string[] { kind };
                Node c = New(kind, ck);
                if (f.Arg == "Behaviour") c.W32(8, Schema.BehaviourHash[e.Str("type")]);
                Apply(c, 0, Schema.Defs[kind], e, ck, "", null);
                if (kind == "EventEmitter" && !e.Has("Index")) c.W32(8, (uint)i);
                a.SetRef(i * 8, c, 0);
            }
            SetList(n, at, a, l.Count, cap);
        }

        List<object> AutoVars(JObj ptxSpec)
        {
            string shader = ptxSpec.Str("ShaderTemplateName") ?? "ptfx_sprite";
            string tech = ptxSpec.Str("ShaderTemplateTechniqueName") ?? "RGBA_soft";
            JObj set = D == null ? null : D.VarSets.Obj(shader + "|" + tech);
            if (set == null) throw new InvalidDataException("no shader var preset for " + shader + "|" + tech + "; give ShaderVars explicitly or pick a technique listed in ptfx-defaults.json");
            List<object> vars = (List<object>)Json.DeepClone(set.Arr("vars"));
            JObj over = ptxSpec.Obj("$vars");
            string texName = ptxSpec.Str("$texture");
            foreach (object vo in vars)
            {
                JObj v = (JObj)vo;
                string name = v.Str("Name");
                if (v.Str("kind") == "Texture" && name == "DiffuseTex2" && texName != null)
                {
                    v.Set("TextureName", texName);
                    v.Set("TextureNameHash", Decompiler.Hex(Jenkins.Hash(texName)));
                    if (tex.ContainsKey(texName)) { v.Set("Texture", texName); v.Set("ExternalReference", 0.0); }
                    else v.Set("ExternalReference", 1.0);
                }
                if (over != null && over.Has(name))
                {
                    object ov = over.Get(name);
                    if (ov is JObj) foreach (KeyValuePair<string, object> kv in ((JObj)ov).Items) v.Set(kv.Key, kv.Value);
                    else if (v.Str("kind") == "Vector")
                    {
                        List<object> vec = ov as List<object> ?? new List<object> { ov };
                        while (vec.Count < 4) vec.Add(0.0);
                        v.Set("Vector", vec);
                    }
                    else if (v.Str("kind") == "Keyframe")
                    {
                        List<object> items = new List<object>();
                        List<object> rawList = ov as List<object>;
                        if (rawList != null && rawList.Count > 0)
                        {
                            double prevT = 0;
                            for (int ki = 0; ki < rawList.Count; ki++)
                            {
                                JObj rawObj = rawList[ki] as JObj;
                                if (rawObj != null) { items.Add(rawObj); continue; }
                                List<object> pair = rawList[ki] as List<object>;
                                if (pair != null && pair.Count >= 2)
                                {
                                    double kt = Json.ToDouble(pair[0]), kv2 = Json.ToDouble(pair[1]);
                                    JObj it = new JObj();
                                    it.Add("U0", kt);
                                    it.Add("U4", ki == 0 || kt <= prevT ? 0.0 : 1.0 / (kt - prevT));
                                    it.Add("U10", kv2);
                                    items.Add(it);
                                    prevT = kt;
                                }
                            }
                        }
                        if (items.Count == 0)
                        {
                            JObj it = new JObj();
                            it.Add("U10", ov);
                            items.Add(it);
                        }
                        v.Set("Items", items);
                    }
                }
            }
            return vars;
        }

        Node BuildDict(string kind, List<KeyValuePair<string, Node>> items, JObj fields)
        {
            Node d = New(kind, new string[] { "Dict" });
            if (fields != null) Apply(d, 0, Schema.Defs["Dict_ParticleRule"], fields, new string[] { "Dict" }, "", new HashSet<string>());
            items.Sort(delegate (KeyValuePair<string, Node> a, KeyValuePair<string, Node> b) { return Jenkins.Hash(a.Key).CompareTo(Jenkins.Hash(b.Key)); });
            int c = items.Count;
            if (c == 0) return d;
            Node h = new Node("HashArray", c * 4);
            Node p = new Node("PtrArray", c * 8);
            h.ElemCount = c;
            p.ElemCount = c;
            for (int i = 0; i < c; i++)
            {
                h.W32(i * 4, Jenkins.Hash(items[i].Key));
                p.SetRef(i * 8, items[i].Value, 0);
            }
            SetList(d, 0x20, h, c, c);
            SetList(d, 0x30, p, c, c);
            return d;
        }

        TexPayload FromSource(string path, string name)
        {
            YptFile y;
            if (!sourceCache.TryGetValue(path, out y)) { y = YptFile.Parse(path); sourceCache[path] = y; }
            foreach (Node n in y.Nodes)
            {
                if (n.Kind != "Texture" || !string.Equals(n.Label, name, StringComparison.OrdinalIgnoreCase)) continue;
                TexPayload p = new TexPayload();
                p.Width = n.U16(0x50); p.Height = n.U16(0x52); p.Stride = n.U16(0x56); p.Format = n.U32(0x58); p.Levels = n.Data[0x5D];
                Node dn = n.Target(0x70);
                p.Data = dn == null ? new byte[0] : dn.Data;
                return p;
            }
            throw new InvalidDataException("texture '" + name + "' not found in " + path);
        }

        public Node Run(JObj spec)
        {
            root = New("Root", new string[] { "Root" });
            if (spec.Obj("root") != null) Apply(root, 0, Schema.Defs["Root"], spec.Obj("root"), new string[] { "Root" }, "", new HashSet<string>());
            root.SetRef(0x10, Node.MakeString(spec.Str("name") ?? "ptfx"), 0);
            Node pm = New("PageMap", new string[] { "PageMap" });
            if (spec.Obj("pageMap") != null) Apply(pm, 0, Schema.Defs["PageMap"], spec.Obj("pageMap"), new string[] { "PageMap" }, "", null);
            root.SetRef(0x08, pm, 0);
            JObj dj = spec.Obj("dicts") ?? new JObj();

            List<KeyValuePair<string, Node>> texItems = new List<KeyValuePair<string, Node>>();
            List<object> tl = spec.Arr("textures") ?? new List<object>();
            foreach (object o in tl)
            {
                JObj tj = (JObj)o;
                string name = tj.Str("name");
                TexPayload p;
                JObj data = tj.Obj("data");
                if (data != null && data.Has("from")) p = FromSource(data.Str("from"), data.Str("name") ?? name);
                else if (TextureProvider != null) p = TextureProvider(tj, name);
                else throw new InvalidDataException("texture '" + name + "' has no data source");
                Node t = New("Texture", new string[] { "Texture" });
                if (tj.Obj("fields") != null) Apply(t, 0, Schema.Defs["Texture"], tj.Obj("fields"), new string[] { "Texture" }, "", null);
                t.SetRef(0x28, Node.MakeString(name), 0);
                t.W16(0x50, (ushort)p.Width); t.W16(0x52, (ushort)p.Height); t.W16(0x56, (ushort)p.Stride); t.W32(0x58, p.Format); t.Data[0x5D] = (byte)p.Levels;
                if (t.U16(0x54) == 0) t.W16(0x54, 1);
                Node dn = new Node("TexData", p.Data.Length);
                dn.Gfx = true;
                Buffer.BlockCopy(p.Data, 0, dn.Data, 0, p.Data.Length);
                t.SetRef(0x70, dn, 0);
                t.Label = name;
                if (tex.ContainsKey(name)) throw new InvalidDataException("duplicate texture name '" + name + "'");
                tex[name] = t;
                texItems.Add(new KeyValuePair<string, Node>(name, t));
            }
            if (!(dj.Has("TexDict") && dj.Get("TexDict") == null)) root.SetRef(0x20, BuildDict("TexDict", texItems, dj.Obj("TexDict")), 0);
            if (!(dj.Has("DrawDict") && dj.Get("DrawDict") == null)) root.SetRef(0x30, BuildDict("DrawDict", new List<KeyValuePair<string, Node>>(), dj.Obj("DrawDict")), 0);
            if (spec.Has("drawables")) Warn("model drawables listed in the spec are dropped; ptfx_model rules will draw nothing");

            List<KeyValuePair<string, Node>> ptxItems = new List<KeyValuePair<string, Node>>();
            foreach (object o in spec.Arr("particles") ?? new List<object>())
            {
                JObj pj = (JObj)o;
                string[] keys = new string[] { "ParticleRule|" + (pj.Str("ShaderTemplateName") ?? "ptfx_sprite") + "|" + (pj.Str("ShaderTemplateTechniqueName") ?? "RGBA_soft"), "ParticleRule" };
                Node n = New("ParticleRule", keys);
                if (!pj.Has("ShaderTemplateName")) pj.Set("ShaderTemplateName", "ptfx_sprite");
                if (!pj.Has("ShaderTemplateTechniqueName")) pj.Set("ShaderTemplateTechniqueName", "RGBA_soft");
                Apply(n, 0, Schema.Defs["ParticleRule"], pj, keys, "", null);
                string id = pj.Str("id") ?? pj.Str("Name");
                if (ptx.ContainsKey(id)) throw new InvalidDataException("duplicate particle rule id '" + id + "'");
                ptx[id] = n;
                if (!(pj.Has("inDict") && pj.Get("inDict") is bool && !(bool)pj.Get("inDict"))) ptxItems.Add(new KeyValuePair<string, Node>(pj.Str("Name") ?? id, n));
            }
            List<KeyValuePair<string, Node>> emitItems = new List<KeyValuePair<string, Node>>();
            foreach (object o in spec.Arr("emitters") ?? new List<object>())
            {
                JObj ej = (JObj)o;
                Node n = New("EmitterRule", new string[] { "EmitterRule" });
                Apply(n, 0, Schema.Defs["EmitterRule"], ej, new string[] { "EmitterRule" }, "", null);
                string id = ej.Str("id") ?? ej.Str("Name");
                if (emit.ContainsKey(id)) throw new InvalidDataException("duplicate emitter rule id '" + id + "'");
                emit[id] = n;
                if (!(ej.Has("inDict") && ej.Get("inDict") is bool && !(bool)ej.Get("inDict"))) emitItems.Add(new KeyValuePair<string, Node>(ej.Str("Name") ?? id, n));
            }
            List<KeyValuePair<string, Node>> effItems = new List<KeyValuePair<string, Node>>();
            foreach (object o in spec.Arr("effects") ?? new List<object>())
            {
                JObj ej = (JObj)o;
                Node n = New("EffectRule", new string[] { "EffectRule" });
                Apply(n, 0, Schema.Defs["EffectRule"], ej, new string[] { "EffectRule" }, "", null);
                string id = ej.Str("id") ?? ej.Str("Name");
                if (eff.ContainsKey(id)) throw new InvalidDataException("duplicate effect rule id '" + id + "'");
                eff[id] = n;
                effItems.Add(new KeyValuePair<string, Node>(ej.Str("Name") ?? id, n));
            }
            foreach (object[] p in pending)
            {
                string what = (string)p[0];
                Node n = (Node)p[1];
                int at = (int)p[2];
                if (what == "iptr") continue;
                Dictionary<string, Node> map = what == "EmitterRule" ? emit : what == "ParticleRule" ? ptx : eff;
                Node t;
                if (map.TryGetValue((string)p[3], out t)) n.SetRef(at, t, 0);
                else Warn(what + " '" + p[3] + "' is referenced but not defined in this spec");
            }
            ResolveEvoMaps();

            bool effectInB = spec.Str("effectSlot") == "B";
            Node pd = (dj.Has("Dict_ParticleRule") && dj.Get("Dict_ParticleRule") == null) ? null : BuildDict("Dict_ParticleRule", ptxItems, dj.Obj("Dict_ParticleRule"));
            Node ed = (dj.Has("Dict_EffectRule") && dj.Get("Dict_EffectRule") == null) ? null : BuildDict("Dict_EffectRule", effItems, dj.Obj("Dict_EffectRule"));
            Node md = (dj.Has("Dict_EmitterRule") && dj.Get("Dict_EmitterRule") == null) ? null : BuildDict("Dict_EmitterRule", emitItems, dj.Obj("Dict_EmitterRule"));
            root.SetRef(0x38, pd, 0);
            root.SetRef(0x48, effectInB ? md : ed, 0);
            root.SetRef(0x50, effectInB ? ed : md, 0);
            return root;
        }

        void ResolveEvoMaps()
        {
            foreach (Node n in YptWriter.Reachable(root))
            {
                if (n.Kind != "EvolutionList") continue;
                Node props = n.Target(0x10);
                Node map = n.Target(0x28);
                if (map == null) continue;
                foreach (object[] p in pending)
                {
                    if ((string)p[0] != "iptr" || p[1] != map) continue;
                    if (props == null) { Warn("evolution map entry has no keyframe prop list to point at"); continue; }
                    map.SetRef((int)p[2], props, (int)p[3] * 24);
                }
            }
        }
    }

    public static class YptCheck
    {
        public static Dictionary<string, int> Fingerprint(YptFile y)
        {
            Dictionary<string, int> fp = new Dictionary<string, int>();
            HashSet<string> strings = new HashSet<string>();
            using (MD5 md5 = MD5.Create())
            {
                foreach (Node n in YptWriter.Reachable(y.Root))
                {
                    byte[] d = (byte[])n.Data.Clone();
                    foreach (Ref r in n.Refs) for (int i = 0; i < 8; i++) d[r.At + i] = 0;
                    if (n.Kind == "PageMap") { d[8] = 0; d[9] = 0; }
                    string kind = n.Kind.StartsWith("Dict_") ? "Dict" : n.Kind;
                    string key = kind + ":" + BitConverter.ToString(md5.ComputeHash(d)).Replace("-", "").Substring(0, 12) + ":" + d.Length;
                    if (kind == "PtrArray") key = "PtrArray:" + n.ElemCount;
                    if (kind == "String") { if (!strings.Add(key)) continue; }
                    int c;
                    fp.TryGetValue(key, out c);
                    fp[key] = c + 1;
                }
            }
            return fp;
        }

        public static string Compare(YptFile a, YptFile b)
        {
            Dictionary<string, int> fa = Fingerprint(a), fb = Fingerprint(b);
            Dictionary<string, int> diff = new Dictionary<string, int>();
            foreach (KeyValuePair<string, int> kv in fa)
            {
                int c;
                fb.TryGetValue(kv.Key, out c);
                if (c != kv.Value) { string k = kv.Key.Substring(0, kv.Key.IndexOf(':')); int x; diff.TryGetValue(k, out x); diff[k] = x + Math.Abs(kv.Value - c); }
            }
            foreach (KeyValuePair<string, int> kv in fb)
            {
                if (fa.ContainsKey(kv.Key)) continue;
                string k = kv.Key.Substring(0, kv.Key.IndexOf(':'));
                int x;
                diff.TryGetValue(k, out x);
                diff[k] = x + kv.Value;
            }
            if (diff.Count == 0) return "";
            StringBuilder sb = new StringBuilder();
            foreach (KeyValuePair<string, int> kv in diff) sb.Append(kv.Key).Append('=').Append(kv.Value).Append(' ');
            return sb.ToString().Trim();
        }
    }
}
