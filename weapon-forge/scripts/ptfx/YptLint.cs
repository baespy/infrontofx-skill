using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace WeaponForge
{
    // Corpus knowledge used to judge a new dictionary: for every field of every struct, the values real files use.
    // Built by "ptfx.ps1 ranges", stored in ptfx-ranges.json, read by "ptfx.ps1 lint" and by every build.
    public class RangeBuilder
    {
        class Stat
        {
            public int N;
            public double Min = double.MaxValue, Max = double.MinValue;
            public bool AllInt = true;
            public Dictionary<double, int> Vals = new Dictionary<double, int>();
            public List<float> Samples = new List<float>();
        }

        Dictionary<string, Stat> stats = new Dictionary<string, Stat>(StringComparer.Ordinal);
        Dictionary<string, int> gameTex = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        HashSet<string> gameEffects = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        Dictionary<string, int> behSets = new Dictionary<string, int>();
        public int Files;

        public static bool IsNumber(object o)
        {
            return o is double || o is float || o is int || o is uint || o is long || o is ulong || o is short || o is ushort || o is byte || o is sbyte || o is bool;
        }

        void Put(string path, double v)
        {
            if (double.IsNaN(v) || double.IsInfinity(v)) return;
            Stat s;
            if (!stats.TryGetValue(path, out s)) { s = new Stat(); stats[path] = s; }
            s.N++;
            if (v < s.Min) s.Min = v;
            if (v > s.Max) s.Max = v;
            if (v != Math.Floor(v)) s.AllInt = false;
            if (s.Vals != null)
            {
                int c;
                s.Vals.TryGetValue(v, out c);
                s.Vals[v] = c + 1;
                if (s.Vals.Count > 24) s.Vals = null;
            }
            s.Samples.Add((float)v);
        }

        public delegate void Visit(string path, double value);

        public static bool SkipKey(string k)
        {
            return k == "id" || k == "keys" || k.IndexOf('#') >= 0 || k == "Name" || k == "TextureNameHash" || k == "offsets" || k == "RandomIndex";
        }

        public static string Discriminator(JObj el)
        {
            string t = el.Str("type");
            if (t != null) return t;
            string k = el.Str("kind");
            if (k != null) return k + ":" + el.Str("Name");
            return null;
        }

        // One walker for both sides, so the builder and the linter can never disagree about a path.
        public static void Walk(JObj o, string path, Visit visit)
        {
            foreach (KeyValuePair<string, object> kv in o.Items)
            {
                string k = kv.Key;
                object v = kv.Value;
                if (v == null || SkipKey(k)) continue;
                string p = path + "." + k;
                JObj child = v as JObj;
                if (child != null)
                {
                    List<object> keys = child.Arr("keys");
                    if (k.EndsWith("KFP") || keys != null)
                    {
                        visit(p + "#count", keys == null ? 0 : keys.Count);
                        if (keys != null)
                            foreach (object ko in keys)
                            {
                                List<object> kk = ko as List<object>;
                                if (kk == null) continue;
                                int vo = kk.Count >= 8 ? 4 : 1;
                                visit(p + "#t", Json.ToDouble(kk[0]));
                                for (int c = 0; c < 4 && vo + c < kk.Count; c++) visit(p + "#c" + c, Json.ToDouble(kk[vo + c]));
                            }
                    }
                    Walk(child, p, visit);
                    continue;
                }
                List<object> list = v as List<object>;
                if (list != null)
                {
                    for (int i = 0; i < list.Count; i++)
                    {
                        JObj el = list[i] as JObj;
                        if (el != null) { string d = Discriminator(el); Walk(el, p + (d != null ? "<" + d + ">" : "[]"), visit); }
                        else if (IsNumber(list[i]) && list.Count <= 4) visit(p + "[" + i + "]", Json.ToDouble(list[i]));
                    }
                    continue;
                }
                if (IsNumber(v)) { visit(p, Json.ToDouble(v)); continue; }
                string s = v as string;
                if (s != null && s.StartsWith("0x") && s.Length <= 10) { try { visit(p, Json.ToDouble(s)); } catch { } }
            }
        }

        public static string TextureOf(JObj pr)
        {
            foreach (object vo in pr.Arr("ShaderVars") ?? new List<object>())
            {
                JObj v = vo as JObj;
                if (v != null && v.Str("kind") == "Texture" && v.Str("Name") == "DiffuseTex2")
                {
                    string n = v.Str("TextureName") ?? v.Str("Texture");
                    return string.IsNullOrEmpty(n) ? null : n;
                }
            }
            return pr.Str("$texture");
        }

        public static JObj Beh(JObj pr, string type)
        {
            foreach (object bo in pr.Arr("AllBehaviours") ?? new List<object>()) { JObj b = bo as JObj; if (b != null && b.Str("type") == type) return b; }
            return null;
        }

        public void Add(YptFile y, bool isGameCore)
        {
            Decompiler dc = new Decompiler(y, null);
            dc.Full = true;
            JObj spec = dc.Run();
            Files++;
            Visit put = delegate (string p, double v) { Put(p, v); };
            foreach (object o in spec.Arr("effects") ?? new List<object>()) { JObj e = (JObj)o; Walk(e, "Effect", put); if (isGameCore) gameEffects.Add(e.Str("Name") ?? ""); }
            foreach (object o in spec.Arr("emitters") ?? new List<object>()) Walk((JObj)o, "Emitter", put);
            foreach (object o in spec.Arr("particles") ?? new List<object>())
            {
                JObj p = (JObj)o;
                Walk(p, "Particle", put);
                StringBuilder set = new StringBuilder();
                foreach (object bo in p.Arr("AllBehaviours") ?? new List<object>()) { JObj b = bo as JObj; if (b != null) { if (set.Length > 0) set.Append(' '); set.Append(b.Str("type")); } }
                int c;
                behSets.TryGetValue(set.ToString(), out c);
                behSets[set.ToString()] = c + 1;
                if (!isGameCore) continue;
                string tn = TextureOf(p);
                if (tn == null) continue;
                int frames = (int)p.Num("TexFrameIDMax", 0);
                JObj an = Beh(p, "AnimateTexture");
                if (an != null) frames = Math.Max(frames, (int)an.Num("LastFrameID", 0));
                int had;
                gameTex.TryGetValue(tn, out had);
                gameTex[tn] = Math.Max(had, frames);
            }
            if (isGameCore)
                foreach (object o in spec.Arr("textures") ?? new List<object>()) { string n = ((JObj)o).Str("name"); if (n != null && !gameTex.ContainsKey(n)) gameTex[n] = 0; }
        }

        static string N(double v)
        {
            if (v == Math.Floor(v) && Math.Abs(v) < 1e15) return ((long)v).ToString(CultureInfo.InvariantCulture);
            return Json.FloatStr((float)v);
        }

        public string Finish()
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{\n\"format\": \"weapon-forge-ptfx-ranges/1\",\n\"files\": ").Append(Files).Append(",\n\"gameTextures\": {");
            List<string> names = new List<string>(gameTex.Keys);
            names.Sort(StringComparer.Ordinal);
            for (int i = 0; i < names.Count; i++) sb.Append(i > 0 ? ", " : "").Append('"').Append(names[i]).Append("\": ").Append(gameTex[names[i]]);
            sb.Append("},\n\"gameEffects\": [");
            names = new List<string>(gameEffects);
            names.Sort(StringComparer.Ordinal);
            for (int i = 0; i < names.Count; i++) sb.Append(i > 0 ? ", " : "").Append('"').Append(names[i]).Append('"');
            sb.Append("],\n\"behaviourSets\": {");
            List<KeyValuePair<string, int>> bl = new List<KeyValuePair<string, int>>(behSets);
            bl.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b) { return b.Value.CompareTo(a.Value); });
            for (int i = 0; i < bl.Count; i++) sb.Append(i > 0 ? ",\n" : "\n").Append('"').Append(bl[i].Key).Append("\": ").Append(bl[i].Value);
            sb.Append("\n},\n\"fields\": {");
            names = new List<string>(stats.Keys);
            names.Sort(StringComparer.Ordinal);
            bool first = true;
            foreach (string n in names)
            {
                Stat s = stats[n];
                s.Samples.Sort();
                int c = s.Samples.Count;
                double p1 = s.Samples[(int)(c * 0.01)], p99 = s.Samples[Math.Min(c - 1, (int)(c * 0.99))];
                sb.Append(first ? "\n" : ",\n");
                first = false;
                sb.Append('"').Append(n).Append("\": [").Append(s.N).Append(", ").Append(N(s.Min)).Append(", ").Append(N(s.Max)).Append(", ").Append(N(p1)).Append(", ").Append(N(p99)).Append(", ");
                if (s.Vals == null) sb.Append("null");
                else
                {
                    List<double> vs = new List<double>(s.Vals.Keys);
                    vs.Sort();
                    sb.Append('[');
                    for (int i = 0; i < vs.Count; i++) sb.Append(i > 0 ? ", " : "").Append(N(vs[i]));
                    sb.Append(']');
                }
                sb.Append(']');
            }
            sb.Append("\n}\n}\n");
            return sb.ToString();
        }
    }

    public class Ranges
    {
        public class Field { public int N; public double Min, Max, P1, P99; public double[] Vals; }
        public Dictionary<string, Field> Fields = new Dictionary<string, Field>(StringComparer.Ordinal);
        public Dictionary<string, int> GameTextures = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public HashSet<string> GameEffects = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        public Dictionary<string, int> BehaviourSets = new Dictionary<string, int>();
        public int Files;

        public static Ranges Load(string path)
        {
            if (path == null || !File.Exists(path)) return null;
            JObj j = (JObj)Json.Parse(File.ReadAllText(path));
            Ranges r = new Ranges();
            r.Files = (int)j.Num("files", 0);
            JObj gt = j.Obj("gameTextures");
            if (gt != null) foreach (KeyValuePair<string, object> kv in gt.Items) r.GameTextures[kv.Key] = (int)Json.ToDouble(kv.Value);
            foreach (object o in j.Arr("gameEffects") ?? new List<object>()) r.GameEffects.Add(Convert.ToString(o));
            JObj bs = j.Obj("behaviourSets");
            if (bs != null) foreach (KeyValuePair<string, object> kv in bs.Items) r.BehaviourSets[kv.Key] = (int)Json.ToDouble(kv.Value);
            JObj f = j.Obj("fields");
            if (f != null)
                foreach (KeyValuePair<string, object> kv in f.Items)
                {
                    List<object> a = (List<object>)kv.Value;
                    Field fd = new Field();
                    fd.N = (int)Json.ToDouble(a[0]);
                    fd.Min = Json.ToDouble(a[1]); fd.Max = Json.ToDouble(a[2]); fd.P1 = Json.ToDouble(a[3]); fd.P99 = Json.ToDouble(a[4]);
                    List<object> vs = a[5] as List<object>;
                    if (vs != null) { fd.Vals = new double[vs.Count]; for (int i = 0; i < vs.Count; i++) fd.Vals[i] = Json.ToDouble(vs[i]); }
                    r.Fields[kv.Key] = fd;
                }
            return r;
        }
    }

    public class LintResult
    {
        public List<string> Errors = new List<string>(), Warnings = new List<string>(), Notes = new List<string>();
        public int FieldsChecked, FieldsUnknown;
        public string Summary()
        {
            return "LINT fields=" + FieldsChecked + " errors=" + Errors.Count + " warnings=" + Warnings.Count + " notes=" + Notes.Count;
        }
    }

    public static class Linter
    {
        static string F(double v) { return v.ToString("0.####", CultureInfo.InvariantCulture); }

        static List<object> KeysOf(object v) { JObj j = v as JObj; return j != null ? j.Arr("keys") : v as List<object>; }

        static double KV(List<object> key, int comp) { int vo = key.Count >= 8 ? 4 : 1; return vo + comp < key.Count ? Json.ToDouble(key[vo + comp]) : 0; }

        static double Peak(object kfp, int comp)
        {
            double m = 0;
            List<object> keys = KeysOf(kfp);
            if (keys != null) foreach (object k in keys) m = Math.Max(m, Math.Abs(KV((List<object>)k, comp)));
            return m;
        }

        static void Add(List<string> l, string s) { if (!l.Contains(s)) l.Add(s); }

        // Structural pass: every numeric field of the rebuilt file against what real files contain.
        static void RangePass(JObj spec, Ranges R, LintResult res)
        {
            Dictionary<string, string> worst = new Dictionary<string, string>();
            RangeBuilder.Visit check = delegate (string path, double v)
            {
                Ranges.Field f;
                res.FieldsChecked++;
                if (!R.Fields.TryGetValue(path, out f)) { res.FieldsUnknown++; Add(res.Warnings, "field " + path + " = " + F(v) + " does not occur in any real file"); return; }
                bool isKey = path.IndexOf('#') >= 0;
                if (f.Vals != null && !isKey)
                {
                    bool allInt = true;
                    foreach (double x in f.Vals) if (x != Math.Floor(x)) allInt = false;
                    bool found = false;
                    foreach (double x in f.Vals) if (Math.Abs(x - v) <= Math.Max(Math.Abs(x), 1) * 1e-5) found = true;
                    if (allInt && f.N >= 40 && !found)
                    {
                        StringBuilder sb = new StringBuilder();
                        foreach (double x in f.Vals) sb.Append(sb.Length > 0 ? "," : "").Append(F(x));
                        worst[path] = "value " + F(v) + " for " + path + " is never used by a real file (seen: " + sb + ")";
                        return;
                    }
                }
                double span = Math.Max(Math.Max(Math.Abs(f.Max), Math.Abs(f.Min)), 1e-3) * 1e-5;
                if (v < f.Min - span || v > f.Max + span)
                {
                    string cur;
                    if (!worst.TryGetValue(path, out cur)) worst[path] = path + " = " + F(v) + " is outside every real file (" + F(f.Min) + " to " + F(f.Max) + ")";
                }
            };
            foreach (object o in spec.Arr("effects") ?? new List<object>()) RangeBuilder.Walk((JObj)o, "Effect", check);
            foreach (object o in spec.Arr("emitters") ?? new List<object>()) RangeBuilder.Walk((JObj)o, "Emitter", check);
            foreach (object o in spec.Arr("particles") ?? new List<object>()) RangeBuilder.Walk((JObj)o, "Particle", check);
            foreach (string s in worst.Values) Add(res.Warnings, s);
        }

        static bool TimesOk(object kfp)
        {
            List<object> keys = KeysOf(kfp);
            if (keys == null) return true;
            double last = -1;
            foreach (object k in keys)
            {
                double t = Json.ToDouble(((List<object>)k)[0]);
                if (t < 0 || t > 1.0001 || t <= last) return false;
                last = t;
            }
            return true;
        }

        static void CheckTimes(JObj o, string where, LintResult res)
        {
            foreach (KeyValuePair<string, object> kv in o.Items)
            {
                JObj c = kv.Value as JObj;
                if (c != null)
                {
                    if (c.Arr("keys") != null && !TimesOk(c)) Add(res.Errors, where + "." + kv.Key + ": key times must rise strictly from 0 to 1");
                    CheckTimes(c, where + "." + kv.Key, res);
                }
                List<object> l = kv.Value as List<object>;
                if (l != null) foreach (object x in l) if (x is JObj) CheckTimes((JObj)x, where + "." + kv.Key, res);
            }
        }

        // Design pass: things that load fine but look wrong, cost too much, or silently draw nothing.
        static void DesignPass(JObj spec, Ranges R, LintResult res)
        {
            HashSet<string> own = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (object o in spec.Arr("textures") ?? new List<object>()) own.Add(((JObj)o).Str("name") ?? "");
            Dictionary<string, JObj> em = new Dictionary<string, JObj>(), pr = new Dictionary<string, JObj>();
            foreach (object o in spec.Arr("emitters") ?? new List<object>()) { JObj e = (JObj)o; em[e.Str("Name") ?? ""] = e; CheckTimes(e, "emitter " + e.Str("Name"), res); }
            foreach (object o in spec.Arr("particles") ?? new List<object>()) { JObj e = (JObj)o; pr[e.Str("Name") ?? ""] = e; CheckTimes(e, "particle " + e.Str("Name"), res); }
            string dict = spec.Str("name") ?? "";
            if (dict == "core" || dict.StartsWith("scr_") || dict.StartsWith("cut_") || dict.StartsWith("veh_") || dict.StartsWith("des_") || dict.StartsWith("proj_") || dict.StartsWith("wpn_"))
                Add(res.Errors, "dictionary name '" + dict + "' looks like a game dictionary; a file with that name replaces the game's own effects");

            foreach (KeyValuePair<string, JObj> kv in pr)
            {
                JObj p = kv.Value;
                string where = "particle " + kv.Key;
                string tn = RangeBuilder.TextureOf(p);
                bool trail = RangeBuilder.Beh(p, "Trail") != null;
                bool model = (int)p.Num("DrawType", 0) == 1;
                JObj an = RangeBuilder.Beh(p, "AnimateTexture");
                int frameMax = (int)Math.Max(p.Num("TexFrameIDMax", 0), an == null ? 0 : an.Num("LastFrameID", 0));
                if (tn == null) { if (!model) Add(res.Errors, where + ": no texture"); }
                else if (own.Contains(tn))
                {
                    int cols, rows, known;
                    if (SpriteFx.GameGrid(tn, out cols, out rows))
                    {
                        if (frameMax > cols * rows - 1) Add(res.Errors, where + ": frame " + frameMax + " requested from '" + tn + "', whose grid is " + cols + "x" + rows + " (frames 0 to " + (cols * rows - 1) + ")");
                    }
                    else if (R != null && R.GameTextures.TryGetValue(tn, out known))
                    {
                        if (frameMax > known) Add(res.Warnings, where + ": frame " + frameMax + " requested from '" + tn + "', the game uses at most " + known);
                    }
                    else if (frameMax > 0) Add(res.Warnings, where + ": texture '" + tn + "' is embedded under a new name, so the game draws the whole image as one frame; frames/anim have no effect. Use a sheet (\"sheets\" in the design) for more than one frame");
                }
                else if (R != null)
                {
                    int frames;
                    if (!R.GameTextures.TryGetValue(tn, out frames)) Add(res.Errors, where + ": texture '" + tn + "' is neither embedded in this dictionary nor a texture of the game's core.ypt; it will draw as a blank square");
                    else if (frameMax > frames) Add(res.Warnings, where + ": frame " + frameMax + " requested from '" + tn + "', the game uses at most " + frames);
                }
                JObj sz = RangeBuilder.Beh(p, "Size");
                if (sz == null) Add(res.Errors, where + ": no Size behaviour");
                else if (Peak(sz.Get("WhdMaxKFP"), trail ? 1 : 0) <= 0 && Peak(sz.Get("WhdMaxKFP"), 1) <= 0) Add(res.Errors, where + ": size is zero at every key, nothing will be drawn");
                JObj col = RangeBuilder.Beh(p, "Colour");
                if (col == null) Add(res.Errors, where + ": no Colour behaviour");
                else
                {
                    if (Peak(col.Get("RGBAMaxKFP"), 3) <= 0 && Peak(col.Get("RGBAMinKFP"), 3) <= 0) Add(res.Errors, where + ": alpha is zero at every key, nothing will be drawn");
                    for (int c = 0; c < 4; c++) if (Peak(col.Get("RGBAMaxKFP"), c) > 1.0001 || Peak(col.Get("RGBAMinKFP"), c) > 1.0001) { Add(res.Warnings, where + ": colour component above 1; use emissive for brightness"); break; }
                    List<object> ck = KeysOf(col.Get("RGBAMaxKFP"));
                    if (ck != null && ck.Count > 0 && (int)p.Num("BlendSet", 0) == 0 && KV((List<object>)ck[ck.Count - 1], 3) > 0.05 && !trail)
                        Add(res.Notes, where + ": normal-blend layer still has alpha " + F(KV((List<object>)ck[ck.Count - 1], 3)) + " when it dies, so it pops out instead of fading");
                    if (Peak(col.Get("EmissiveIntensityKFP"), 0) > 150) Add(res.Notes, where + ": emissive " + F(Peak(col.Get("EmissiveIntensityKFP"), 0)) + " is above the p90 of real files (120); expect heavy bloom at night");
                }
                if (RangeBuilder.Beh(p, "Age") == null || RangeBuilder.Beh(p, "Velocity") == null) Add(res.Errors, where + ": Age and Velocity behaviours are present in every real particle rule");
            }

            foreach (object o in spec.Arr("effects") ?? new List<object>())
            {
                JObj e = (JObj)o;
                string name = e.Str("Name") ?? "";
                bool loop = e.Num("NumLoops", 0) != 0;
                double dur = e.Num("DurationMax", 0);
                if (R != null && R.GameEffects.Contains(name)) Add(res.Errors, "effect '" + name + "' has the same name as an effect of the game; prefix it with the set id");
                if (dur <= 0) Add(res.Errors, "effect '" + name + "': duration must be above 0");
                double alive = 0, tail = 0, area = 0;
                List<object> evs = e.Arr("EventEmitters") ?? new List<object>();
                foreach (object eo in evs)
                {
                    JObj ev = eo as JObj;
                    if (ev == null) continue;
                    double st = ev.Num("StartRatio", 0), en = ev.Num("EndRatio", 1);
                    string en1 = ev.Str("EmitterRuleName") ?? ev.Str("EmitterRule"), pn1 = ev.Str("ParticleRuleName") ?? ev.Str("ParticleRule");
                    string where = "effect '" + name + "' layer " + pn1;
                    if (st < 0 || st >= 1) Add(res.Errors, where + ": start " + F(st) + " must be 0 or more and below 1");
                    if (en <= st) Add(res.Errors, where + ": end " + F(en) + " must be after start " + F(st));
                    JObj E, P;
                    if (en1 == null || !em.TryGetValue(en1, out E)) { Add(res.Errors, where + ": emitter rule '" + en1 + "' is missing"); continue; }
                    if (pn1 == null || !pr.TryGetValue(pn1, out P)) { Add(res.Errors, where + ": particle rule '" + pn1 + "' is missing"); continue; }
                    bool one = E.Num("IsOneShot", 0) != 0;
                    double rate = Peak(E.Get("SpawnRateOverTimeKFP"), 1), rateMin = Peak(E.Get("SpawnRateOverTimeKFP"), 0);
                    rate = Math.Max(rate, rateMin);
                    double life = Math.Max(Peak(E.Get("ParticleLifeKFP"), 0), Peak(E.Get("ParticleLifeKFP"), 1));
                    double speed = Math.Max(Peak(E.Get("SpeedScalarKFP"), 0), Peak(E.Get("SpeedScalarKFP"), 1));
                    double window = Math.Max(0, Math.Min(en, 1) - st) * dur;
                    if (rate <= 0 && Peak(E.Get("SpawnRateOverDistKFP"), 1) <= 0) Add(res.Errors, where + ": spawn count is zero");
                    if (life <= 0) Add(res.Errors, where + ": particle life is zero");
                    if (!one && rate > 0 && rate * window < 1) Add(res.Warnings, where + ": " + F(rate) + " per second for " + F(window) + " s emits less than one particle; raise rate or use burst");
                    double n = one ? rate : rate * Math.Min(life, loop ? life : window);
                    alive += n;
                    tail = Math.Max(tail, st * dur + (one ? 0 : window) + life);
                    JObj sp = RangeBuilder.Beh(P, "Sprite"), sz = RangeBuilder.Beh(P, "Size");
                    if (sp != null && (int)sp.Num("AlignmentMode", 0) == 1 && speed <= 0.0001 && RangeBuilder.Beh(P, "Acceleration") == null)
                        Add(res.Warnings, where + ": velocity-aligned sprite on particles that never move has no direction to align to; give it speed or use camera alignment");
                    if (sz != null)
                    {
                        double w = Peak(sz.Get("WhdMaxKFP"), 0), h = Peak(sz.Get("WhdMaxKFP"), 1);
                        double sc = Peak(E.Get("SizeScalarKFP"), 0);
                        if (sc > 0) { w *= sc / 100; h *= sc / 100; }
                        if ((int)P.Num("BlendSet", 0) == 1) area += n * w * h;
                        if (Math.Max(w, h) > 8) Add(res.Warnings, where + ": sprite reaches " + F(Math.Max(w, h)) + " m; Lua scale multiplies this again");
                        if (Math.Max(w, h) > 0 && Math.Max(w, h) < 0.004) Add(res.Warnings, where + ": sprite is under 4 mm and will not be visible");
                    }
                    if (life > 8) Add(res.Notes, where + ": particles live " + F(life) + " s; they keep drawing after the weapon is put away");
                }
                int budget = loop ? 60 : dur <= 1 ? 80 : 160;
                if (alive > budget * 2) Add(res.Warnings, "effect '" + name + "': about " + Math.Round(alive) + " particles alive at once, more than twice the " + budget + " budget for this kind of effect");
                else if (alive > budget) Add(res.Notes, "effect '" + name + "': about " + Math.Round(alive) + " particles alive at once (budget " + budget + ")");
                if (area > 40) Add(res.Notes, "effect '" + name + "': additive layers cover about " + Math.Round(area) + " m2 of screen-facing area; overlapping additive sprites wash out to white");
                if (!loop && tail > 6) Add(res.Notes, "effect '" + name + "': the last particle dies about " + F(tail) + " s after the trigger");
                if (evs.Count > 7) Add(res.Errors, "effect '" + name + "': " + evs.Count + " layers. No effect in any real file, the game's own core.ypt included, has more than 7; split it into two effects and call both from Lua");
            }
        }

        public static LintResult Check(JObj levelOneSpec, JObj fullSpecFromFile, Ranges R)
        {
            LintResult res = new LintResult();
            DesignPass(fullSpecFromFile ?? levelOneSpec, R, res);
            if (R != null && fullSpecFromFile != null) RangePass(fullSpecFromFile, R, res);
            return res;
        }

        public static LintResult CheckFile(string yptPath, Ranges R)
        {
            YptFile y = YptFile.Parse(yptPath);
            Decompiler d = new Decompiler(y, null);
            d.Full = true;
            JObj full = d.Run();
            LintResult res = Check(null, full, R);
            string st = y.Status();
            if (st == "issues") res.Errors.Insert(0, "file structure has issues: " + y.Census().Replace("\n", " "));
            return res;
        }
    }
}
