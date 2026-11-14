using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;

namespace WeaponForge
{
    // Software simulation of a dictionary, drawn as a contact sheet: eight moments seen from the side plus one seen
    // from above. It follows the same numbers the game reads, but it is not the game's renderer.
    public static class PtfxPreview
    {
        public static string GameCorePath;
        static YptFile coreFile;
        static Dictionary<string, TexPayload> coreTex;

        class Sprite
        {
            public int W, H, Cols = 1, Rows = 1;
            public float[] A, R, G, B;
            public Sprite Half;

            // Box-filtered half-size copies, so a sprite drawn a few pixels wide averages its texels the way mip maps do.
            public void BuildMips()
            {
                Sprite s = this;
                while (s.W / s.Cols >= 6 && (s.W / s.Cols) % 2 == 0 && (s.H / s.Rows) % 2 == 0)
                {
                    Sprite h = new Sprite();
                    h.W = s.W / 2; h.H = s.H / 2; h.Cols = s.Cols; h.Rows = s.Rows;
                    int n = h.W * h.H;
                    h.A = new float[n]; h.R = new float[n]; h.G = new float[n]; h.B = new float[n];
                    for (int y = 0; y < h.H; y++)
                        for (int x = 0; x < h.W; x++)
                        {
                            int i = y * h.W + x, a = (y * 2) * s.W + x * 2, b = a + 1, c = a + s.W, d = c + 1;
                            float wa = s.A[a], wb = s.A[b], wc = s.A[c], wd = s.A[d], sum = wa + wb + wc + wd;
                            h.A[i] = sum / 4;
                            if (sum > 1e-5f)
                            {
                                h.R[i] = (s.R[a] * wa + s.R[b] * wb + s.R[c] * wc + s.R[d] * wd) / sum;
                                h.G[i] = (s.G[a] * wa + s.G[b] * wb + s.G[c] * wc + s.G[d] * wd) / sum;
                                h.B[i] = (s.B[a] * wa + s.B[b] * wb + s.B[c] * wc + s.B[d] * wd) / sum;
                            }
                            else { h.R[i] = s.R[a]; h.G[i] = s.G[a]; h.B[i] = s.B[a]; }
                        }
                    s.Half = h;
                    s = h;
                }
            }
        }

        class P
        {
            public double X, Y, Z, Vx, Vy, Vz, Age, Life, Rot, Spin, Rnd, Rnd2;
            public double Ax, Ay, Az, Drag, Noise;
            public int Frame0;
        }

        class Layer
        {
            public JObj Em, Pr;
            public double Start, End;
            public Sprite Tex;
            public bool Additive, Ground, Velocity, Trail, HasMtxWeight;
            public double Emissive, DistRate;
            public List<P> Ps = new List<P>();
            public double Carry;
            public bool Fired, HasPrevEmitter;
            public double PrevEx, PrevEy, PrevEz;
            public int LoopIndex = -1;
            public int FrameMin, FrameMax, AnimLast;
            public bool Anim, AnimLoop, AnimScaled, AnimHold, AnimRandom;
            public double FpsMin, FpsMax;
            public double Zoom = 1;
        }

        static List<object> KeysOf(object v)
        {
            JObj j = v as JObj;
            return j != null ? j.Arr("keys") : v as List<object>;
        }

        static double Eval(object kfp, double t, int comp, double def)
        {
            List<object> keys = KeysOf(kfp);
            if (keys == null || keys.Count == 0) return def;
            List<object> prev = (List<object>)keys[0];
            int vo = prev.Count >= 8 ? 4 : 1;
            if (t <= Json.ToDouble(prev[0]) || keys.Count == 1) return vo + comp < prev.Count ? Json.ToDouble(prev[vo + comp]) : 0;
            for (int i = 1; i < keys.Count; i++)
            {
                List<object> k = (List<object>)keys[i];
                double t0 = Json.ToDouble(prev[0]), t1 = Json.ToDouble(k[0]);
                if (t <= t1)
                {
                    double f = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
                    double a = vo + comp < prev.Count ? Json.ToDouble(prev[vo + comp]) : 0, b = vo + comp < k.Count ? Json.ToDouble(k[vo + comp]) : 0;
                    return a + (b - a) * f;
                }
                prev = k;
            }
            return vo + comp < prev.Count ? Json.ToDouble(prev[vo + comp]) : 0;
        }

        static JObj Beh(JObj pr, string type) { return RangeBuilder.Beh(pr, type); }

        static Sprite FromBitmap(Bitmap bmp, int cols, int rows)
        {
            int cell = cols * rows > 16 ? 64 : 96;
            int w = Math.Min(672, cols * cell), h = Math.Min(960, rows * cell);
            using (Bitmap small = new Bitmap(w, h, PixelFormat.Format32bppArgb))
            {
                using (Graphics g = Graphics.FromImage(small))
                {
                    g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                    g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;
                    g.Clear(Color.Transparent);
                    g.DrawImage(bmp, 0, 0, w, h);
                }
                byte[] px = SpriteGen.Pixels(small);
                bool flat = TexDecode.AlphaIsFlat(px);
                Sprite s = new Sprite();
                s.W = w; s.H = h; s.Cols = cols; s.Rows = rows;
                s.A = new float[w * h]; s.R = new float[w * h]; s.G = new float[w * h]; s.B = new float[w * h];
                for (int i = 0; i < w * h; i++)
                {
                    s.B[i] = px[i * 4] / 255f; s.G[i] = px[i * 4 + 1] / 255f; s.R[i] = px[i * 4 + 2] / 255f;
                    s.A[i] = flat ? Math.Max(s.R[i], Math.Max(s.G[i], s.B[i])) : px[i * 4 + 3] / 255f;
                }
                s.BuildMips();
                return s;
            }
        }

        static Sprite Placeholder(string name, Dictionary<string, Sprite> cache)
        {
            string shape = "glow";
            string n = name.ToLowerInvariant();
            if (n.Contains("smoke") || n.Contains("fireball") || n.Contains("dust") || n.Contains("mist") || n.Contains("steam")) shape = "smoke";
            else if (n.Contains("star") || n.Contains("flare")) shape = "burst";
            else if (n.Contains("spark") || n.Contains("tracer") || n.Contains("streak")) shape = "sparkle";
            else if (n.Contains("lightning") || n.Contains("arc")) shape = "bolt";
            else if (n.Contains("ring") || n.Contains("shock")) shape = "ring";
            else if (n.Contains("bubble")) shape = "bubble";
            else if (n.Contains("fire") || n.Contains("flame")) shape = "fire";
            Sprite s;
            if (cache.TryGetValue("#" + shape, out s)) return s;
            JObj g = new JObj();
            g.Add("shape", shape);
            g.Add("size", 128.0);
            using (Bitmap b = SpriteGen.Render(g)) s = FromBitmap(b, 1, 1);
            cache["#" + shape] = s;
            return s;
        }

        static Sprite FromPayload(string name, TexPayload p)
        {
            using (Bitmap b = TexDecode.ToBitmap(p))
            {
                if (b == null) return null;
                int cols = 1, rows = 1;
                SpriteFx.GameGrid(name, out cols, out rows);
                return FromBitmap(b, cols, rows);
            }
        }

        static Sprite FromGameCore(string name)
        {
            if (string.IsNullOrEmpty(GameCorePath) || !File.Exists(GameCorePath)) return null;
            try
            {
                if (coreTex == null)
                {
                    coreFile = YptFile.Parse(GameCorePath);
                    coreTex = new Dictionary<string, TexPayload>(StringComparer.OrdinalIgnoreCase);
                    foreach (KeyValuePair<string, TexPayload> kv in TexDecode.All(coreFile)) coreTex[kv.Key] = kv.Value;
                }
                TexPayload p;
                return coreTex.TryGetValue(name, out p) ? FromPayload(name, p) : null;
            }
            catch { return null; }
        }

        static string TextureOf(JObj pr)
        {
            if (pr.Has("$texture")) return pr.Str("$texture");
            return RangeBuilder.TextureOf(pr) ?? "glow";
        }

        static void Domain(JObj d, Random rnd, double t, out double x, out double y, out double z)
        {
            x = y = z = 0;
            if (d == null) return;
            double px = Eval(d.Get("PositionKFP"), t, 0, 0), py = Eval(d.Get("PositionKFP"), t, 1, 0), pz = Eval(d.Get("PositionKFP"), t, 2, 0);
            double ox = Eval(d.Get("SizeOuterKFP"), t, 0, 0), oy = Eval(d.Get("SizeOuterKFP"), t, 1, 0), oz = Eval(d.Get("SizeOuterKFP"), t, 2, 0);
            double ix = Eval(d.Get("SizeInnerKFP"), t, 0, 0);
            int type = (int)d.Num("DomainType", 1);
            if (type == 0)
            {
                x = (rnd.NextDouble() * 2 - 1) * ox; y = (rnd.NextDouble() * 2 - 1) * oy; z = (rnd.NextDouble() * 2 - 1) * oz;
            }
            else
            {
                double u = rnd.NextDouble() * 2 - 1, a = rnd.NextDouble() * Math.PI * 2, s = Math.Sqrt(1 - u * u);
                double inner = ox > 0 ? Math.Min(1, ix / ox) : 0;
                double r = inner + (1 - inner) * Math.Pow(rnd.NextDouble(), 1.0 / 3);
                if (oy == 0 && oz == 0) { oy = ox; oz = ox; }
                x = Math.Cos(a) * s * r * ox; y = Math.Sin(a) * s * r * oy; z = u * r * oz;
                // A cylinder's axis is local Y (the game's own muzzle and stab effects put the length there).
                if (type == 2) { x = Math.Cos(a) * r * ox; z = Math.Sin(a) * r * oz; y = (rnd.NextDouble() * 2 - 1) * oy; }
            }
            x += px; y += py; z += pz;
        }

        static void EmitterOffset(Layer L, double t, bool loop, out double ex, out double ey, out double ez)
        {
            ex = ey = ez = 0;
            if (loop && (L.Trail || L.DistRate > 0) && !L.HasMtxWeight)
            {
                double w = 3.6;
                ex = 0.52 * Math.Sin(w * t);
                ey = 0.34 * Math.Cos(w * t);
                ez = 0.18 * Math.Sin(2.0 * w * t);
            }
        }

        static void Spawn(Layer L, Random rnd, double te, double ex, double ey, double ez)
        {
            JObj em = L.Em, pr = L.Pr;
            P p = new P();
            double cx, cy, cz, tx, ty, tz;
            Domain(em.Obj("CreationDomain"), rnd, te, out cx, out cy, out cz);
            JObj td = em.Obj("TargetDomain");
            Domain(td, rnd, te, out tx, out ty, out tz);
            if (td != null && td.Num("IsPointRelative", 0) != 0) { tx += cx; ty += cy; tz += cz; }
            // The effect zoom scales the whole emitter: where particles appear and how fast they leave.
            cx *= L.Zoom; cy *= L.Zoom; cz *= L.Zoom; tx *= L.Zoom; ty *= L.Zoom; tz *= L.Zoom;
            double dx = tx - cx, dy = ty - cy, dz = tz - cz;
            double len = Math.Sqrt(dx * dx + dy * dy + dz * dz);
            double smin = Eval(em.Get("SpeedScalarKFP"), te, 0, 0), smax = Eval(em.Get("SpeedScalarKFP"), te, 1, 0);
            double speed = (smin + (smax - smin) * rnd.NextDouble()) * L.Zoom;
            p.X = cx + ex; p.Y = cy + ey; p.Z = cz + ez;
            if (len > 1e-6) { p.Vx = dx / len * speed; p.Vy = dy / len * speed; p.Vz = dz / len * speed; }
            double lmin = Eval(em.Get("ParticleLifeKFP"), te, 0, 1), lmax = Eval(em.Get("ParticleLifeKFP"), te, 1, 1);
            p.Life = Math.Max(0.02, lmin + (lmax - lmin) * rnd.NextDouble());
            p.Rnd = rnd.NextDouble();
            p.Rnd2 = rnd.NextDouble();
            p.Frame0 = L.FrameMin + rnd.Next(Math.Max(1, L.FrameMax - L.FrameMin + 1));
            JObj rot = Beh(pr, "Rotation");
            if (rot != null)
            {
                double a0 = Eval(rot.Get("InitialAngleMinKFP"), 0, 0, 0), a1 = Eval(rot.Get("InitialAngleMaxKFP"), 0, 0, 0);
                double s0 = Eval(rot.Get("AngleMinKFP"), 0, 0, 0), s1 = Eval(rot.Get("AngleMaxKFP"), 0, 0, 0);
                p.Rot = a0 + (a1 - a0) * rnd.NextDouble();
                p.Spin = s0 + (s1 - s0) * rnd.NextDouble();
            }
            JObj acc = Beh(pr, "Acceleration");
            if (acc != null)
            {
                double f = rnd.NextDouble();
                p.Ax = Eval(acc.Get("XYZMinKFP"), 0, 0, 0) + (Eval(acc.Get("XYZMaxKFP"), 0, 0, 0) - Eval(acc.Get("XYZMinKFP"), 0, 0, 0)) * f;
                p.Ay = Eval(acc.Get("XYZMinKFP"), 0, 1, 0) + (Eval(acc.Get("XYZMaxKFP"), 0, 1, 0) - Eval(acc.Get("XYZMinKFP"), 0, 1, 0)) * f;
                p.Az = Eval(acc.Get("XYZMinKFP"), 0, 2, 0) + (Eval(acc.Get("XYZMaxKFP"), 0, 2, 0) - Eval(acc.Get("XYZMinKFP"), 0, 2, 0)) * f;
                if (acc.Num("IsAffectedByZoom", 0) != 0) { p.Ax *= L.Zoom; p.Ay *= L.Zoom; p.Az *= L.Zoom; }
            }
            JObj dmp = Beh(pr, "Dampening");
            if (dmp != null) p.Drag = Eval(dmp.Get("XYZMinKFP"), 0, 0, 0) + (Eval(dmp.Get("XYZMaxKFP"), 0, 0, 0) - Eval(dmp.Get("XYZMinKFP"), 0, 0, 0)) * rnd.NextDouble();
            JObj nz = Beh(pr, "Noise");
            if (nz != null) p.Noise = Eval(nz.Get("VelNoiseMaxKFP"), 0, 0, 0);
            L.Ps.Add(p);
        }

        static void Step(Layer L, Random rnd, double t, double dt, double duration, bool loop)
        {
            double ex, ey, ez;
            EmitterOffset(L, t, loop, out ex, out ey, out ez);
            double ds = 0;
            if (L.HasPrevEmitter)
            {
                double ddx = ex - L.PrevEx, ddy = ey - L.PrevEy, ddz = ez - L.PrevEz;
                ds = Math.Sqrt(ddx * ddx + ddy * ddy + ddz * ddz);
            }
            L.PrevEx = ex; L.PrevEy = ey; L.PrevEz = ez; L.HasPrevEmitter = true;
            double local = loop ? t % duration : t;
            double ratio = duration > 0 ? local / duration : 0;
            bool active = ratio >= L.Start && ratio <= L.End && (loop || t <= duration);
            if (L.Em.Num("IsOneShot", 0) != 0)
            {
                // A looped effect restarts its timeline, so a one-shot emitter fires once in every loop.
                int loopIndex = loop && duration > 0 ? (int)(t / duration) : 0;
                if (loopIndex != L.LoopIndex) { L.LoopIndex = loopIndex; L.Fired = false; }
                if (!L.Fired && ratio >= L.Start && (loop || t <= duration + dt))
                {
                    L.Fired = true;
                    double n0 = Eval(L.Em.Get("SpawnRateOverTimeKFP"), 0, 0, 1), n1 = Eval(L.Em.Get("SpawnRateOverTimeKFP"), 0, 1, 1);
                    int n = (int)Math.Round(n0 + (n1 - n0) * rnd.NextDouble());
                    for (int i = 0; i < n && L.Ps.Count < 4000; i++) Spawn(L, rnd, 0, ex, ey, ez);
                }
            }
            else if (active)
            {
                double span = Math.Max(1e-6, L.End - L.Start);
                double te = (ratio - L.Start) / span;
                double r0 = Eval(L.Em.Get("SpawnRateOverTimeKFP"), te, 0, 0), r1 = Eval(L.Em.Get("SpawnRateOverTimeKFP"), te, 1, 0);
                double d0 = Eval(L.Em.Get("SpawnRateOverDistKFP"), te, 0, 0), d1 = Eval(L.Em.Get("SpawnRateOverDistKFP"), te, 1, 0);
                L.Carry += (r0 + (r1 - r0) * 0.5) * dt + (d0 + (d1 - d0) * 0.5) * ds;
                while (L.Carry >= 1 && L.Ps.Count < 4000) { L.Carry -= 1; Spawn(L, rnd, te, ex, ey, ez); }
            }
            for (int i = L.Ps.Count - 1; i >= 0; i--)
            {
                P p = L.Ps[i];
                p.Age += dt;
                if (p.Age >= p.Life) { L.Ps.RemoveAt(i); continue; }
                p.Vx += p.Ax * dt; p.Vy += p.Ay * dt; p.Vz += p.Az * dt;
                if (p.Noise > 0) { p.Vx += (rnd.NextDouble() - 0.5) * p.Noise * dt * 6; p.Vy += (rnd.NextDouble() - 0.5) * p.Noise * dt * 6; p.Vz += (rnd.NextDouble() - 0.5) * p.Noise * dt * 6; }
                if (p.Drag > 0) { double k = Math.Exp(-p.Drag * dt); p.Vx *= k; p.Vy *= k; p.Vz *= k; }
                p.X += p.Vx * dt; p.Y += p.Vy * dt; p.Z += p.Vz * dt;
                p.Rot += p.Spin * dt;
            }
        }

        static int FrameOf(Layer L, P p, double t)
        {
            int total = L.Tex.Cols * L.Tex.Rows;
            if (total <= 1) return 0;
            int f = p.Frame0;
            if (L.Anim)
            {
                int last = Math.Max(0, L.AnimLast);
                double fps = L.FpsMin + (L.FpsMax - L.FpsMin) * p.Rnd;
                double adv = L.AnimScaled ? t * Math.Max(1, last - p.Frame0) : p.Age * fps;
                if (L.AnimRandom) f = (int)(SpriteGen.Hash((int)(p.Age * Math.Max(1, fps)), (int)(p.Rnd * 1000), 5) * (last + 1));
                else if (L.AnimLoop && !L.AnimScaled) f = (int)(p.Frame0 + adv) % (last + 1);
                else f = Math.Min(last, (int)(p.Frame0 + adv));
            }
            return Math.Max(0, Math.Min(total - 1, f));
        }

        static double EvalSuperAlpha(JObj pr, double t)
        {
            JObj vars = pr.Obj("$vars");
            if (vars != null && vars.Has("SuperAlpha"))
            {
                object ov = vars.Get("SuperAlpha");
                List<object> kl = ov as List<object>;
                if (kl == null || kl.Count == 0) return Json.ToDouble(ov);
                List<object> prev = kl[0] as List<object>;
                if (prev == null) return Json.ToDouble(kl[0]);
                if (t <= Json.ToDouble(prev[0]) || kl.Count == 1) return Json.ToDouble(prev[1]);
                for (int i = 1; i < kl.Count; i++)
                {
                    List<object> cur = kl[i] as List<object>;
                    if (cur == null) break;
                    double t0 = Json.ToDouble(prev[0]), t1 = Json.ToDouble(cur[0]);
                    if (t <= t1) { double f = t1 > t0 ? (t - t0) / (t1 - t0) : 1; return Json.ToDouble(prev[1]) + (Json.ToDouble(cur[1]) - Json.ToDouble(prev[1])) * f; }
                    prev = cur;
                }
                return Json.ToDouble(prev[1]);
            }
            List<object> sv = pr.Arr("ShaderVars");
            if (sv != null)
            {
                foreach (object vo in sv)
                {
                    JObj v = vo as JObj;
                    if (v == null || v.Str("Name") != "SuperAlpha") continue;
                    List<object> items = v.Arr("Items");
                    if (items == null || items.Count == 0) return 1.0;
                    JObj prev = (JObj)items[0];
                    if (t <= prev.Num("U0", 0) || items.Count == 1) return prev.Num("U10", 1);
                    for (int i = 1; i < items.Count; i++)
                    {
                        JObj cur = (JObj)items[i];
                        double t0 = prev.Num("U0", 0), t1 = cur.Num("U0", 1);
                        if (t <= t1) { double f = t1 > t0 ? (t - t0) / (t1 - t0) : 1; return prev.Num("U10", 1) + (cur.Num("U10", 1) - prev.Num("U10", 1)) * f; }
                        prev = cur;
                    }
                    return prev.Num("U10", 1);
                }
                return 1.0;
            }
            return pr.Str("ShaderTemplateName") == "ptfx_trail" ? 1.0 : 5.0 + (0.5 - 5.0) * t;
        }

        static void DrawTrail(Layer L, float[] buf, int w, int h, double view, bool top)
        {
            int n = L.Ps.Count;
            if (n < 2) return;
            JObj size = Beh(L.Pr, "Size"), col = Beh(L.Pr, "Colour");
            double sy = KeysOf(L.Em.Get("SizeScalarKFP")) == null ? 1 : Eval(L.Em.Get("SizeScalarKFP"), 0, 1, 100) / 100;
            sy *= L.Zoom;
            double ppm = h / view;
            Sprite s = L.Tex;
            int cw = s.W / s.Cols, chh = s.H / s.Rows;
            float normGain = (float)Math.Max(0.65, Math.Min(3.5, L.Emissive));
            double addGain = 0.55 + 0.45 * Math.Min(1, L.Emissive / 25.0);
            for (int k = 0; k < n - 1; k++)
            {
                P p0 = L.Ps[k], p1 = L.Ps[k + 1];
                double t0 = p0.Age / p0.Life, t1 = p1.Age / p1.Life;
                double tm = 0.5 * (t0 + t1);
                double sh0 = 0.08, sh1 = 0.08;
                if (size != null)
                {
                    double h0a = Eval(size.Get("WhdMinKFP"), t0, 1, 0.08), h1a = Eval(size.Get("WhdMaxKFP"), t0, 1, h0a);
                    double h0b = Eval(size.Get("WhdMinKFP"), t1, 1, 0.08), h1b = Eval(size.Get("WhdMaxKFP"), t1, 1, h0b);
                    sh0 = (h0a + (h1a - h0a) * p0.Rnd) * sy;
                    sh1 = (h0b + (h1b - h0b) * p1.Rnd) * sy;
                }
                double r = 1, g = 1, b = 1, a = 1;
                if (col != null)
                {
                    object mn = col.Get("RGBAMinKFP"), mx = KeysOf(col.Get("RGBAMaxKFP")) == null ? mn : col.Get("RGBAMaxKFP");
                    r = Eval(mn, tm, 0, 1) + (Eval(mx, tm, 0, 1) - Eval(mn, tm, 0, 1)) * p0.Rnd2;
                    g = Eval(mn, tm, 1, 1) + (Eval(mx, tm, 1, 1) - Eval(mn, tm, 1, 1)) * p0.Rnd2;
                    b = Eval(mn, tm, 2, 1) + (Eval(mx, tm, 2, 1) - Eval(mn, tm, 2, 1)) * p0.Rnd2;
                    a = Eval(mn, tm, 3, 1) + (Eval(mx, tm, 3, 1) - Eval(mn, tm, 3, 1)) * p0.Rnd2;
                }
                double sup = Math.Max(0, EvalSuperAlpha(L.Pr, tm));
                if (a * sup <= 0.003) continue;
                double sx0 = w / 2.0 + p0.X * ppm, sy0 = top ? h / 2.0 - p0.Y * ppm : h / 2.0 - p0.Z * ppm;
                double sx1 = w / 2.0 + p1.X * ppm, sy1 = top ? h / 2.0 - p1.Y * ppm : h / 2.0 - p1.Z * ppm;
                double dx = sx1 - sx0, dy = sy1 - sy0;
                double segLen = Math.Sqrt(dx * dx + dy * dy);
                if (segLen < 0.15 || segLen > w * 0.45) continue;
                double ux = dx / segLen, uy = dy / segLen;
                double nx = -uy, ny = ux;
                double hw0 = Math.Max(0.85, sh0 * ppm * 0.5), hw1 = Math.Max(0.85, sh1 * ppm * 0.5);
                double maxHw = Math.Max(hw0, hw1) + 1.5;
                int bx0 = Math.Max(0, (int)(Math.Min(sx0, sx1) - maxHw)), bx1 = Math.Min(w - 1, (int)(Math.Max(sx0, sx1) + maxHw));
                int by0 = Math.Max(0, (int)(Math.Min(sy0, sy1) - maxHw)), by1 = Math.Min(h - 1, (int)(Math.Max(sy0, sy1) + maxHw));
                double uStart = (double)k / Math.Max(1, n - 1), uEnd = (double)(k + 1) / Math.Max(1, n - 1);
                for (int py = by0; py <= by1; py++)
                    for (int px = bx0; px <= bx1; px++)
                    {
                        double rx = px + 0.5 - sx0, ry = py + 0.5 - sy0;
                        double along = (rx * ux + ry * uy) / segLen;
                        if (along < 0 || along > 1.02) continue;
                        double alClamp = along > 1 ? 1 : along;
                        double hw = hw0 + (hw1 - hw0) * alClamp;
                        double v = (rx * nx + ry * ny) / hw;
                        if (v < -1 || v >= 1) continue;
                        double uTex = uStart + (uEnd - uStart) * alClamp;
                        int tx = Math.Min(cw - 1, Math.Max(0, (int)(uTex * cw)));
                        int ty = Math.Min(chh - 1, Math.Max(0, (int)((v + 1) * 0.5 * chh)));
                        int si = ty * s.W + tx;
                        float sa2 = Math.Min(1f, s.A[si] * (float)(a * sup));
                        if (sa2 <= 0.002f) continue;
                        int o = (py * w + px) * 3;
                        float cr = s.R[si] * (float)r, cg = s.G[si] * (float)g, cb = s.B[si] * (float)b;
                        if (L.Additive)
                        {
                            float ka = sa2 * (float)addGain;
                            buf[o] += cr * ka; buf[o + 1] += cg * ka; buf[o + 2] += cb * ka;
                        }
                        else
                        {
                            buf[o] = buf[o] * (1 - sa2) + cr * normGain * sa2;
                            buf[o + 1] = buf[o + 1] * (1 - sa2) + cg * normGain * sa2;
                            buf[o + 2] = buf[o + 2] * (1 - sa2) + cb * normGain * sa2;
                        }
                    }
            }
        }

        // top = false: camera looks along +Y, screen up is +Z. top = true: camera looks down, screen up is +Y.
        static void Draw(Layer L, float[] buf, int w, int h, double view, bool top)
        {
            if (L.Trail) { DrawTrail(L, buf, w, h, view, top); return; }
            JObj size = Beh(L.Pr, "Size"), col = Beh(L.Pr, "Colour");
            double sx = Eval(L.Em.Get("SizeScalarKFP"), 0, 0, 100) / 100, sy = Eval(L.Em.Get("SizeScalarKFP"), 0, 1, 100) / 100;
            if (KeysOf(L.Em.Get("SizeScalarKFP")) == null) { sx = 1; sy = 1; }
            sx *= L.Zoom; sy *= L.Zoom;
            double ppm = h / view;
            Sprite s0 = L.Tex;
            foreach (P p in L.Ps)
            {
                double t = p.Age / p.Life;
                double sw = 0.1, sh = 0.1;
                if (size != null)
                {
                    double w0 = Eval(size.Get("WhdMinKFP"), t, 0, 0.1), w1 = Eval(size.Get("WhdMaxKFP"), t, 0, w0);
                    double h0 = Eval(size.Get("WhdMinKFP"), t, 1, w0), h1 = Eval(size.Get("WhdMaxKFP"), t, 1, h0);
                    if (KeysOf(size.Get("WhdMaxKFP")) == null) { w1 = w0; h1 = h0; }
                    sw = (w0 + (w1 - w0) * p.Rnd) * sx;
                    sh = (h0 + (h1 - h0) * p.Rnd) * sy;
                }
                double r = 1, g = 1, b = 1, a = 1;
                if (col != null)
                {
                    object mn = col.Get("RGBAMinKFP"), mx = KeysOf(col.Get("RGBAMaxKFP")) == null ? mn : col.Get("RGBAMaxKFP");
                    r = Eval(mn, t, 0, 1) + (Eval(mx, t, 0, 1) - Eval(mn, t, 0, 1)) * p.Rnd2;
                    g = Eval(mn, t, 1, 1) + (Eval(mx, t, 1, 1) - Eval(mn, t, 1, 1)) * p.Rnd2;
                    b = Eval(mn, t, 2, 1) + (Eval(mx, t, 2, 1) - Eval(mn, t, 2, 1)) * p.Rnd2;
                    a = Eval(mn, t, 3, 1) + (Eval(mx, t, 3, 1) - Eval(mn, t, 3, 1)) * p.Rnd2;
                }
                double sup = Math.Max(0, EvalSuperAlpha(L.Pr, t));
                if (a * sup <= 0.003 || sw <= 0 || sh <= 0) continue;
                double gain = L.Additive ? 0.55 + 0.45 * Math.Min(1, L.Emissive / 25.0) : 1;
                double cx = w / 2.0 + p.X * ppm, cy = top ? h / 2.0 - p.Y * ppm : h / 2.0 - p.Z * ppm;
                // Keep hair-thin sprites visible: below one pixel they are widened and dimmed by the same factor.
                // A side thinner than about a pixel is drawn one pixel wide from the sprite's centre line, dimmed a little.
                double hw = sw * ppm / 2, hh = sh * ppm / 2, thin = 1;
                bool narrowU = hw < 0.7, narrowV = hh < 0.7;
                if (narrowU) { thin *= Math.Sqrt(hw / 0.7); hw = 0.7; }
                if (narrowV) { thin *= Math.Sqrt(hh / 0.7); hh = 0.7; }
                thin = Math.Max(0.45, thin);
                double ang = p.Rot * Math.PI / 180;
                if (L.Velocity) ang = top ? Math.Atan2(p.Vx, p.Vy) : Math.Atan2(p.Vx, p.Vz);
                if (L.Ground && !top) { hh *= 0.22; ang = 0; }
                else if (!L.Ground && !L.Velocity && top) { }
                double ca = Math.Cos(ang), sa = Math.Sin(ang);
                double ext = Math.Sqrt(hw * hw + hh * hh) + 1;
                int x0 = Math.Max(0, (int)(cx - ext)), x1 = Math.Min(w - 1, (int)(cx + ext)), y0 = Math.Max(0, (int)(cy - ext)), y1 = Math.Min(h - 1, (int)(cy + ext));
                int frame = FrameOf(L, p, t);
                Sprite s = s0;
                while (s.Half != null && Math.Max(narrowU ? 0 : (s.W / s.Cols) / (2 * hw), narrowV ? 0 : (s.H / s.Rows) / (2 * hh)) >= 2) s = s.Half;
                int cw = s.W / s.Cols, chh = s.H / s.Rows;
                int fx = (frame % s.Cols) * cw, fy = (frame / s.Cols) * chh;
                for (int y = y0; y <= y1; y++)
                    for (int x = x0; x <= x1; x++)
                    {
                        double dx = x + 0.5 - cx, dy = y + 0.5 - cy;
                        double u = (dx * ca - dy * sa) / hw, v = (dx * sa + dy * ca) / hh;
                        if (u < -1 || u >= 1 || v < -1 || v >= 1) continue;
                        int si = (fy + (int)(((narrowV ? 0 : v) + 1) * 0.5 * chh)) * s.W + fx + (int)(((narrowU ? 0 : u) + 1) * 0.5 * cw);
                        float sa2 = Math.Min(1f, s.A[si] * (float)(a * sup)) * (float)thin;
                        if (sa2 <= 0.002f) continue;
                        int o = (y * w + x) * 3;
                        float cr = s.R[si] * (float)r, cg = s.G[si] * (float)g, cb = s.B[si] * (float)b;
                        if (L.Additive)
                        {
                            float k = sa2 * (float)gain;
                            buf[o] += cr * k; buf[o + 1] += cg * k; buf[o + 2] += cb * k;
                        }
                        else
                        {
                            float ng = (float)Math.Max(0.65, Math.Min(3.5, L.Emissive));
                            buf[o] = buf[o] * (1 - sa2) + cr * ng * sa2; buf[o + 1] = buf[o + 1] * (1 - sa2) + cg * ng * sa2; buf[o + 2] = buf[o + 2] * (1 - sa2) + cb * ng * sa2;
                        }
                    }
            }
        }

        static double Energy(float[] buf) { double e = 0; for (int i = 0; i < buf.Length; i += 7) e += buf[i]; return e; }

        static Bitmap ToBitmap(float[] buf, int cell, double view, bool top)
        {
            byte[] px = new byte[cell * cell * 4];
            double ppm = cell / view;
            for (int y = 0; y < cell; y++)
                for (int x = 0; x < cell; x++)
                {
                    int o = (y * cell + x) * 3, d = (y * cell + x) * 4;
                    double wz = (cell / 2.0 - y) / ppm, wx = (x - cell / 2.0) / ppm;
                    float bg = top ? 0.07f : 0.085f;
                    if (Math.Abs(wz - Math.Round(wz)) * ppm < 0.5 || Math.Abs(wx - Math.Round(wx)) * ppm < 0.5) bg += 0.055f;
                    if (Math.Abs(wz) * ppm < 0.5 || Math.Abs(wx) * ppm < 0.5) bg += 0.06f;
                    px[d] = (byte)(255 * Math.Min(1, bg * (top ? 1.35 : 1.1) + 1 - Math.Exp(-buf[o + 2] * 1.6)));
                    px[d + 1] = (byte)(255 * Math.Min(1, bg + 1 - Math.Exp(-buf[o + 1] * 1.6)));
                    px[d + 2] = (byte)(255 * Math.Min(1, bg + 1 - Math.Exp(-buf[o] * 1.6)));
                    px[d + 3] = 255;
                }
            Bitmap fb = new Bitmap(cell, cell, PixelFormat.Format32bppArgb);
            BitmapData bd = fb.LockBits(new Rectangle(0, 0, cell, cell), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            for (int y = 0; y < cell; y++) Marshal.Copy(px, y * cell * 4, new IntPtr(bd.Scan0.ToInt64() + (long)y * bd.Stride), cell * 4);
            fb.UnlockBits(bd);
            return fb;
        }

        static List<Layer> BuildLayers(JObj e, Dictionary<string, JObj> emit, Dictionary<string, JObj> ptx, Dictionary<string, Sprite> sprites, out double extent, out double maxLife, List<string> missing)
        {
            List<Layer> layers = new List<Layer>();
            double duration = Math.Max(0.05, e.Num("DurationMax", 1));
            extent = 0.3; maxLife = 0;
            double zoom = 1;
            if (KeysOf(e.Get("ZoomScalarKFP")) != null)
            {
                zoom = (Eval(e.Get("ZoomScalarKFP"), 0, 0, 100) + Eval(e.Get("ZoomScalarKFP"), 0, 1, 100)) / 200;
                if (zoom <= 0) zoom = 1;
            }
            foreach (object evo in e.Arr("EventEmitters") ?? new List<object>())
            {
                JObj ev = evo as JObj;
                if (ev == null) continue;
                JObj em, pr;
                if (!emit.TryGetValue(ev.Str("EmitterRule") ?? ev.Str("EmitterRuleName") ?? "", out em) || !ptx.TryGetValue(ev.Str("ParticleRule") ?? ev.Str("ParticleRuleName") ?? "", out pr)) continue;
                Layer L = new Layer();
                L.Em = em; L.Pr = pr;
                L.Zoom = zoom;
                L.Start = ev.Num("StartRatio", 0);
                L.End = ev.Has("EndRatio") ? ev.Num("EndRatio", 1) : 1;
                string tn = TextureOf(pr);
                if (!sprites.TryGetValue(tn, out L.Tex))
                {
                    L.Tex = FromGameCore(tn);
                    if (L.Tex == null) { L.Tex = Placeholder(tn, sprites); if (!missing.Contains(tn)) missing.Add(tn); }
                    else sprites[tn] = L.Tex;
                }
                L.Additive = pr.Num("BlendSet", 0) != 0;
                L.Trail = pr.Str("ShaderTemplateName") == "ptfx_trail" || Beh(pr, "Trail") != null;
                JObj mw = Beh(pr, "MatrixWeight");
                L.HasMtxWeight = mw != null && Eval(mw.Get("MtxWeightKFP"), 0, 0, 0) > 0.05;
                L.DistRate = Eval(em.Get("SpawnRateOverDistKFP"), 0, 1, Eval(em.Get("SpawnRateOverDistKFP"), 0, 0, 0));
                JObj sp = Beh(pr, "Sprite");
                int mode = sp == null ? 0 : (int)sp.Num("AlignmentMode", 0);
                L.Velocity = mode == 1;
                L.Ground = mode == 2 || mode == 4;
                JObj col = Beh(pr, "Colour");
                L.Emissive = col == null ? 1 : Eval(col.Get("EmissiveIntensityKFP"), 0, 0, 1);
                L.FrameMin = (int)pr.Num("TexFrameIDMin", 0);
                L.FrameMax = (int)pr.Num("TexFrameIDMax", 0);
                JObj an = Beh(pr, "AnimateTexture");
                if (an != null)
                {
                    L.Anim = true;
                    L.AnimLast = (int)an.Num("LastFrameID", 0);
                    L.AnimLoop = an.Num("LoopMode", 0) != 0;
                    L.AnimScaled = an.Num("IsScaledOverParticleLife", 0) != 0;
                    L.AnimHold = an.Num("IsHeldOnLastFrame", 0) != 0;
                    L.AnimRandom = an.Num("IsRandomised", 0) != 0;
                    L.FpsMin = Eval(an.Get("AnimRateKFP"), 0, 0, 12);
                    L.FpsMax = Eval(an.Get("AnimRateKFP"), 0, 1, L.FpsMin);
                }
                layers.Add(L);
                JObj size = Beh(pr, "Size");
                double peak = 0;
                double sc = KeysOf(em.Get("SizeScalarKFP")) == null ? 1 : Eval(em.Get("SizeScalarKFP"), 0, 0, 100) / 100;
                if (size != null) for (double t = 0; t <= 1.0; t += 0.1) peak = Math.Max(peak, Math.Max(Eval(size.Get("WhdMaxKFP"), t, 0, 0), Eval(size.Get("WhdMaxKFP"), t, 1, 0)) * sc);
                double life = Eval(em.Get("ParticleLifeKFP"), 0, 1, 1), speed = Eval(em.Get("SpeedScalarKFP"), 0, 1, 0);
                maxLife = Math.Max(maxLife, life + L.Start * duration);
                JObj cd = em.Obj("CreationDomain");
                double off = cd == null ? 0 : Math.Abs(Eval(cd.Get("PositionKFP"), 0, 2, 0)) + Eval(cd.Get("SizeOuterKFP"), 0, 0, 0);
                if (e.Num("NumLoops", 0) != 0 && (L.Trail || L.DistRate > 0) && !L.HasMtxWeight) off = Math.Max(off, 0.62);
                extent = Math.Max(extent, (peak / 2 + off) * zoom + Math.Min(Math.Abs(speed) * zoom * life * 0.3, 1.0));
            }
            return layers;
        }

        public static string Render(JObj spec, string outPath, int frames, int cell, string baseDir)
        {
            List<object> effects = spec.Arr("effects") ?? new List<object>();
            Dictionary<string, JObj> emit = new Dictionary<string, JObj>(), ptx = new Dictionary<string, JObj>();
            foreach (object o in spec.Arr("emitters") ?? new List<object>()) { JObj e = (JObj)o; emit[e.Str("id") ?? e.Str("Name")] = e; }
            foreach (object o in spec.Arr("particles") ?? new List<object>()) { JObj e = (JObj)o; ptx[e.Str("id") ?? e.Str("Name")] = e; }
            Dictionary<string, Sprite> sprites = new Dictionary<string, Sprite>(StringComparer.OrdinalIgnoreCase);
            Dictionary<string, Dictionary<string, TexPayload>> sources = new Dictionary<string, Dictionary<string, TexPayload>>();
            foreach (object o in spec.Arr("textures") ?? new List<object>())
            {
                JObj t = (JObj)o;
                string name = t.Str("name");
                try
                {
                    JObj sheet = t.Obj("sheet");
                    if (sheet != null)
                    {
                        SpriteFx.Slot slot = SpriteFx.FindSlot(name);
                        if (slot == null) continue;
                        JObj sh = sheet.Clone();
                        foreach (object co in sh.Arr("cells") ?? new List<object>())
                        {
                            JObj c0 = co as JObj;
                            if (c0 != null && c0.Str("shape") == "image" && c0.Has("file") && !Path.IsPathRooted(c0.Str("file")) && baseDir != null)
                                c0.Set("file", Path.Combine(baseDir, c0.Str("file")));
                        }
                        int n;
                        using (Bitmap b = SpriteFx.RenderSheetTexture(sh, slot.Cols, slot.Rows, out n)) sprites[name] = FromBitmap(b, slot.Cols, slot.Rows);
                        continue;
                    }
                    JObj gen = t.Obj("gen");
                    if (gen == null && t.Has("file"))
                    {
                        gen = new JObj();
                        gen.Add("shape", "image");
                        gen.Add("file", t.Str("file"));
                        if (t.Has("size")) gen.Add("size", t.Num("size", 256));
                        if (t.Has("width")) gen.Add("width", t.Num("width", 256));
                        if (t.Has("height")) gen.Add("height", t.Num("height", 256));
                    }
                    if (gen != null)
                    {
                        if (gen.Str("shape") == "image" && gen.Has("file") && !Path.IsPathRooted(gen.Str("file")) && baseDir != null) gen.Set("file", Path.Combine(baseDir, gen.Str("file")));
                        using (Bitmap b = SpriteGen.Render(gen)) sprites[name] = FromBitmap(b, 1, 1);
                        continue;
                    }
                    JObj data = t.Obj("data");
                    if (data != null && data.Has("from") && File.Exists(data.Str("from")))
                    {
                        Dictionary<string, TexPayload> src;
                        if (!sources.TryGetValue(data.Str("from"), out src))
                        {
                            src = new Dictionary<string, TexPayload>(StringComparer.OrdinalIgnoreCase);
                            foreach (KeyValuePair<string, TexPayload> kv in TexDecode.All(YptFile.Parse(data.Str("from")))) src[kv.Key] = kv.Value;
                            sources[data.Str("from")] = src;
                        }
                        TexPayload p;
                        if (src.TryGetValue(data.Str("name") ?? name, out p)) { Sprite s = FromPayload(name, p); if (s != null) sprites[name] = s; }
                    }
                }
                catch { }
            }
            int rows = Math.Max(1, effects.Count);
            int label = 20, colsOut = frames + 1;
            List<string> missing = new List<string>();
            System.Text.StringBuilder rep = new System.Text.StringBuilder();
            using (Bitmap sheetBmp = new Bitmap(colsOut * cell, rows * (cell + label), PixelFormat.Format32bppArgb))
            {
                using (Graphics gfx = Graphics.FromImage(sheetBmp))
                using (Font font = new Font("Consolas", 9f))
                using (Brush tb = new SolidBrush(Color.FromArgb(235, 235, 235)))
                using (Brush tb2 = new SolidBrush(Color.FromArgb(150, 200, 255)))
                {
                    gfx.Clear(Color.FromArgb(18, 18, 22));
                    for (int ei = 0; ei < effects.Count; ei++)
                    {
                        JObj e = (JObj)effects[ei];
                        double duration = Math.Max(0.05, e.Num("DurationMax", 1));
                        bool loop = e.Num("NumLoops", 0) != 0;
                        double extent, maxLife;
                        List<Layer> layers = BuildLayers(e, emit, ptx, sprites, out extent, out maxLife, missing);
                        double view = Math.Min(24, Math.Max(0.5, extent * 2.15));
                        double total = loop ? duration * 2 : Math.Max(duration * 0.35, Math.Min(duration + maxLife, maxLife + 0.05));
                        Random rnd = new Random(1234 + ei);
                        double simT = 0, dt = 1.0 / 90, bestE = -1, bestT = 0;
                        for (int f = 0; f < frames; f++)
                        {
                            double target = total * (f + 0.5) / frames;
                            while (simT < target) { foreach (Layer L in layers) Step(L, rnd, simT, dt, duration, loop); simT += dt; }
                            float[] buf = new float[cell * cell * 3];
                            foreach (Layer L in layers) if (!L.Additive) Draw(L, buf, cell, cell, view, false);
                            foreach (Layer L in layers) if (L.Additive) Draw(L, buf, cell, cell, view, false);
                            double en = Energy(buf);
                            if (en > bestE) { bestE = en; bestT = target; }
                            using (Bitmap fb = ToBitmap(buf, cell, view, false)) gfx.DrawImage(fb, f * cell, ei * (cell + label) + label);
                            gfx.DrawString(target.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture) + "s", font, tb, f * cell + 3, ei * (cell + label) + label + 2);
                        }
                        // Same simulation again up to the brightest moment, this time seen from above.
                        double e2, m2;
                        List<Layer> again = BuildLayers(e, emit, ptx, sprites, out e2, out m2, missing);
                        rnd = new Random(1234 + ei);
                        simT = 0;
                        while (simT < bestT) { foreach (Layer L in again) Step(L, rnd, simT, dt, duration, loop); simT += dt; }
                        float[] tbuf = new float[cell * cell * 3];
                        foreach (Layer L in again) if (!L.Additive) Draw(L, tbuf, cell, cell, view, true);
                        foreach (Layer L in again) if (L.Additive) Draw(L, tbuf, cell, cell, view, true);
                        using (Bitmap fb = ToBitmap(tbuf, cell, view, true)) gfx.DrawImage(fb, frames * cell, ei * (cell + label) + label);
                        gfx.DrawString("top view " + bestT.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture) + "s", font, tb2, frames * cell + 3, ei * (cell + label) + label + 2);
                        string head = e.Str("Name") + (loop ? "  (loop " : "  (one-shot ") + duration.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture) + "s)  view " + view.ToString("0.#", System.Globalization.CultureInfo.InvariantCulture) + " m, grid 1 m, layers " + layers.Count;
                        gfx.DrawString(head, font, tb, 3, ei * (cell + label) + 3);
                        rep.AppendLine("preview " + head);
                    }
                }
                sheetBmp.Save(outPath, ImageFormat.Png);
            }
            if (missing.Count > 0) rep.AppendLine("preview used stand-in art for game textures: " + string.Join(", ", missing.ToArray()) + (string.IsNullOrEmpty(GameCorePath) ? "  (pass -Core <core.ypt> to draw the real ones)" : ""));
            rep.AppendLine("wrote " + outPath);
            return rep.ToString();
        }
    }
}
