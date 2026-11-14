using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;

namespace WeaponForge
{
    public class DesignCompiler
    {
        public const int MaxLayers = 7;
        public JObj BuiltinSheets;
        static readonly string[] BigSprites = new string[] { "rune", "slash", "smoke", "bolt", "crack", "claw", "magic_circle", "wing", "energy_slash", "shockwave", "swirl", "plasma", "fire", "nova",
            "impact", "web", "hexgrid", "lotus", "sakura", "tomoe", "card", "flare", "beam", "wisp", "ripple", "glitch", "eye", "gear", "ribbon_line", "lantern", "pumpkin", "anchor" };
        public JObj Archetypes;
        public List<string> Warnings = new List<string>();
        public List<string> Summary = new List<string>();
        JObj palette;
        string dict;
        List<object> textures = new List<object>(), effects = new List<object>(), emitters = new List<object>(), particles = new List<object>();
        Dictionary<string, JObj> texByName = new Dictionary<string, JObj>(StringComparer.OrdinalIgnoreCase);
        HashSet<string> ruleNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        JObj sheets;
        class SheetUse { public string Slot; public int Frames; public bool Flipbook; public bool Loops; }
        Dictionary<string, SheetUse> sheetUse = new Dictionary<string, SheetUse>(StringComparer.OrdinalIgnoreCase);
        HashSet<string> externalWanted = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        SheetUse lastSheet;

        public DesignCompiler(JObj archetypes) { Archetypes = archetypes; }

        void Warn(string s) { if (!Warnings.Contains(s)) Warnings.Add(s); }

        static double D(object o) { return Json.ToDouble(o); }

        static double[] Range(object v, double defMin, double defMax)
        {
            if (v == null) return new double[] { defMin, defMax };
            List<object> l = v as List<object>;
            if (l == null) { double x = D(v); return new double[] { x, x }; }
            if (l.Count == 1) return new double[] { D(l[0]), D(l[0]) };
            return new double[] { D(l[0]), D(l[1]) };
        }

        static double[] Vec3(object v, double def)
        {
            if (v == null) return new double[] { def, def, def };
            List<object> l = v as List<object>;
            if (l == null) { double x = D(v); return new double[] { x, x, x }; }
            return new double[] { l.Count > 0 ? D(l[0]) : def, l.Count > 1 ? D(l[1]) : def, l.Count > 2 ? D(l[2]) : def };
        }

        static List<object> Key(double t, double a, double b, double c, double d)
        {
            return new List<object> { (float)t, (float)a, (float)b, (float)c, (float)d };
        }

        static List<object> One(double a, double b, double c, double d)
        {
            return new List<object> { Key(0, a, b, c, d) };
        }

        double[] Rgb(object v, double[] def)
        {
            if (v == null) return def;
            string s = Convert.ToString(v, CultureInfo.InvariantCulture);
            if (palette != null && palette.Has(s)) s = palette.Str(s);
            if (!s.StartsWith("#")) { Warn("colour '" + s + "' is neither a palette key nor #rrggbb; white used"); return new double[] { 1, 1, 1 }; }
            Color c = SpriteGen.ParseColor(s, Color.White);
            return new double[] { c.R / 255.0, c.G / 255.0, c.B / 255.0 };
        }

        string UniqueRule(string name)
        {
            string n = name;
            int k = 2;
            while (!ruleNames.Add(n)) n = name + "_" + (k++);
            return n;
        }

        // burst and rate are two ways to say how many: whichever the more specific level names replaces the other.
        static void Exclusive(JObj res, JObj over)
        {
            if ((over.Has("rate") || over.Has("rateOverDist") || over.Has("rateDistKeys")) && !over.Has("burst")) res.Remove("burst");
            if (over.Has("burst") && !over.Has("rate")) { res.Remove("rate"); res.Remove("rateOverDist"); res.Remove("rateDistKeys"); }
            if (over.Has("sizeKeys") && !over.Has("grow")) res.Remove("grow");
            if (over.Has("grow") && !over.Has("sizeKeys")) res.Remove("sizeKeys");
            if (over.Has("alphaKeys")) { if (!over.Has("fadeIn")) res.Remove("fadeIn"); if (!over.Has("fadeOut")) res.Remove("fadeOut"); }
            if ((over.Has("fadeIn") || over.Has("fadeOut") || over.Has("alpha")) && !over.Has("alphaKeys")) res.Remove("alphaKeys");
            if (over.Has("emissiveKeys") && !over.Has("emissive")) res.Remove("emissive");
            if (over.Has("emissive") && !over.Has("emissiveKeys")) res.Remove("emissiveKeys");
            if (over.Has("accelKeys")) { if (!over.Has("gravity")) res.Remove("gravity"); if (!over.Has("accel")) res.Remove("accel"); }
            if ((over.Has("gravity") || over.Has("accel")) && !over.Has("accelKeys")) res.Remove("accelKeys");
        }

        JObj Merge(JObj layer)
        {
            string use = layer.Str("use");
            JObj res = new JObj();
            if (use != null)
            {
                JObj a = Archetypes == null ? null : Archetypes.Obj(use);
                if (a == null) throw new InvalidDataException("unknown layer archetype '" + use + "'. Run ptfx.ps1 recipes to list them.");
                string parent = a.Str("use");
                if (parent != null && parent != use)
                {
                    JObj p = new JObj();
                    p.Add("use", parent);
                    foreach (KeyValuePair<string, object> kv in Merge(p).Items) res.Set(kv.Key, kv.Value);
                }
                Exclusive(res, a);
                foreach (KeyValuePair<string, object> kv in a.Items) if (kv.Key != "about" && kv.Key != "use") res.Set(kv.Key, Json.DeepClone(kv.Value));
            }
            Exclusive(res, layer);
            foreach (KeyValuePair<string, object> kv in layer.Items) if (kv.Key != "use") res.Set(kv.Key, kv.Value);
            if (use != null) res.Set("use", use);
            return res;
        }

        // Sprite colours may name a palette entry, the same as layer colours.
        void ResolveGenColours(JObj gen)
        {
            if (gen == null || palette == null) return;
            foreach (string k in new string[] { "color", "mid", "core" })
            {
                string v = gen.Str(k);
                if (v != null && !v.StartsWith("#") && palette.Has(v)) gen.Set(k, palette.Str(v));
            }
            foreach (string k in new string[] { "cells" })
                foreach (object o in gen.Arr(k) ?? new List<object>()) ResolveGenColours(o as JObj);
            ResolveGenColours(gen.Obj("flipbook"));
            ResolveGenColours(gen.Obj("sprite"));
        }

        bool IsSheet(string name)
        {
            return name != null && ((sheets != null && sheets.Has(name)) || (BuiltinSheets != null && BuiltinSheets.Has(name)));
        }

        SheetUse ResolveSheet(string name)
        {
            SheetUse u;
            if (sheetUse.TryGetValue(name, out u)) return u;
            JObj sh = (sheets != null && sheets.Has(name) ? sheets.Obj(name) : BuiltinSheets.Obj(name)).Clone();
            sh.Remove("about");
            ResolveGenColours(sh);
            int cols, rows;
            SpriteFx.ParseGrid(sh.Get("grid") ?? "2x2", out cols, out rows);
            SpriteFx.Slot slot = null;
            string wanted = sh.Str("slot");
            foreach (SpriteFx.Slot s in SpriteFx.Slots)
            {
                if (wanted != null ? !string.Equals(s.Name, wanted, StringComparison.OrdinalIgnoreCase) : (s.Cols != cols || s.Rows != rows)) continue;
                if (texByName.ContainsKey(s.Name) || externalWanted.Contains(s.Name)) continue;
                slot = s;
                break;
            }
            if (slot == null)
                throw new InvalidDataException("sheet '" + name + "': no free " + cols + "x" + rows + " slot. Grids available: 2x2, 3x3, 4x4, 5x5, 6x6, 7x7; each dictionary can hold only a few sheets of one grid (" + (wanted != null ? "slot '" + wanted + "' is unknown or taken" : "all are in use") + ").");
            if (slot.Cols != cols || slot.Rows != rows) { cols = slot.Cols; rows = slot.Rows; }
            List<object> cells = sh.Arr("cells");
            u = new SheetUse();
            u.Slot = slot.Name;
            JObj animate = sh.Obj("animate");
            bool variants = animate != null && animate.Count == 1 && animate.Has("seed");
            u.Flipbook = (cells == null || cells.Count == 0) && !variants;
            u.Frames = u.Flipbook ? (int)Math.Min(cols * rows, sh.Num("count", cols * rows)) : (sh.Num("repeat", 1) != 0 ? cols * rows : Math.Min(cols * rows, cells.Count));
            u.Loops = sh.Num("loop", 0) != 0;
            JObj tj = new JObj();
            tj.Add("name", slot.Name);
            tj.Add("sheet", sh);
            tj.Add("sheetName", name);
            textures.Add(tj);
            texByName[slot.Name] = tj;
            sheetUse[name] = u;
            return u;
        }

        string ResolveTexture(JObj L, out bool external, out string defaultTechnique)
        {
            string t = L.Str("texture") ?? "glow";
            external = false;
            defaultTechnique = "RGBA_soft";
            lastSheet = null;
            if (IsSheet(t)) { lastSheet = ResolveSheet(t); return lastSheet.Slot; }
            if (texByName.ContainsKey(t)) return t;
            if (Array.IndexOf(SpriteGen.Shapes, t) >= 0 && t != "image")
            {
                JObj gen = L.Obj("sprite") == null ? new JObj() : L.Obj("sprite").Clone();
                ResolveGenColours(gen);
                gen.Set("shape", t);
                if (!gen.Has("size")) gen.Set("size", Array.IndexOf(BigSprites, t) >= 0 ? 256.0 : 128.0);
                string key = dict + "_" + t;
                if (L.Obj("sprite") != null)
                {
                    string sig = Json.Write(gen, false);
                    int n = 2;
                    string cand = key;
                    while (texByName.ContainsKey(cand) && Json.Write(texByName[cand].Obj("gen"), false) != sig) cand = key + "_" + (n++);
                    key = cand;
                }
                if (!texByName.ContainsKey(key))
                {
                    JObj tj = new JObj();
                    tj.Add("name", key);
                    tj.Add("gen", gen);
                    textures.Add(tj);
                    texByName[key] = tj;
                }
                return key;
            }
            external = true;
            if (t.EndsWith("_rgb", StringComparison.OrdinalIgnoreCase) || t == "ptfx_glow" ) defaultTechnique = "RGB_soft";
            return t;
        }

        static void Kfp(JObj o, string name, List<object> keys) { o.Set(name, keys); }

        JObj Domain(int type, double[] pos, double[] rot, double[] outer, double[] inner, bool pointRel, bool world)
        {
            JObj d = new JObj();
            d.Add("DomainType", (double)type);
            d.Add("IsWorldSpace", world ? 1.0 : 0.0);
            d.Add("IsPointRelative", pointRel ? 1.0 : 0.0);
            if (pos[0] != 0 || pos[1] != 0 || pos[2] != 0) Kfp(d, "PositionKFP", One(pos[0], pos[1], pos[2], 0));
            if (rot[0] != 0 || rot[1] != 0 || rot[2] != 0) Kfp(d, "RotationKFP", One(rot[0], rot[1], rot[2], 0));
            Kfp(d, "SizeOuterKFP", One(outer[0], outer[1], outer[2], 0));
            Kfp(d, "SizeInnerKFP", One(inner[0], inner[1], inner[2], 0));
            return d;
        }

        static List<object> CurveKeys(object v, double def)
        {
            List<object> res = new List<object>();
            List<object> l = v as List<object>;
            if (l == null || l.Count == 0 || !(l[0] is List<object>)) { res.Add(new double[] { 0, v == null ? def : (l != null ? D(l[0]) : D(v)) }); if (l != null && l.Count > 1) res.Add(new double[] { 1, D(l[1]) }); return res; }
            foreach (object k in l) { List<object> kk = (List<object>)k; res.Add(new double[] { D(kk[0]), D(kk[1]) }); }
            return res;
        }

        void BuildLayer(JObj effect, List<object> events, JObj rawLayer, int index, double scale)
        {
            JObj L = Merge(rawLayer);
            string use = L.Str("use") ?? "layer";
            string baseName = UniqueRule(effect.Str("Name") + "_" + (L.Str("name") ?? use));
            double z = scale * L.Num("zoom", 1);

            bool external;
            string defTech;
            string tex = ResolveTexture(L, out external, out defTech);
            bool trail = L.Num("trail", 0) != 0 || (L.Get("trail") is bool && (bool)L.Get("trail"));
            bool lit = L.Get("lit") is bool ? (bool)L.Get("lit") : L.Num("lit", 0) != 0;
            string technique = L.Str("technique") ?? (lit ? "RGBA_lit_soft" : defTech);
            string blend = L.Str("blend") ?? (lit ? "normal" : "add");

            bool isBurst = L.Has("burst");
            bool hasDistSpawn = L.Has("rateOverDist") || L.Has("rateDistKeys");
            double defRate = isBurst ? 12 : (hasDistSpawn ? 0 : 20);
            double[] count = Range(isBurst ? L.Get("burst") : L.Get("rate"), defRate, defRate);
            double[] distRate = Range(L.Get("rateOverDist"), 0, 0);
            double[] life = Range(L.Get("life"), 0.5, 0.8);
            double[] speed = Range(L.Get("speed"), 0, 0);
            string shape = L.Str("shape") ?? "sphere";
            double[] radius = Vec3(L.Get("radius"), 0.02);
            double[] inner = Vec3(L.Get("inner"), 0);
            double[] offset = Vec3(L.Get("offset"), 0);
            double[] domRot = Vec3(L.Get("domainRot"), 0);
            for (int i = 0; i < 3; i++) { radius[i] *= z; inner[i] *= z; offset[i] *= z; }
            int dtype = shape == "box" ? 0 : shape == "cylinder" ? 2 : 1;

            JObj em = new JObj();
            em.Add("id", baseName);
            em.Add("Name", baseName);
            em.Add("IsOneShot", isBurst ? 1.0 : 0.0);
            em.Add("CreationDomain", Domain(dtype, offset, domRot, radius, inner, false, false));

            object dirv = L.Get("dir");
            string dir = dirv as string ?? (dirv == null ? "out" : "vector");
            double spread = L.Num("spread", 0.35);
            double dist = L.Num("distance", 1.0);
            double[] tpos = new double[] { 0, 0, 0 };
            double[] tout = new double[] { dist, dist, dist };
            double[] tin = new double[] { 0, 0, 0 };
            bool pointRel = true;
            switch (dir)
            {
                case "out": tout = new double[] { dist, dist, dist }; tin = new double[] { dist * 0.85, dist * 0.85, dist * 0.85 }; pointRel = L.Num("radialFromPoint", 1) != 0; break;
                case "in": tout = new double[] { 0.01, 0.01, 0.01 }; pointRel = false; break;
                case "up": tpos = new double[] { 0, 0, dist }; tout = new double[] { spread * dist, spread * dist, spread * dist }; break;
                case "down": tpos = new double[] { 0, 0, -dist }; tout = new double[] { spread * dist, spread * dist, spread * dist }; break;
                case "none": tout = new double[] { 0.01, 0.01, 0.01 }; break;
                case "vector":
                {
                    double[] v = Vec3(dirv, 0);
                    double len = Math.Sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
                    if (len < 1e-6) len = 1;
                    tpos = new double[] { v[0] / len * dist, v[1] / len * dist, v[2] / len * dist };
                    tout = new double[] { spread * dist, spread * dist, spread * dist };
                    break;
                }
                default: Warn("layer '" + use + "': dir '" + dir + "' is not out/in/up/down/none or a vector; 'out' used"); break;
            }
            em.Add("TargetDomain", Domain(1, tpos, new double[] { 0, 0, 0 }, tout, tin, pointRel, false));

            List<object> rateKeys = L.Arr("rateKeys");
            if (rateKeys != null)
            {
                List<object> rk = new List<object>();
                foreach (object k in rateKeys) { List<object> kk = (List<object>)k; rk.Add(Key(D(kk[0]), D(kk[1]), kk.Count > 2 ? D(kk[2]) : D(kk[1]), 0, 0)); }
                Kfp(em, "SpawnRateOverTimeKFP", rk);
            }
            else Kfp(em, "SpawnRateOverTimeKFP", One(count[0], count[1], 0, 0));
            List<object> rateDistKeys = L.Arr("rateDistKeys");
            if (rateDistKeys != null)
            {
                List<object> rdk = new List<object>();
                foreach (object k in rateDistKeys) { List<object> kk = (List<object>)k; rdk.Add(Key(D(kk[0]), D(kk[1]), kk.Count > 2 ? D(kk[2]) : D(kk[1]), 0, 0)); }
                Kfp(em, "SpawnRateOverDistKFP", rdk);
            }
            else if (distRate[0] > 0 || distRate[1] > 0) Kfp(em, "SpawnRateOverDistKFP", One(distRate[0], distRate[1], 0, 0));
            Kfp(em, "ParticleLifeKFP", One(life[0], life[1], 0.01, 0.01));
            Kfp(em, "PlaybackRateScalarKFP", One(L.Num("playback", 1), 0.01, 0.01, 0.01));
            Kfp(em, "SpeedScalarKFP", One(speed[0] * z, speed[1] * z, 0, 0));
            Kfp(em, "SizeScalarKFP", One(100, 100, 100, 0));
            emitters.Add(em);

            JObj pr = new JObj();
            pr.Add("id", baseName);
            pr.Add("Name", baseName);
            pr.Add("ShaderTemplateName", trail ? "ptfx_trail" : "ptfx_sprite");
            pr.Add("ShaderTemplateTechniqueName", technique);
            pr.Add("BlendSet", blend == "add" ? 1.0 : 0.0);
            if (trail) pr.Add("DrawType", 2.0);
            pr.Add("$texture", tex);
            SheetUse sheet = lastSheet;
            bool sheetOnce = sheet != null && sheet.Flipbook && !sheet.Loops && !(L.Get("anim") is string && L.Str("anim") != "once") && (L.Obj("anim") == null || L.Obj("anim").Str("mode") == "once" || L.Obj("anim").Str("mode") == null);
            double[] fr = Range(L.Get("frames"), 0, sheet == null || sheetOnce ? 0 : sheet.Frames - 1);
            pr.Add("TexFrameIDMin", fr[0]);
            pr.Add("TexFrameIDMax", fr[1]);
            if (L.Has("sort")) pr.Add("SortType", L.Num("sort", 2));
            else if (trail) pr.Add("SortType", 2.0);
            if (L.Has("lightingMode")) pr.Add("LightingMode", L.Num("lightingMode", 0));
            else if (!lit) pr.Add("LightingMode", 0.0);
            JObj vars = L.Obj("vars") != null ? (JObj)Json.DeepClone(L.Obj("vars")) : new JObj();
            if (!vars.Has("SuperAlpha")) vars.Set("SuperAlpha", L.Has("superAlpha") ? L.Get("superAlpha") : (lit ? (object)1.2 : (object)1.0));
            if (!lit)
            {
                if (!vars.Has("DirectionalMult")) vars.Set("DirectionalMult", 0.0);
                if (!vars.Has("AmbientMult")) vars.Set("AmbientMult", 0.0);
                if (!vars.Has("ExtraLightMult")) vars.Set("ExtraLightMult", 0.0);
            }
            if (L.Has("softness") && !vars.Has("Softness")) vars.Set("Softness", L.Get("softness"));
            if (vars.Items.Count > 0) pr.Add("$vars", vars);

            List<object> beh = new List<object>();
            JObj age = new JObj(); age.Add("type", "Age"); beh.Add(age);

            double gravity = L.Num("gravity", 0);
            double[] accel = Vec3(L.Get("accel"), 0);
            List<object> accelKeys = L.Arr("accelKeys");
            if (accelKeys != null && accelKeys.Count > 0)
            {
                JObj a = new JObj();
                a.Add("type", "Acceleration");
                double jitter = L.Num("accelJitter", 0.15);
                List<object> amin = new List<object>(), amax = new List<object>();
                foreach (object ko in accelKeys)
                {
                    List<object> kk = (List<object>)ko;
                    double kt = D(kk[0]);
                    double kx = kk.Count > 1 ? D(kk[1]) : 0;
                    double ky = kk.Count > 2 ? D(kk[2]) : 0;
                    double kz = kk.Count > 3 ? D(kk[3]) : 0;
                    amin.Add(Key(kt, kx * z * (1 - jitter), ky * z * (1 - jitter), kz * z * (1 - jitter), 0));
                    amax.Add(Key(kt, kx * z * (1 + jitter), ky * z * (1 + jitter), kz * z * (1 + jitter), 0));
                }
                Kfp(a, "XYZMinKFP", amin);
                Kfp(a, "XYZMaxKFP", amax);
                beh.Add(a);
            }
            else if (gravity != 0 || accel[0] != 0 || accel[1] != 0 || accel[2] != 0)
            {
                JObj a = new JObj();
                a.Add("type", "Acceleration");
                double jitter = L.Num("accelJitter", 0.15);
                double az = accel[2] - gravity;
                Kfp(a, "XYZMinKFP", One(accel[0] * z * (1 - jitter), accel[1] * z * (1 - jitter), az * z * (1 - jitter), 0));
                Kfp(a, "XYZMaxKFP", One(accel[0] * z * (1 + jitter), accel[1] * z * (1 + jitter), az * z * (1 + jitter), 0));
                beh.Add(a);
            }
            JObj vel = new JObj(); vel.Add("type", "Velocity"); beh.Add(vel);

            string align = L.Str("align") ?? "camera";
            double[] rot = Range(L.Get("rot"), align == "camera" ? -180 : 0, align == "camera" ? 180 : 0);
            double[] spin = Range(L.Get("spin"), 0, 0);
            if (rot[0] != 0 || rot[1] != 0 || spin[0] != 0 || spin[1] != 0)
            {
                JObj r = new JObj();
                r.Add("type", "Rotation");
                Kfp(r, "InitialAngleMinKFP", One(rot[0], 0, 0, 0));
                Kfp(r, "InitialAngleMaxKFP", One(rot[1], 0, 0, 0));
                if (spin[0] != 0 || spin[1] != 0)
                {
                    Kfp(r, "AngleMinKFP", One(spin[0], 0, 0, 0));
                    Kfp(r, "AngleMaxKFP", One(spin[1], 0, 0, 0));
                }
                beh.Add(r);
            }

            double[] size = Range(L.Get("size"), 0.1, 0.1);
            double aspect = L.Num("aspect", 1);
            List<object> sizeCurve = CurveKeys(L.Has("sizeKeys") ? L.Get("sizeKeys") : (L.Has("grow") ? (object)new List<object> { 1.0, L.Num("grow", 1) } : null), 1);
            JObj sz = new JObj();
            sz.Add("type", "Size");
            List<object> smin = new List<object>(), smax = new List<object>();
            foreach (object ko in sizeCurve)
            {
                double[] k = (double[])ko;
                if (trail)
                {
                    smin.Add(Key(k[0], 0, size[0] * k[1] * z, 0, 0));
                    smax.Add(Key(k[0], 0, size[1] * k[1] * z, 0, 0));
                    continue;
                }
                smin.Add(Key(k[0], size[0] * k[1] * z, size[0] * k[1] * z * aspect, 0, 0));
                smax.Add(Key(k[0], size[1] * k[1] * z, size[1] * k[1] * z * aspect, 0, 0));
            }
            Kfp(sz, "WhdMinKFP", smin);
            Kfp(sz, "WhdMaxKFP", smax);
            Kfp(sz, "TblrScalarKFP", One(1, 1, 1, 1));
            if (L.Has("stretch")) { double st = L.Num("stretch", 0); Kfp(sz, "TblrVelScalarKFP", One(st, st, 0, 0)); }
            beh.Add(sz);

            if (L.Has("drag"))
            {
                double[] dr = Range(L.Get("drag"), 1, 1);
                JObj d = new JObj();
                d.Add("type", "Dampening");
                Kfp(d, "XYZMinKFP", One(dr[0], dr[0], dr[0], 0));
                Kfp(d, "XYZMaxKFP", One(dr[1], dr[1], dr[1], 0));
                beh.Add(d);
            }

            if (!trail || L.Has("attach"))
            {
                List<object> wk = CurveKeys(L.Has("attach") ? L.Get("attach") : null, 0);
                JObj m = new JObj();
                m.Add("type", "MatrixWeight");
                List<object> keys = new List<object>();
                foreach (object ko in wk) { double[] k = (double[])ko; keys.Add(Key(k[0], k[1], k[1], 0, 0)); }
                Kfp(m, "MtxWeightKFP", keys);
                beh.Add(m);
            }

            // Animation presets follow the combinations the game's own rules use:
            //   loop   fire: random start frame, plays at fps and wraps        (ent_sht_flame, fire_wrecked_rc_flames)
            //   once   plays through at fps and holds the last frame           (ent_brk_blood_anim)
            //   random a new random frame at fps, for arcs and flicker         (exp_xs_ray_sparks)
            //   smoke  slow evolve scaled over the particle's life             (bul_glass_plume_sg and 250 others)
            JObj anim = L.Obj("anim");
            if (anim == null && L.Get("anim") is string) { anim = new JObj(); anim.Add("mode", L.Str("anim")); }
            if (anim == null && sheet != null && sheet.Flipbook) { anim = new JObj(); anim.Add("mode", sheet.Loops ? "loop" : "once"); }
            if (anim != null)
            {
                string mode = anim.Str("mode");
                int lastFrame = (int)anim.Num("last", sheet != null ? sheet.Frames - 1 : 3);
                double avgLife = Math.Max(0.05, (life[0] + life[1]) / 2);
                double[] fpsDef = mode == "once" ? new double[] { (lastFrame + 1) / avgLife, (lastFrame + 1) / avgLife } : mode == "smoke" ? new double[] { 6, 11 } : mode == "random" ? new double[] { 15, 15 } : new double[] { 18, 28 };
                double[] fps = Range(anim.Get("fps"), fpsDef[0], fpsDef[1]);
                double loopDef = 1, scaledDef = 0, holdDef = 0, randDef = 0;
                if (mode == "once") { loopDef = 0; holdDef = 1; }
                else if (mode == "random") { loopDef = 0; randDef = 1; }
                else if (mode == "smoke") { scaledDef = 1; holdDef = 1; }
                else if (mode != null && mode != "loop") Warn("layer '" + use + "': anim mode '" + mode + "' is not loop/once/random/smoke");
                JObj a = new JObj();
                a.Add("type", "AnimateTexture");
                Kfp(a, "AnimRateKFP", One(fps[0], fps[1], 0, 0));
                a.Add("LastFrameID", (double)lastFrame);
                a.Add("LoopMode", anim.Num("loop", loopDef));
                a.Add("IsScaledOverParticleLife", anim.Num("overLife", scaledDef));
                a.Add("IsRandomised", anim.Num("random", randDef));
                a.Add("IsHeldOnLastFrame", anim.Num("hold", holdDef));
                beh.Add(a);
            }

            {
                double[] c1 = Rgb(L.Get("color"), new double[] { 1, 1, 1 });
                double[] c2 = Rgb(L.Get("color2"), c1);
                double[] ce1 = Rgb(L.Get("colorEnd"), c1);
                double[] ce2 = L.Has("colorEnd") ? ce1 : c2;
                double alpha = L.Num("alpha", 1);
                double fin = L.Num("fadeIn", 0.08), fout = L.Num("fadeOut", 0.55);
                List<object> ak = L.Arr("alphaKeys");
                List<double[]> al = new List<double[]>();
                if (ak != null) foreach (object k in ak) { List<object> kk = (List<object>)k; al.Add(new double[] { D(kk[0]), D(kk[1]) }); }
                else
                {
                    if (fin > 0) al.Add(new double[] { 0, 0 });
                    al.Add(new double[] { fin, alpha });
                    if (fout > fin && fout < 1) al.Add(new double[] { fout, alpha });
                    al.Add(new double[] { 1, 0 });
                }
                List<object> kmin = new List<object>(), kmax = new List<object>();
                foreach (double[] k in al)
                {
                    double t = k[0];
                    kmin.Add(Key(t, c1[0] + (ce1[0] - c1[0]) * t, c1[1] + (ce1[1] - c1[1]) * t, c1[2] + (ce1[2] - c1[2]) * t, k[1]));
                    kmax.Add(Key(t, c2[0] + (ce2[0] - c2[0]) * t, c2[1] + (ce2[1] - c2[1]) * t, c2[2] + (ce2[2] - c2[2]) * t, k[1]));
                }
                JObj c = new JObj();
                c.Add("type", "Colour");
                Kfp(c, "RGBAMinKFP", kmin);
                Kfp(c, "RGBAMaxKFP", kmax);
                List<object> emKeys = L.Arr("emissiveKeys");
                if (emKeys != null && emKeys.Count > 0)
                {
                    List<object> ek = new List<object>();
                    foreach (object ko in emKeys)
                    {
                        List<object> kk = (List<object>)ko;
                        double emin = kk.Count > 1 ? D(kk[1]) : 1;
                        double emax = kk.Count > 2 ? D(kk[2]) : emin;
                        ek.Add(Key(D(kk[0]), emin, emax, 0, 0));
                    }
                    Kfp(c, "EmissiveIntensityKFP", ek);
                }
                else if (L.Has("emissive"))
                {
                    double[] e = Range(L.Get("emissive"), 1, 1);
                    List<object> ek = new List<object> { Key(0, e[0], e[0], 0, 0) };
                    if (e[1] != e[0]) ek.Add(Key(1, e[1], e[1], 0, 0));
                    Kfp(c, "EmissiveIntensityKFP", ek);
                }
                c.Add("RGBAMaxEnable", 1.0);
                beh.Add(c);
            }

            if (L.Has("noise"))
            {
                double nz = L.Num("noise", 0) * z;
                JObj n = new JObj();
                n.Add("type", "Noise");
                Kfp(n, "VelNoiseMinKFP", One(nz * 0.5, nz * 0.5, nz * 0.5, 0));
                Kfp(n, "VelNoiseMaxKFP", One(nz, nz, nz, 0));
                beh.Add(n);
            }

            JObj light = L.Obj("light");
            if (light != null)
            {
                double[] lc = Rgb(light.Get("color") ?? L.Get("color"), new double[] { 1, 1, 1 });
                double inten = light.Num("intensity", 8), range = light.Num("range", 2) * z;
                JObj lt = new JObj();
                lt.Add("type", "Light");
                Kfp(lt, "RGBMinKFP", One(lc[0], lc[1], lc[2], 0));
                Kfp(lt, "RGBMaxKFP", One(lc[0], lc[1], lc[2], 0));
                Kfp(lt, "IntensityKFP", new List<object> { Key(0, inten, inten, 0, 0), Key(1, 0, 0, 0, 0) });
                Kfp(lt, "RangeKFP", One(range, range, 0, 0));
                lt.Add("ColourFromParticle", 0.0);
                beh.Add(lt);
            }

            if (trail)
            {
                JObj t = new JObj();
                t.Add("type", "Trail");
                List<object> ti = L.Arr("texInfo");
                if (ti != null && ti.Count > 0 && ti[0] is List<object>)
                {
                    List<object> tik = new List<object>();
                    foreach (object ko in ti)
                    {
                        List<object> kk = (List<object>)ko;
                        tik.Add(Key(D(kk[0]), kk.Count > 1 ? D(kk[1]) : 1, kk.Count > 2 ? D(kk[2]) : 1, kk.Count > 3 ? D(kk[3]) : 0, kk.Count > 4 ? D(kk[4]) : 0));
                    }
                    Kfp(t, "TexInfoKFP", tik);
                }
                else if (ti != null && ti.Count >= 2)
                {
                    Kfp(t, "TexInfoKFP", One(D(ti[0]), D(ti[1]), ti.Count > 2 ? D(ti[2]) : 0, ti.Count > 3 ? D(ti[3]) : 0));
                }
                else Kfp(t, "TexInfoKFP", One(1, 1, 0, 0));
                t.Add("TessellationU", L.Num("tessU", 2));
                t.Add("TessellationV", L.Num("tessV", 4));
                t.Add("WrapTextureOverParticleLife", L.Num("trailWrap", 1));
                if (L.Has("smoothness")) t.Add("SmoothnessX", L.Num("smoothness", 0.1));
                beh.Add(t);
            }
            else
            {
                JObj sp = new JObj();
                sp.Add("type", "Sprite");
                if (align == "velocity") sp.Add("AlignmentMode", 1.0);
                else if (align == "ground") { sp.Add("AlignmentMode", 2.0); sp.Add("AlignAxis", new List<object> { 0f, 0f, 1f }); }
                else if (align == "axis") { double[] ax = Vec3(L.Get("axis"), 0); sp.Add("AlignmentMode", 2.0); sp.Add("AlignAxis", new List<object> { (float)ax[0], (float)ax[1], (float)ax[2] }); }
                else if (align != "camera") Warn("layer '" + use + "': align '" + align + "' is not camera/velocity/ground/axis");
                if (L.Has("flipU")) sp.Add("FlipChanceU", L.Num("flipU", 0));
                if (L.Has("flipV")) sp.Add("FlipChanceV", L.Num("flipV", 0));
                beh.Add(sp);
            }
            pr.Add("AllBehaviours", beh);
            particles.Add(pr);

            JObj ev = new JObj();
            ev.Add("EmitterRuleName", baseName);
            ev.Add("ParticleRuleName", baseName);
            ev.Add("EmitterRule", baseName);
            ev.Add("ParticleRule", baseName);
            ev.Add("StartRatio", L.Num("start", 0));
            ev.Add("EndRatio", L.Num("end", 1));
            events.Add(ev);

            double peakLife = life[1];
            double alive = isBurst ? count[1] : (count[1] + distRate[1] * 2.0) * peakLife;
            string rateDesc = isBurst ? "burst=" + count[1].ToString(CultureInfo.InvariantCulture) :
                (distRate[1] > 0 ? "rate=" + count[1].ToString(CultureInfo.InvariantCulture) + "+dist=" + distRate[1].ToString(CultureInfo.InvariantCulture) + "/m" : "rate=" + count[1].ToString(CultureInfo.InvariantCulture));
            Summary.Add(string.Format(CultureInfo.InvariantCulture, "  layer {0,-2} {1,-18} tex={2}{3} {4}/{5} {6} life={7}-{8}s size={9}-{10}m speed={11}-{12} alive~{13}",
                index, use, tex, external ? "(game)" : "", technique, blend, rateDesc, life[0], life[1], size[0] * z, size[1] * z, speed[0] * z, speed[1] * z, Math.Round(alive)));
        }

        static void AssignRandomIndices(JObj o, ref int next)
        {
            for (int i = 0; i < o.Items.Count; i++)
            {
                KeyValuePair<string, object> kv = o.Items[i];
                if (kv.Key.EndsWith("KFP"))
                {
                    JObj k = kv.Value as JObj;
                    if (k == null) { k = new JObj(); k.Add("keys", kv.Value); }
                    if (!k.Has("RandomIndex")) k.Set("RandomIndex", (double)(next++ & 0xFF));
                    o.Items[i] = new KeyValuePair<string, object>(kv.Key, k);
                }
                else if (kv.Value is JObj) AssignRandomIndices((JObj)kv.Value, ref next);
                else if (kv.Value is List<object>)
                    foreach (object x in (List<object>)kv.Value) if (x is JObj) AssignRandomIndices((JObj)x, ref next);
            }
        }

        public JObj Expand(JObj design)
        {
            dict = design.Str("dict") ?? design.Str("name");
            if (string.IsNullOrEmpty(dict)) throw new InvalidDataException("design needs \"dict\": the dictionary and .ypt file name");
            if (!System.Text.RegularExpressions.Regex.IsMatch(dict, "^[a-z0-9_]{3,40}$")) throw new InvalidDataException("dict must be 3-40 chars of a-z, 0-9, _ : " + dict);
            palette = design.Obj("palette");
            sheets = design.Obj("sheets");
            foreach (object o in design.Arr("textures") ?? new List<object>())
            {
                JObj t = ((JObj)o).Clone();
                if (texByName.ContainsKey(t.Str("name"))) throw new InvalidDataException("duplicate texture '" + t.Str("name") + "'");
                ResolveGenColours(t.Obj("gen"));
                textures.Add(t);
                texByName[t.Str("name")] = t;
            }
            // Game textures the layers ask for by name must stay free: a sheet embedded under the same name would replace them.
            foreach (object o in design.Arr("effects") ?? new List<object>())
                foreach (object lo in ((JObj)o).Arr("layers") ?? new List<object>())
                {
                    string tn = Merge((JObj)lo).Str("texture");
                    if (tn != null && !texByName.ContainsKey(tn) && !IsSheet(tn) && Array.IndexOf(SpriteGen.Shapes, tn) < 0) externalWanted.Add(tn);
                }
            double globalScale = design.Num("scale", 1);
            foreach (object o in design.Arr("effects") ?? new List<object>())
            {
                JObj e = (JObj)o;
                string name = e.Str("name");
                if (string.IsNullOrEmpty(name)) throw new InvalidDataException("every effect needs a name");
                bool loop = e.Get("loop") is bool ? (bool)e.Get("loop") : e.Num("loop", 0) != 0;
                double dur = e.Num("duration", 1);
                JObj er = new JObj();
                er.Add("id", name);
                er.Add("Name", name);
                er.Add("NumLoops", loop ? -1.0 : 0.0);
                er.Add("DurationMin", dur);
                er.Add("DurationMax", dur);
                er.Add("DistanceCullingFadeDist", e.Num("fadeDist", 50));
                er.Add("DistanceCullingCullDist", e.Num("cullDist", 60));
                Kfp(er, "ZoomScalarKFP", One(100, 100, 100, 100));
                List<object> events = new List<object>();
                Summary.Add("effect " + name + (loop ? "  loop" : "  one-shot") + " duration=" + dur.ToString(CultureInfo.InvariantCulture) + "s");
                int i = 0;
                foreach (object lo in e.Arr("layers") ?? new List<object>()) BuildLayer(er, events, (JObj)lo, i++, globalScale * e.Num("scale", 1));
                if (events.Count == 0) throw new InvalidDataException("effect '" + name + "' has no layers");
                if (events.Count > MaxLayers) throw new InvalidDataException("effect '" + name + "' has " + events.Count + " layers; the limit is " + MaxLayers + " (no effect in any real file has more). Move the extra layers into a second effect such as '" + name + "_b' and call both from Lua.");
                er.Add("EventEmitters", events);
                JObj raw = e.Obj("raw");
                if (raw != null) foreach (KeyValuePair<string, object> kv in raw.Items) er.Set(kv.Key, kv.Value);
                effects.Add(er);
            }
            JObj spec = new JObj();
            spec.Add("format", "weapon-forge-ptfx/1");
            spec.Add("name", dict);
            spec.Add("textures", textures);
            spec.Add("effects", effects);
            spec.Add("emitters", emitters);
            spec.Add("particles", particles);
            foreach (object o in emitters) { int n = 0; AssignRandomIndices((JObj)o, ref n); }
            foreach (object o in particles) { int n = 32; AssignRandomIndices((JObj)o, ref n); }
            foreach (object o in effects)
            {
                JObj e = (JObj)o;
                int n = 200;
                for (int i = 0; i < e.Items.Count; i++)
                    if (e.Items[i].Key.EndsWith("KFP"))
                    {
                        JObj k = e.Items[i].Value as JObj;
                        if (k == null) { k = new JObj(); k.Add("keys", e.Items[i].Value); }
                        k.Set("RandomIndex", (double)(n++));
                        e.Items[i] = new KeyValuePair<string, object>(e.Items[i].Key, k);
                    }
            }
            return spec;
        }

        public static TexPayload GenerateTexture(JObj tj, string name, string baseDir)
        {
            JObj sheet = tj.Obj("sheet");
            if (sheet != null)
            {
                SpriteFx.Slot slot = SpriteFx.FindSlot(name);
                if (slot == null) throw new InvalidDataException("texture '" + name + "' carries a sheet, but that name is not a known grid slot");
                JObj sh = sheet.Clone();
                foreach (object o in sh.Arr("cells") ?? new List<object>())
                {
                    JObj c = o as JObj;
                    if (c != null && c.Str("shape") == "image" && c.Has("file") && !Path.IsPathRooted(c.Str("file")) && baseDir != null) c.Set("file", Path.Combine(baseDir, c.Str("file")));
                }
                int frames;
                using (Bitmap bmp = SpriteFx.RenderSheetTexture(sh, slot.Cols, slot.Rows, out frames))
                {
                    int cellPx = bmp.Width / slot.Cols, levels = 1;
                    while (cellPx >= 16) { levels++; cellPx /= 2; }
                    return SpriteGen.Encode(bmp, tj.Str("format"), levels);
                }
            }
            JObj gen = tj.Obj("gen");
            if (gen == null && tj.Has("file"))
            {
                gen = new JObj();
                gen.Add("shape", "image");
                gen.Add("file", tj.Str("file"));
                if (tj.Has("size")) gen.Add("size", tj.Num("size", 256));
                if (tj.Has("width")) gen.Add("width", tj.Num("width", 256));
                if (tj.Has("height")) gen.Add("height", tj.Num("height", 256));
            }
            if (gen == null) throw new InvalidDataException("texture '" + name + "' needs \"gen\" (procedural sprite), \"file\" (png) or \"data\":{\"from\":...}");
            if (gen.Str("shape") == "image" && gen.Has("file") && !Path.IsPathRooted(gen.Str("file")) && baseDir != null) gen.Set("file", Path.Combine(baseDir, gen.Str("file")));
            using (Bitmap bmp = SpriteGen.Render(gen)) return SpriteGen.Encode(bmp, tj.Str("format"));
        }
    }
}
