using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;

namespace WeaponForge
{
    // Second sprite library: effect-grade shapes drawn from noise, icon shapes drawn as paths, modifiers that work on
    // any shape, and multi-frame sheets.
    public static class SpriteFx
    {
        public static readonly string[] AnalyticShapes = new string[] {
            "shockwave", "ripple", "swirl", "flare", "beam", "nova", "plasma", "fire", "wisp", "energy_slash", "impact", "glitch", "hexgrid", "pixel", "ribbon_line"
        };

        public static readonly string[] PathShapes = new string[] {
            "magic_circle", "wing", "wings", "flower", "sakura", "lotus", "clover", "gear", "eye", "sword", "fang", "web", "sun", "arrow", "splat", "shuriken",
            "cat", "ghost", "bat", "bone", "holy_cross", "zap", "coin", "dice", "card", "chain", "tomoe", "lantern", "pumpkin", "candy", "anchor"
        };

        public static bool IsAnalytic(string shape) { return Array.IndexOf(AnalyticShapes, shape) >= 0; }

        static float C(float v) { return v < 0 ? 0 : v > 1 ? 1 : v; }

        // Noise that scrolls by (dx, dy) while phase runs 0 to 1 and arrives exactly where it started, so a looping
        // flipbook has no jump between its last and first frame. Two scrolled copies are cross-faded; the division
        // restores the contrast the average loses.
        static float LoopFbm(float x, float y, float dx, float dy, float phase, int seed)
        {
            float ph = phase - (float)Math.Floor(phase);
            if (ph < 1e-5f) return SpriteGen.Fbm(x, y, seed);
            float a = SpriteGen.Fbm(x + dx * ph, y + dy * ph, seed), b = SpriteGen.Fbm(x + dx * (ph - 1), y + dy * (ph - 1), seed);
            float mix = a * (1 - ph) + b * ph;
            return 0.47f + (mix - 0.47f) / (float)Math.Sqrt((1 - ph) * (1 - ph) + ph * ph);
        }
        static float Exp(double v) { return (float)Math.Exp(v); }
        static float Pow(double a, double b) { return (float)Math.Pow(a, b); }

        public static float[] Analytic(string shape, JObj g, int n, int seed)
        {
            float[] m = new float[n * n];
            float th = (float)g.Num("thickness", 0.08);
            float r0 = (float)g.Num("radius", 0.70);
            float phase = (float)g.Num("phase", 0);
            int points = (int)g.Num("points", shape == "swirl" ? 3 : shape == "hexgrid" ? 5 : shape == "pixel" ? 8 : shape == "glitch" ? 11 : 5);
            float detail = (float)g.Num("detail", shape == "nova" ? 7 : 6);
            float sweep = (float)g.Num("sweep", 150);
            float twist = (float)g.Num("twist", 3);
            float sharp = (float)g.Num("sharp", 3);
            float rings = (float)g.Num("rings", 3);
            double rotRad = g.Num("rotation", 0) * Math.PI / 180;
            float rc = (float)Math.Cos(rotRad), rs = (float)Math.Sin(rotRad), asp = (float)Math.Max(0.05, g.Num("aspect", 1));
            const float TwoPi = 6.2831853f;
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float u0 = (x + 0.5f) / n * 2 - 1, v0 = (y + 0.5f) / n * 2 - 1;
                    float u = (u0 * rc + v0 * rs) / asp, v = -u0 * rs + v0 * rc;
                    float r = (float)Math.Sqrt(u * u + v * v);
                    float a = (float)Math.Atan2(v, u);
                    float ca = (float)Math.Cos(a), sa = (float)Math.Sin(a);
                    float val = 0;
                    switch (shape)
                    {
                        case "shockwave":
                        {
                            float sth = g.Has("thickness") ? th : 0.042f;
                            float d = r - r0;
                            float rim = d > 0 ? Exp(-(d * d) / (sth * sth * 0.14f)) : Exp(-(d * d) / (sth * sth * 3.8f));
                            float innerSpokes = d < 0 && d > -0.26f ? Exp(-(d * d) / 0.032f) * Pow(SpriteGen.Noise(ca * 22 + 13, sa * 22 + 7, seed + 9), 2.4) * 0.65f : 0;
                            float nz = SpriteGen.Fbm(ca * detail + 31, sa * detail + 17 + r * 1.8f, seed);
                            val = (rim * C(0.28f + nz * 1.45f) + innerSpokes) * C((0.97f - r) * 10);
                            break;
                        }
                        case "ripple":
                        {
                            float w = 0.5f + 0.5f * (float)Math.Cos(TwoPi * (r * rings - phase));
                            float nz = 0.72f + 0.52f * LoopFbm(ca * 3.5f + 5, sa * 3.5f + 9, 1.5f, -1.5f, phase, seed);
                            val = Pow(w, 9) * nz * Pow(C(0.95f - r), 0.9) * C(r * 6);
                            break;
                        }
                        case "swirl":
                        {
                            float s = (float)Math.Cos(points * (a - twist * (float)Math.Log(r + 0.06f)) - phase * TwoPi);
                            float s2 = (float)Math.Cos(points * 2 * (a - twist * 1.15f * (float)Math.Log(r + 0.09f)) - phase * TwoPi + 1.1f);
                            float arm = Pow(C(0.5f + 0.5f * s), sharp + 1.4f) + Pow(C(0.5f + 0.5f * s2), sharp + 3.0f) * 0.42f;
                            float env = Pow(C(0.94f - r), 1.1) * C(r * 5.5f + 0.12f);
                            float nz = 0.52f + 0.95f * LoopFbm(u * 4.2f, v * 4.2f, 2f, -2f, phase, seed);
                            val = arm * env * nz + Exp(-r * r * 26f) * 0.85f;
                            break;
                        }
                        case "flare":
                        {
                            float fth = g.Has("thickness") ? th : 0.055f;
                            float hs = Exp(-(v * v) / (fth * fth * 0.045f)) * Pow(C(1 - Math.Abs(u) * 1.04f), 1.8) + Exp(-(v * v) / (fth * fth * 0.55f)) * Exp(-Math.Abs(u) * 3.2f) * 0.28f;
                            float vs = Exp(-(u * u) / (fth * fth * 0.055f)) * Pow(C(1 - Math.Abs(v) * 1.45f), 2.2) * 0.65f;
                            float du = (u + v) * 0.7071068f, dv = (v - u) * 0.7071068f;
                            float diag = (Exp(-(dv * dv) / (fth * fth * 0.04f)) * Pow(C(1 - Math.Abs(du) * 2.3f), 2.2) + Exp(-(du * du) / (fth * fth * 0.04f)) * Pow(C(1 - Math.Abs(dv) * 2.3f), 2.2)) * 0.35f;
                            float core = Exp(-r * r * 36f) + Exp(-r * r * 8f) * 0.22f;
                            float halo = Exp(-Math.Pow((r - 0.38f) / 0.022f, 2)) * 0.10f;
                            val = (hs + vs + diag + core + halo) * C((1 - Math.Max(Math.Abs(u), Math.Abs(v))) * 9);
                            break;
                        }
                        case "beam":
                        {
                            float w = (g.Has("thickness") ? th : 0.065f) * 2.0f;
                            float warpU = u + (LoopFbm(u * 3f + 1, v * 2.2f, 0, 3f, phase, seed + 13) - 0.47f) * w * 0.45f;
                            float core = Exp(-(warpU * warpU) / (w * w * 0.14f));
                            float sheath = Exp(-(warpU * warpU) / (w * w * 1.65f)) * 0.38f;
                            float stri = 0.52f + 0.88f * Pow(SpriteGen.Noise(warpU * 18f, v * 1.8f + phase * 4f, seed), 1.4);
                            float vert = Pow(C(1 - Math.Abs(v) * 1.04f), 1.35);
                            val = (core * stri + sheath * (0.65f + 0.35f * stri)) * vert;
                            break;
                        }
                        case "nova":
                        {
                            float rays = Pow(SpriteGen.Noise(ca * detail * 1.4f + 31, sa * detail * 1.4f + 17, seed), 3.6) * 2.1f;
                            float fine = Pow(SpriteGen.Noise(ca * detail * 4.2f + 5, sa * detail * 4.2f + 9, seed + 3), 2.6) * 0.85f;
                            val = (rays * 0.78f + fine * 0.42f) * Pow(C(0.95f - r), 1.55) + Exp(-r * r * 24f) * 0.92f;
                            break;
                        }
                        case "plasma":
                        {
                            float f1 = LoopFbm(u * 3.2f, v * 3.2f, 2.0f, -2.0f, phase, seed);
                            float f2 = LoopFbm(u * 6.4f + 4.1f, v * 6.4f - 2.7f, -3.0f, 2.0f, phase, seed + 19);
                            float r1 = Pow(1 - Math.Abs(2 * f1 - 1), 7.5) * 1.45f;
                            float r2 = Pow(1 - Math.Abs(2 * f2 - 1), 9.0) * 0.85f;
                            float env = Pow(C(0.92f - r * r), 1.35);
                            val = (r1 + r2 + Exp(-r * r * 18f) * 0.55f) * env * C((0.94f - r) * 8);
                            break;
                        }
                        case "fire":
                        {
                            // Turbulent multi-strand flame with vertical tongues, dark erosion channels and seamless upward loop.
                            float hh = (0.88f - v) / 1.76f;
                            if (hh <= -0.02f || hh >= 0.98f) break;
                            float h01 = C(hh);
                            float sway = (LoopFbm(u * 1.5f + 2.1f, v * 1.1f, 0, 3f, phase, seed) - 0.47f) * (0.16f + 0.62f * h01);
                            float warpX = (LoopFbm(u * 3.8f - 5.2f, v * 1.8f, 0, 6f, phase, seed + 3) - 0.47f) * (0.08f + 0.28f * h01);
                            float fx2 = u + sway + warpX;
                            float width = 0.50f * Pow(C(1 - h01 * 0.92f), 0.58) * C(0.32f + h01 * 5.2f) + 0.016f;
                            float d = Math.Abs(fx2) / width;
                            if (d >= 1.45f) break;
                            float env = C(1 - d * d * 0.82f);
                            float n1 = LoopFbm(fx2 * 5.2f + 4.3f, v * 1.35f, 0, 6f, phase, seed + 7);
                            float n2 = LoopFbm(fx2 * 10.5f + 9.1f, v * 2.7f, 0, 12f, phase, seed + 15);
                            float strands = Pow(1 - Math.Abs(2 * n1 - 0.94f), 1.9);
                            float fine = Pow(1 - Math.Abs(2 * n2 - 0.94f), 2.5);
                            float carve = C((n1 * 0.76f + n2 * 0.46f - (0.20f + 0.34f * h01 * h01 + 0.28f * d * d)) * 3.2f);
                            float coreBase = Exp(-(fx2 * fx2) / 0.032f) * Exp(-Pow((h01 - 0.20f) / 0.28f, 2)) * 0.62f;
                            val = C((env * (0.22f + strands * 0.78f + fine * 0.44f) * carve * (1.18f - h01 * 0.34f) + coreBase) * C((hh + 0.02f) * 14) * C((0.96f - h01) * 7));
                            break;
                        }
                        case "wisp":
                        {
                            float wth = g.Has("thickness") ? th * 0.55f : 0.046f;
                            float s = (v + 1) / 2;
                            float vEnv = Pow(C(1 - v * v), 1.25);
                            float acc = 0;
                            for (int k = 0; k < 3; k++)
                            {
                                float phOff = k * 2.094f;
                                float turb = (LoopFbm(u * 2.4f + k * 3.7f, v * 2.2f, 0, 3f, phase, seed + k * 13) - 0.47f) * 0.28f;
                                float cx = (0.24f - k * 0.05f) * (float)Math.Sin(v * (2.8f + k * 0.9f) + phase * TwoPi + phOff) * (0.35f + 0.65f * (1 - s)) + turb;
                                float wd = Math.Max(0.012f, wth * (0.45f + 0.95f * s) * (k == 0 ? 1.0f : 0.68f));
                                float d = (u - cx) / wd;
                                float dens = 0.42f + 0.78f * LoopFbm(u * 5.5f + k * 2f, v * 4.5f, 0, 4f, phase, seed + 31 + k * 7);
                                acc += Exp(-d * d * 1.4f) * dens * (k == 0 ? 0.95f : 0.58f);
                            }
                            val = C(acc) * vEnv * C((0.96f - Math.Abs(u)) * 6);
                            break;
                        }
                        case "ribbon_line":
                        {
                            float rth = g.Has("thickness") ? th : 0.14f;
                            float xAng = (u0 + 1f) * 0.5f * TwoPi;
                            float cx = (float)Math.Cos(xAng), sx2 = (float)Math.Sin(xAng);
                            float flow = 0.78f + 0.32f * LoopFbm(cx * 1.8f + 3.1f, sx2 * 1.8f + v * 2.2f, 2f, 0f, phase, seed);
                            float fine = 0.84f + 0.24f * SpriteGen.Noise(cx * 5.2f + 11f, sx2 * 5.2f + v * 6.5f, seed + 19);
                            float sway = (SpriteGen.Noise(cx * 1.6f + 7f, sx2 * 1.6f + 2f, seed + 5) - 0.5f) * rth * 0.35f;
                            float dv = v - sway;
                            float core = Exp(-(dv * dv) / Math.Max(0.0008f, rth * rth * 0.22f));
                            float sheath = Exp(-(dv * dv) / Math.Max(0.004f, rth * rth * 2.6f)) * 0.56f;
                            float vFade = Pow(C(1f - Math.Abs(v) * 1.08f), 1.6);
                            val = C((core * 1.05f + sheath * flow) * fine * vFade);
                            break;
                        }
                        case "energy_slash":
                        {
                            float eth = g.Has("thickness") ? th * 0.72f : 0.052f;
                            float R = 0.85f, cy = 0.28f;
                            float ru = u, rv = v - cy;
                            float rr = (float)Math.Sqrt(ru * ru + rv * rv);
                            float deg = (float)(Math.Atan2(rv, ru) * 180 / Math.PI);
                            float t = (deg - (-90 - sweep / 2)) / sweep;
                            if (t <= 0 || t >= 1) break;
                            float taper = Pow((float)Math.Sin(Math.PI * Math.Pow(t, 0.76)), 1.25);
                            float wOut = eth * 0.28f, wIn = eth * 3.6f * taper + 0.001f;
                            float d = rr - R;
                            float wake = d > 0 ? Exp(-(d * d) / (wOut * wOut * 0.08f)) : Exp(-(d * d) / (wIn * wIn * 0.42f));
                            float shear = Pow(SpriteGen.Noise(t * 5.5f + 1.3f, rr * 58f, seed), 1.65);
                            float fine = SpriteGen.Noise(t * 16f + 7f, rr * 110f, seed + 11);
                            float rim = Exp(-(d * d) / (eth * eth * 0.014f));
                            float subArc = Exp(-Pow((d + eth * 1.35f * taper) / Math.Max(0.004f, eth * 0.16f), 2)) * taper * (0.35f + 0.65f * fine) * 0.55f;
                            val = C(wake * (0.28f + 1.05f * shear) * taper * 0.85f + rim * taper * 1.05f + subArc);
                            break;
                        }
                        case "impact":
                        {
                            float n1 = SpriteGen.Noise(ca * 11 + 31, sa * 11 + 17, seed);
                            float n2 = SpriteGen.Noise(ca * 29 + 3, sa * 29 + 8, seed + 7);
                            float spike = Pow(n1, 4.8) * 0.82f + Pow(n2, 6.0) * 0.42f;
                            float len = 0.10f + spike;
                            float ray = C((len - r) * 11f) * Exp(-r * 1.35f) * (0.45f + 0.75f * Pow(n2, 1.8));
                            val = ray + Exp(-r * r * 34f) * 0.95f + Exp(-r * r * 9f) * 0.22f;
                            break;
                        }
                        case "glitch":
                        {
                            float fy = (v + 1) / 2 * points;
                            int row = (int)Math.Floor(fy);
                            float inRow = fy - row;
                            if (inRow < 0.14f || inRow > 0.86f || SpriteGen.Hash(row, 3, seed) < 0.30f) break;
                            float start = -0.88f + 0.9f * SpriteGen.Hash(row, 1, seed);
                            float len = 0.25f + 0.95f * SpriteGen.Hash(row, 2, seed);
                            if (u < start || u > Math.Min(0.9f, start + len)) break;
                            int seg = (int)Math.Floor((u - start) * 7);
                            val = SpriteGen.Hash(row * 31 + seg, 5, seed) > 0.22f ? 0.55f + 0.45f * SpriteGen.Hash(row * 17 + seg, 9, seed) : 0;
                            break;
                        }
                        case "hexgrid":
                        {
                            float px = u * points, py = v * points;
                            const float RX = 1f, RY = 1.7320508f;
                            float ax = px - RX * (float)Math.Floor(px / RX) - RX * 0.5f, ay = py - RY * (float)Math.Floor(py / RY) - RY * 0.5f;
                            float bx = (px - RX * 0.5f) - RX * (float)Math.Floor((px - RX * 0.5f) / RX) - RX * 0.5f, by = (py - RY * 0.5f) - RY * (float)Math.Floor((py - RY * 0.5f) / RY) - RY * 0.5f;
                            bool useA = ax * ax + ay * ay < bx * bx + by * by;
                            float gx = Math.Abs(useA ? ax : bx), gy = Math.Abs(useA ? ay : by);
                            float cx = px - (useA ? ax : bx), cy2 = py - (useA ? ay : by);
                            float c = Math.Max(gx * 0.5f + gy * 0.8660254f, gx);
                            float line = C((c - (0.5f - th * 1.4f)) / 0.04f);
                            float fill = SpriteGen.Hash((int)Math.Round(cx * 2), (int)Math.Round(cy2 * 2), seed) > 0.78f ? 0.45f : 0;
                            val = Math.Max(line, fill * C((0.47f - c) * 30)) * Pow(C(1.02f - r), 0.7);
                            break;
                        }
                        case "pixel":
                        {
                            float cu = ((float)Math.Floor(u * points * 0.5f + 0.5f)) / (points * 0.5f), cv = ((float)Math.Floor(v * points * 0.5f + 0.5f)) / (points * 0.5f);
                            float rq = (float)Math.Sqrt(cu * cu + cv * cv);
                            if (rq > 0.84f) break;
                            int ix = (int)Math.Round(cu * points), iy = (int)Math.Round(cv * points);
                            if (rq > 0.5f && SpriteGen.Hash(ix, iy, seed) < (rq - 0.5f) * 2.2f) break;
                            float lu = Math.Abs(u - cu) * points * 0.5f, lv = Math.Abs(v - cv) * points * 0.5f;
                            val = (lu < 0.44f && lv < 0.44f) ? 0.7f + 0.3f * SpriteGen.Hash(ix, iy, seed + 4) : 0;
                            break;
                        }
                    }
                    m[y * n + x] = C(val);
                }
            return m;
        }

        static float Sample(float[] m, int n, float x, float y)
        {
            if (x < 0 || y < 0 || x > n - 1 || y > n - 1) return 0;
            int xi = (int)x, yi = (int)y;
            int x1 = Math.Min(n - 1, xi + 1), y1 = Math.Min(n - 1, yi + 1);
            float fx = x - xi, fy = y - yi;
            float a = m[yi * n + xi], b = m[yi * n + x1], c = m[y1 * n + xi], d = m[y1 * n + x1];
            return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
        }

        // Modifiers, applied in this order: kaleido, mirror, warp, erode, streaks, fade, toon.
        public static float[] Modify(float[] mask, int n, JObj g, int seed)
        {
            float phase = (float)g.Num("phase", 0);
            int kal = (int)g.Num("kaleido", 0);
            string mirror = g.Str("mirror");
            if (kal > 1 || mirror != null)
            {
                float[] o = new float[mask.Length];
                double wedge = Math.PI * 2 / Math.Max(1, kal);
                for (int y = 0; y < n; y++)
                    for (int x = 0; x < n; x++)
                    {
                        float u = (x + 0.5f) / n * 2 - 1, v = (y + 0.5f) / n * 2 - 1;
                        if (mirror == "x" || mirror == "both") u = -Math.Abs(u);
                        if (mirror == "y" || mirror == "both") v = -Math.Abs(v);
                        if (kal > 1)
                        {
                            double r = Math.Sqrt(u * u + v * v), a = Math.Atan2(v, u) + Math.PI / 2;
                            a = ((a % wedge) + wedge) % wedge;
                            if (a > wedge / 2) a = wedge - a;
                            a -= Math.PI / 2;
                            u = (float)(Math.Cos(a) * r);
                            v = (float)(Math.Sin(a) * r);
                        }
                        o[y * n + x] = Sample(mask, n, (u + 1) / 2 * n - 0.5f, (v + 1) / 2 * n - 0.5f);
                    }
                mask = o;
            }
            float warp = (float)g.Num("warp", 0);
            if (warp > 0)
            {
                float ws = (float)g.Num("warpScale", 3);
                float[] o = new float[mask.Length];
                for (int y = 0; y < n; y++)
                    for (int x = 0; x < n; x++)
                    {
                        float u = (x + 0.5f) / n * 2 - 1, v = (y + 0.5f) / n * 2 - 1;
                        float dx = (SpriteGen.Fbm(u * ws + 3.7f, v * ws + phase * 2, seed + 41) - 0.48f) * warp * n;
                        float dy = (SpriteGen.Fbm(u * ws - 8.1f, v * ws + 5.3f + phase * 2, seed + 59) - 0.48f) * warp * n;
                        o[y * n + x] = Sample(mask, n, x + dx, y + dy);
                    }
                mask = o;
            }
            float erode = (float)g.Num("erode", 0);
            float streaks = (float)g.Num("streaks", 0);
            string fade = g.Str("fade");
            float fadePow = (float)g.Num("fadePower", 1.5);
            int toon = (int)g.Num("toon", 0);
            if (erode <= 0 && streaks <= 0 && fade == null && toon <= 0) return mask;
            float es = (float)g.Num("erodeScale", 4);
            string smode = g.Str("streakMode") ?? "linear";
            double sang = g.Num("streakAngle", 0) * Math.PI / 180;
            float sc = (float)Math.Cos(sang), ss = (float)Math.Sin(sang);
            float sfreq = (float)g.Num("streakFreq", 26);
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    int i = y * n + x;
                    float m = mask[i];
                    if (m <= 0) continue;
                    float u = (x + 0.5f) / n * 2 - 1, v = (y + 0.5f) / n * 2 - 1;
                    if (erode > 0)
                    {
                        float nz = SpriteGen.Fbm(u * es + 13, v * es + 29 + phase * 3, seed + 23);
                        m *= C((nz - erode * 0.75f + 0.12f) * 5);
                    }
                    if (streaks > 0)
                    {
                        float s;
                        if (smode == "radial") { float a = (float)Math.Atan2(v, u); s = SpriteGen.Noise((float)Math.Cos(a) * sfreq * 0.4f + 7, (float)Math.Sin(a) * sfreq * 0.4f + 3, seed + 31); }
                        else if (smode == "ring") s = SpriteGen.Noise((float)Math.Sqrt(u * u + v * v) * sfreq, 1.5f, seed + 31);
                        else { float al = u * sc + v * ss, ac = -u * ss + v * sc; s = SpriteGen.Noise(al * 1.2f + 5, ac * sfreq, seed + 31); }
                        m *= 1 - streaks + streaks * C(s * 1.7f);
                    }
                    if (fade != null)
                    {
                        float f = 1;
                        switch (fade)
                        {
                            case "top": f = (v + 1) / 2; break;
                            case "bottom": f = (1 - v) / 2; break;
                            case "left": f = (u + 1) / 2; break;
                            case "right": f = (1 - u) / 2; break;
                            case "out": f = C(1 - (float)Math.Sqrt(u * u + v * v)); break;
                            case "in": f = C((float)Math.Sqrt(u * u + v * v)); break;
                        }
                        m *= Pow(C(f), fadePow);
                    }
                    if (toon > 0)
                    {
                        float q = (float)Math.Floor(m * (toon + 0.999f)) / toon;
                        m = C(q);
                    }
                    mask[i] = C(m);
                }
            return mask;
        }

        static GraphicsPath Leaf(double len, double width, double skew)
        {
            GraphicsPath p = new GraphicsPath(FillMode.Winding);
            p.AddBezier(SpriteGen.P(0, 0), SpriteGen.P(width, -len * 0.25), SpriteGen.P(width * (0.85 + skew), -len * 0.80), SpriteGen.P(0, -len));
            p.AddBezier(SpriteGen.P(0, -len), SpriteGen.P(-width * (0.85 - skew), -len * 0.80), SpriteGen.P(-width, -len * 0.25), SpriteGen.P(0, 0));
            p.CloseFigure();
            return p;
        }

        static void Place(GraphicsPath target, GraphicsPath item, double x, double y, double deg, double scale)
        {
            using (Matrix m = new Matrix())
            {
                m.Translate((float)x, (float)y);
                m.Rotate((float)deg);
                m.Scale((float)scale, (float)scale);
                item.Transform(m);
            }
            target.AddPath(item, false);
            item.Dispose();
        }

        static void Circle(GraphicsPath p, double x, double y, double r) { p.AddEllipse((float)(x - r), (float)(y - r), (float)(2 * r), (float)(2 * r)); }

        static void RingAt(GraphicsPath p, double x, double y, double r, double width)
        {
            using (GraphicsPath line = new GraphicsPath())
            {
                line.AddEllipse((float)(x - r), (float)(y - r), (float)(2 * r), (float)(2 * r));
                SpriteGen.WidenPath(line, width, LineCap.Flat, LineCap.Flat);
                p.AddPath(line, false);
            }
        }

        static GraphicsPath Glyph(string text, string font, bool bold, double size)
        {
            GraphicsPath p = new GraphicsPath(FillMode.Winding);
            using (FontFamily ff = new FontFamily(font ?? "Segoe UI Symbol"))
            using (StringFormat sf = new StringFormat(StringFormat.GenericTypographic))
                p.AddString(text, ff, (int)(bold ? FontStyle.Bold : FontStyle.Regular), 1.0f, new PointF(0, 0), sf);
            RectangleF b = p.GetBounds();
            if (b.Width > 0 && b.Height > 0)
            {
                float s = (float)(size / Math.Max(b.Width, b.Height));
                using (Matrix m = new Matrix())
                {
                    m.Scale(s, s);
                    m.Translate(-(b.Left + b.Width / 2), -(b.Top + b.Height / 2));
                    p.Transform(m);
                }
            }
            return p;
        }

        static GraphicsPath RoundRect(double x, double y, double w, double h, double r)
        {
            GraphicsPath p = new GraphicsPath(FillMode.Winding);
            float d = (float)(r * 2), fx = (float)x, fy = (float)y, fw = (float)w, fh = (float)h;
            p.AddArc(fx, fy, d, d, 180, 90);
            p.AddArc(fx + fw - d, fy, d, d, 270, 90);
            p.AddArc(fx + fw - d, fy + fh - d, d, d, 0, 90);
            p.AddArc(fx, fy + fh - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }

        public static GraphicsPath Path(string shape, JObj g, Random rnd)
        {
            int points = (int)g.Num("points", shape == "magic_circle" ? 6 : shape == "gear" ? 8 : shape == "sun" ? 12 : shape == "clover" ? 4 : shape == "flower" ? 6 : 5);
            double thick = g.Num("thickness", 0.08);
            GraphicsPath p = new GraphicsPath(FillMode.Winding);
            switch (shape)
            {
                case "magic_circle":
                {
                    double mth = g.Has("thickness") ? thick : 0.048;
                    for (int s = 0; s < points; s++) SpriteGen.AddArc(p, 0.91, s * (360.0 / points) + 4, 360.0 / points - 10, mth * 0.18);
                    SpriteGen.AddArc(p, 0.87, 0, 360, mth * 0.34);
                    SpriteGen.AddArc(p, 0.82, 0, 360, mth * 0.14);
                    SpriteGen.AddArc(p, 0.62, 0, 360, mth * 0.22);
                    SpriteGen.AddArc(p, 0.58, 0, 360, mth * 0.12);
                    int ticks = points * 8;
                    for (int i = 0; i < ticks; i++)
                    {
                        double ta = Math.PI * 2 * i / ticks;
                        double tlen = i % 4 == 0 ? 0.042 : 0.020;
                        SpriteGen.AddLine(p, Math.Cos(ta) * 0.82, Math.Sin(ta) * 0.82, Math.Cos(ta) * (0.82 + tlen), Math.Sin(ta) * (0.82 + tlen), mth * 0.12);
                    }
                    string glyphs = g.Str("text") ?? "ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ";
                    int count = (int)g.Num("glyphs", 20);
                    int off = rnd.Next(glyphs.Length);
                    for (int i = 0; i < count; i++)
                    {
                        double a = 360.0 * i / count;
                        string ch = glyphs.Substring((off + i * 5) % glyphs.Length, 1);
                        try
                        {
                            GraphicsPath gp = Glyph(ch, g.Str("font"), true, 0.108);
                            Place(p, gp, Math.Cos((a - 90) * Math.PI / 180) * 0.72, Math.Sin((a - 90) * Math.PI / 180) * 0.72, a, 1);
                        }
                        catch { }
                    }
                    int step = points % 2 == 0 ? 2 : (points > 4 ? 2 : 1);
                    for (int i = 0; i < points; i++)
                    {
                        double a0 = Math.PI * 2 * i / points - Math.PI / 2, a1 = Math.PI * 2 * (i + step) / points - Math.PI / 2;
                        SpriteGen.AddLine(p, Math.Cos(a0) * 0.58, Math.Sin(a0) * 0.58, Math.Cos(a1) * 0.58, Math.Sin(a1) * 0.58, mth * 0.22);
                        double aNext = Math.PI * 2 * (i + 1) / points - Math.PI / 2;
                        SpriteGen.AddLine(p, Math.Cos(a0) * 0.58, Math.Sin(a0) * 0.58, Math.Cos(aNext) * 0.58, Math.Sin(aNext) * 0.58, mth * 0.12);
                        RingAt(p, Math.Cos(a0) * 0.58, Math.Sin(a0) * 0.58, 0.055, mth * 0.16);
                        double am = a0 + Math.PI / points;
                        SpriteGen.AddLine(p, Math.Cos(am) * 0.19, Math.Sin(am) * 0.19, Math.Cos(am) * 0.35, Math.Sin(am) * 0.35, mth * 0.15);
                    }
                    SpriteGen.AddArc(p, 0.35, 0, 360, mth * 0.18);
                    SpriteGen.AddArc(p, 0.19, 0, 360, mth * 0.22);
                    using (GraphicsPath s = SpriteGen.Star(points, 0.035, 0.125)) p.AddPath(s, false);
                    return p;
                }
                case "wing":
                {
                    // Feathers hang from an arm that rises from the shoulder (bottom left) to the wrist (top right).
                    int prim = 11;
                    for (int i = 0; i < prim; i++)
                    {
                        double t = (double)i / (prim - 1);
                        double ax = -0.82 + 1.20 * t, ay = 0.10 - 0.86 * Math.Pow(t, 0.75);
                        double deg = 168 - 92 * Math.Pow(t, 1.15);
                        double len = 0.50 + 0.62 * Math.Sin(Math.PI * (0.18 + 0.62 * t));
                        Place(p, Leaf(len, 0.075 + 0.02 * t, 0.2), ax, ay, deg, 1);
                    }
                    for (int i = 0; i < 9; i++)
                    {
                        double t = (double)i / 8;
                        double ax = -0.80 + 1.02 * t, ay = 0.08 - 0.80 * Math.Pow(t, 0.75);
                        Place(p, Leaf(0.30 + 0.12 * Math.Sin(Math.PI * t), 0.07, 0.1), ax, ay, 172 - 70 * t, 1);
                    }
                    using (GraphicsPath arm = SpriteGen.Curve(false, 0.5f, -0.84, 0.12, -0.40, -0.34, 0.08, -0.62, 0.40, -0.78))
                    {
                        SpriteGen.WidenPath(arm, 0.10, LineCap.Round, LineCap.Round);
                        p.AddPath(arm, false);
                    }
                    return p;
                }
                case "wings":
                {
                    // A matched pair: the single wing shrunk into each half and mirrored about the centre line.
                    foreach (int side in new int[] { 1, -1 })
                    {
                        GraphicsPath w = Path("wing", g, rnd);
                        using (Matrix m = new Matrix())
                        {
                            m.Translate(side * 0.47f, 0.08f);
                            m.Scale(side * 0.52f, 0.52f);
                            w.Transform(m);
                        }
                        if (side < 0) w.Reverse();
                        p.AddPath(w, false);
                        w.Dispose();
                    }
                    return p;
                }
                case "flower":
                    for (int i = 0; i < points; i++) Place(p, Leaf(0.84, 0.30, 0), 0, 0, 360.0 * i / points, 1);
                    {
                        Region r = new Region(p);
                        using (GraphicsPath cut = new GraphicsPath()) { Circle(cut, 0, 0, 0.17); r.Exclude(cut); }
                        using (GraphicsPath add = new GraphicsPath()) { Circle(add, 0, 0, 0.10); r.Union(add); }
                        p.Dispose();
                        SpriteGen.SetRegion(r);
                        return new GraphicsPath();
                    }
                case "sakura":
                    for (int i = 0; i < 5; i++)
                    {
                        GraphicsPath petal = new GraphicsPath(FillMode.Winding);
                        petal.AddBezier(SpriteGen.P(0, -0.08), SpriteGen.P(-0.44, -0.30), SpriteGen.P(-0.40, -0.74), SpriteGen.P(-0.13, -0.88));
                        petal.AddLine(SpriteGen.P(-0.13, -0.88), SpriteGen.P(0, -0.74));
                        petal.AddLine(SpriteGen.P(0, -0.74), SpriteGen.P(0.13, -0.88));
                        petal.AddBezier(SpriteGen.P(0.13, -0.88), SpriteGen.P(0.40, -0.74), SpriteGen.P(0.44, -0.30), SpriteGen.P(0, -0.08));
                        petal.CloseFigure();
                        Place(p, petal, 0, 0, 72.0 * i, 1);
                    }
                    {
                        Region r = new Region(p);
                        using (GraphicsPath cut = new GraphicsPath())
                        {
                            Circle(cut, 0, 0, 0.07);
                            for (int i = 0; i < 5; i++) { double a = (72.0 * i - 90) * Math.PI / 180; Circle(cut, Math.Cos(a) * 0.20, Math.Sin(a) * 0.20, 0.028); }
                            r.Exclude(cut);
                        }
                        p.Dispose();
                        SpriteGen.SetRegion(r);
                        return new GraphicsPath();
                    }
                case "lotus":
                    for (int i = 0; i < 8; i++) Place(p, Leaf(0.86, 0.20, 0), 0, 0, 45.0 * i, 1);
                    for (int i = 0; i < 8; i++) Place(p, Leaf(0.60, 0.19, 0), 0, 0, 45.0 * i + 22.5, 1);
                    {
                        Region r = new Region(p);
                        using (GraphicsPath cut = new GraphicsPath(FillMode.Winding))
                        {
                            for (int i = 0; i < 8; i++) { GraphicsPath inner = Leaf(0.36, 0.085, 0); Place(cut, inner, 0, 0, 45.0 * i, 1); }
                            r.Exclude(cut);
                        }
                        using (GraphicsPath add = new GraphicsPath()) { Circle(add, 0, 0, 0.07); r.Union(add); }
                        p.Dispose();
                        SpriteGen.SetRegion(r);
                        return new GraphicsPath();
                    }
                case "clover":
                    for (int i = 0; i < points; i++)
                    {
                        GraphicsPath h = new GraphicsPath(FillMode.Winding);
                        h.AddBezier(SpriteGen.P(0, 0), SpriteGen.P(-0.62, -0.30), SpriteGen.P(-0.50, -0.92), SpriteGen.P(0, -0.60));
                        h.AddBezier(SpriteGen.P(0, -0.60), SpriteGen.P(0.50, -0.92), SpriteGen.P(0.62, -0.30), SpriteGen.P(0, 0));
                        h.CloseFigure();
                        Place(p, h, 0, -0.06, 360.0 * i / points + (points == 3 ? 0 : 45), 0.92);
                    }
                    using (GraphicsPath stem = SpriteGen.Curve(false, 0.5f, 0, -0.04, 0.06, 0.40, 0.24, 0.84)) { SpriteGen.WidenPath(stem, 0.07, LineCap.Round, LineCap.Round); p.AddPath(stem, false); }
                    return p;
                case "gear":
                {
                    int teeth = Math.Max(5, points);
                    List<PointF> pts = new List<PointF>();
                    for (int i = 0; i < teeth; i++)
                    {
                        double a = Math.PI * 2 * i / teeth, w = Math.PI * 2 / teeth;
                        pts.Add(SpriteGen.P(Math.Cos(a - w * 0.30) * 0.66, Math.Sin(a - w * 0.30) * 0.66));
                        pts.Add(SpriteGen.P(Math.Cos(a - w * 0.18) * 0.86, Math.Sin(a - w * 0.18) * 0.86));
                        pts.Add(SpriteGen.P(Math.Cos(a + w * 0.18) * 0.86, Math.Sin(a + w * 0.18) * 0.86));
                        pts.Add(SpriteGen.P(Math.Cos(a + w * 0.30) * 0.66, Math.Sin(a + w * 0.30) * 0.66));
                    }
                    p.AddPolygon(pts.ToArray());
                    Region r = new Region(p);
                    using (GraphicsPath cut = new GraphicsPath()) { Circle(cut, 0, 0, 0.40); r.Exclude(cut); }
                    using (GraphicsPath add = new GraphicsPath(FillMode.Winding))
                    {
                        Circle(add, 0, 0, 0.17);
                        for (int i = 0; i < 4; i++) { double a = Math.PI / 2 * i + Math.PI / 4; SpriteGen.AddLine(add, 0, 0, Math.Cos(a) * 0.44, Math.Sin(a) * 0.44, 0.09); }
                        r.Union(add);
                    }
                    using (GraphicsPath cut = new GraphicsPath()) { Circle(cut, 0, 0, 0.07); r.Exclude(cut); }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "eye":
                {
                    p.AddBezier(SpriteGen.P(-0.88, 0), SpriteGen.P(-0.40, -0.66), SpriteGen.P(0.40, -0.66), SpriteGen.P(0.88, 0));
                    p.AddBezier(SpriteGen.P(0.88, 0), SpriteGen.P(0.40, 0.66), SpriteGen.P(-0.40, 0.66), SpriteGen.P(-0.88, 0));
                    p.CloseFigure();
                    Region r = new Region(p);
                    using (GraphicsPath cut = new GraphicsPath())
                    {
                        cut.AddBezier(SpriteGen.P(-0.70, 0), SpriteGen.P(-0.32, -0.50), SpriteGen.P(0.32, -0.50), SpriteGen.P(0.70, 0));
                        cut.AddBezier(SpriteGen.P(0.70, 0), SpriteGen.P(0.32, 0.50), SpriteGen.P(-0.32, 0.50), SpriteGen.P(-0.70, 0));
                        cut.CloseFigure();
                        r.Exclude(cut);
                    }
                    using (GraphicsPath iris = new GraphicsPath()) { Circle(iris, 0, 0, 0.34); r.Union(iris); }
                    using (GraphicsPath pupil = new GraphicsPath())
                    {
                        if (g.Num("slit", 0) != 0) pupil.AddEllipse(-0.07f, -0.30f, 0.14f, 0.60f); else Circle(pupil, 0, 0, 0.15);
                        r.Exclude(pupil);
                    }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "sword":
                    p.AddPolygon(new PointF[] { SpriteGen.P(0, -0.92), SpriteGen.P(0.09, -0.74), SpriteGen.P(0.085, 0.36), SpriteGen.P(-0.085, 0.36), SpriteGen.P(-0.09, -0.74) });
                    p.AddPolygon(new PointF[] { SpriteGen.P(-0.36, 0.34), SpriteGen.P(0.36, 0.34), SpriteGen.P(0.30, 0.45), SpriteGen.P(-0.30, 0.45) });
                    p.AddRectangle(new RectangleF(-0.05f, 0.45f, 0.10f, 0.32f));
                    Circle(p, 0, 0.83, 0.085);
                    return p;
                case "fang":
                    p.AddBezier(SpriteGen.P(-0.34, -0.82), SpriteGen.P(-0.30, -0.10), SpriteGen.P(0.02, 0.50), SpriteGen.P(0.36, 0.88));
                    p.AddBezier(SpriteGen.P(0.36, 0.88), SpriteGen.P(0.30, 0.30), SpriteGen.P(0.34, -0.40), SpriteGen.P(0.30, -0.82));
                    p.AddBezier(SpriteGen.P(0.30, -0.82), SpriteGen.P(0.10, -0.92), SpriteGen.P(-0.16, -0.92), SpriteGen.P(-0.34, -0.82));
                    p.CloseFigure();
                    return p;
                case "web":
                {
                    int spokes = 8;
                    for (int i = 0; i < spokes; i++) { double a = Math.PI * 2 * i / spokes; SpriteGen.AddLine(p, 0, 0, Math.Cos(a) * 0.88, Math.Sin(a) * 0.88, thick * 0.28); }
                    foreach (double rr in new double[] { 0.22, 0.42, 0.62, 0.82 })
                        for (int i = 0; i < spokes; i++)
                        {
                            double a0 = Math.PI * 2 * i / spokes, a1 = Math.PI * 2 * (i + 1) / spokes, am = (a0 + a1) / 2;
                            using (GraphicsPath c = SpriteGen.Curve(false, 0.6f, Math.Cos(a0) * rr, Math.Sin(a0) * rr, Math.Cos(am) * rr * 0.86, Math.Sin(am) * rr * 0.86, Math.Cos(a1) * rr, Math.Sin(a1) * rr))
                            {
                                SpriteGen.WidenPath(c, thick * 0.22, LineCap.Round, LineCap.Round);
                                p.AddPath(c, false);
                            }
                        }
                    return p;
                }
                case "sun":
                    Circle(p, 0, 0, 0.40);
                    for (int i = 0; i < points; i++)
                    {
                        double a = Math.PI * 2 * i / points, w = Math.PI / points * 0.55;
                        double len = i % 2 == 0 ? 0.88 : 0.70;
                        p.AddPolygon(new PointF[] { SpriteGen.P(Math.Cos(a - w) * 0.48, Math.Sin(a - w) * 0.48), SpriteGen.P(Math.Cos(a) * len, Math.Sin(a) * len), SpriteGen.P(Math.Cos(a + w) * 0.48, Math.Sin(a + w) * 0.48) });
                    }
                    return p;
                case "arrow":
                    foreach (double dy in new double[] { -0.20, 0.34 })
                        p.AddPolygon(new PointF[] { SpriteGen.P(-0.72, 0.10 + dy), SpriteGen.P(0, -0.62 + dy), SpriteGen.P(0.72, 0.10 + dy), SpriteGen.P(0.72, 0.38 + dy), SpriteGen.P(0, -0.34 + dy), SpriteGen.P(-0.72, 0.38 + dy) });
                    return p;
                case "splat":
                {
                    int k = 16;
                    PointF[] pts = new PointF[k];
                    for (int i = 0; i < k; i++)
                    {
                        double a = Math.PI * 2 * i / k, rr = i % 2 == 0 ? 0.42 + rnd.NextDouble() * 0.40 : 0.26 + rnd.NextDouble() * 0.16;
                        pts[i] = SpriteGen.P(Math.Cos(a) * rr, Math.Sin(a) * rr);
                    }
                    p.AddClosedCurve(pts, 0.55f);
                    for (int i = 0; i < 9; i++)
                    {
                        double a = rnd.NextDouble() * Math.PI * 2, rr = 0.60 + rnd.NextDouble() * 0.26, s = 0.02 + rnd.NextDouble() * 0.06;
                        Circle(p, Math.Cos(a) * rr, Math.Sin(a) * rr, s);
                    }
                    return p;
                }
                case "shuriken":
                {
                    PointF[] pts = new PointF[8];
                    for (int i = 0; i < 4; i++)
                    {
                        double a = Math.PI / 2 * i - Math.PI / 2;
                        pts[i * 2] = SpriteGen.P(Math.Cos(a) * 0.88, Math.Sin(a) * 0.88);
                        pts[i * 2 + 1] = SpriteGen.P(Math.Cos(a + 0.95) * 0.27, Math.Sin(a + 0.95) * 0.27);
                    }
                    p.AddPolygon(pts);
                    Region r = new Region(p);
                    using (GraphicsPath cut = new GraphicsPath()) { Circle(cut, 0, 0, 0.11); r.Exclude(cut); }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "cat":
                {
                    p.AddEllipse(-0.68f, -0.40f, 1.36f, 1.18f);
                    Region r = new Region(p);
                    using (GraphicsPath ear = SpriteGen.Polygon(-0.66, -0.02, -0.62, -0.88, -0.10, -0.34)) r.Union(ear);
                    using (GraphicsPath ear = SpriteGen.Polygon(0.66, -0.02, 0.62, -0.88, 0.10, -0.34)) r.Union(ear);
                    using (GraphicsPath cut = new GraphicsPath(FillMode.Winding))
                    {
                        cut.AddEllipse(-0.40f, 0.00f, 0.20f, 0.28f);
                        cut.AddEllipse(0.20f, 0.00f, 0.20f, 0.28f);
                        cut.AddPolygon(new PointF[] { SpriteGen.P(-0.07, 0.34), SpriteGen.P(0.07, 0.34), SpriteGen.P(0, 0.44) });
                        r.Exclude(cut);
                    }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "ghost":
                {
                    p.AddArc(-0.60f, -0.86f, 1.20f, 1.20f, 180, 180);
                    p.AddLine(SpriteGen.P(0.60, -0.26), SpriteGen.P(0.60, 0.84));
                    p.AddBezier(SpriteGen.P(0.60, 0.84), SpriteGen.P(0.48, 0.58), SpriteGen.P(0.32, 0.58), SpriteGen.P(0.20, 0.84));
                    p.AddBezier(SpriteGen.P(0.20, 0.84), SpriteGen.P(0.08, 0.58), SpriteGen.P(-0.08, 0.58), SpriteGen.P(-0.20, 0.84));
                    p.AddBezier(SpriteGen.P(-0.20, 0.84), SpriteGen.P(-0.32, 0.58), SpriteGen.P(-0.48, 0.58), SpriteGen.P(-0.60, 0.84));
                    p.CloseFigure();
                    Region r = new Region(p);
                    using (GraphicsPath cut = new GraphicsPath(FillMode.Winding))
                    {
                        cut.AddEllipse(-0.34f, -0.42f, 0.22f, 0.32f);
                        cut.AddEllipse(0.12f, -0.42f, 0.22f, 0.32f);
                        cut.AddEllipse(-0.11f, 0.02f, 0.22f, 0.26f);
                        r.Exclude(cut);
                    }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "bat":
                {
                    double[] half = new double[] { 0, -0.16, 0.07, -0.20, 0.10, -0.46, 0.20, -0.22, 0.50, -0.40, 0.90, -0.14, 0.86, 0.10, 0.68, 0.00, 0.56, 0.28, 0.40, 0.06, 0.24, 0.36, 0.11, 0.14, 0, 0.46 };
                    List<PointF> pts = new List<PointF>();
                    for (int i = 0; i < half.Length; i += 2) pts.Add(SpriteGen.P(half[i], half[i + 1]));
                    for (int i = half.Length - 4; i >= 2; i -= 2) pts.Add(SpriteGen.P(-half[i], half[i + 1]));
                    p.AddPolygon(pts.ToArray());
                    return p;
                }
                case "bone":
                    foreach (int sx in new int[] { -1, 1 })
                        foreach (int sy in new int[] { -1, 1 })
                            Circle(p, sx * 0.62, sy * 0.13, 0.17);
                    p.AddRectangle(new RectangleF(-0.62f, -0.105f, 1.24f, 0.21f));
                    return p;
                case "holy_cross":
                    p.AddPolygon(new PointF[] { SpriteGen.P(-0.13, -0.88), SpriteGen.P(0.13, -0.88), SpriteGen.P(0.085, -0.38), SpriteGen.P(0.085, 0.60), SpriteGen.P(0.15, 0.88), SpriteGen.P(-0.15, 0.88), SpriteGen.P(-0.085, 0.60), SpriteGen.P(-0.085, -0.38) });
                    p.AddPolygon(new PointF[] { SpriteGen.P(-0.58, -0.42), SpriteGen.P(-0.10, -0.375), SpriteGen.P(0.10, -0.375), SpriteGen.P(0.58, -0.42), SpriteGen.P(0.58, -0.16), SpriteGen.P(0.10, -0.205), SpriteGen.P(-0.10, -0.205), SpriteGen.P(-0.58, -0.16) });
                    return p;
                case "zap":
                    return SpriteGen.Polygon(0.20, -0.90, -0.46, 0.08, -0.06, 0.08, -0.24, 0.90, 0.48, -0.18, 0.08, -0.18);
                case "coin":
                    SpriteGen.AddArc(p, 0.80, 0, 360, 0.11);
                    SpriteGen.AddArc(p, 0.62, 0, 360, 0.03);
                    if (g.Has("text")) { try { using (GraphicsPath gp = Glyph(g.Str("text"), g.Str("font"), true, 0.74)) p.AddPath(gp, false); } catch { } }
                    else using (GraphicsPath s = SpriteGen.Star(5, 0.19, 0.46)) p.AddPath(s, false);
                    return p;
                case "dice":
                {
                    using (GraphicsPath body = RoundRect(-0.74, -0.74, 1.48, 1.48, 0.20))
                    {
                        Region r = new Region(body);
                        using (GraphicsPath cut = new GraphicsPath(FillMode.Winding))
                        {
                            int face = Math.Max(1, Math.Min(6, (int)g.Num("face", 5)));
                            double[][] pip = new double[][] {
                                new double[] { 0, 0 },
                                new double[] { -0.36, -0.36, 0.36, 0.36 },
                                new double[] { -0.36, -0.36, 0, 0, 0.36, 0.36 },
                                new double[] { -0.36, -0.36, 0.36, -0.36, -0.36, 0.36, 0.36, 0.36 },
                                new double[] { -0.36, -0.36, 0.36, -0.36, 0, 0, -0.36, 0.36, 0.36, 0.36 },
                                new double[] { -0.36, -0.40, 0.36, -0.40, -0.36, 0, 0.36, 0, -0.36, 0.40, 0.36, 0.40 } };
                            double[] pp = pip[face - 1];
                            for (int i = 0; i < pp.Length; i += 2) Circle(cut, pp[i], pp[i + 1], 0.125);
                            r.Exclude(cut);
                        }
                        p.Dispose();
                        SpriteGen.SetRegion(r);
                        return new GraphicsPath();
                    }
                }
                case "card":
                {
                    using (GraphicsPath body = RoundRect(-0.56, -0.84, 1.12, 1.68, 0.12))
                    {
                        SpriteGen.WidenPath(body, 0.07, LineCap.Flat, LineCap.Flat);
                        p.AddPath(body, false);
                    }
                    string t = g.Str("text") ?? "♠";
                    try
                    {
                        using (GraphicsPath gp = Glyph(t, g.Str("font"), true, 0.62)) p.AddPath(gp, false);
                        GraphicsPath c1 = Glyph(t, g.Str("font"), true, 0.20);
                        Place(p, c1, -0.36, -0.62, 0, 1);
                        GraphicsPath c2 = Glyph(t, g.Str("font"), true, 0.20);
                        Place(p, c2, 0.36, 0.62, 180, 1);
                    }
                    catch { }
                    return p;
                }
                case "chain":
                    using (GraphicsPath l1 = RoundRect(-0.86, -0.26, 0.98, 0.52, 0.25)) { SpriteGen.WidenPath(l1, 0.12, LineCap.Flat, LineCap.Flat); p.AddPath(l1, false); }
                    using (GraphicsPath l2 = RoundRect(-0.12, -0.26, 0.98, 0.52, 0.25)) { SpriteGen.WidenPath(l2, 0.12, LineCap.Flat, LineCap.Flat); p.AddPath(l2, false); }
                    return p;
                case "tomoe":
                {
                    Region r = new Region();
                    r.MakeEmpty();
                    for (int k = 0; k < 3; k++)
                    {
                        GraphicsPath head = new GraphicsPath();
                        Circle(head, 0, -0.40, 0.152);
                        using (Matrix hm = new Matrix()) { hm.Rotate(120f * k); head.Transform(hm); }
                        r.Union(head);
                        head.Dispose();
                        GraphicsPath c = new GraphicsPath(FillMode.Winding);
                        int segs = 32;
                        PointF[] pts = new PointF[segs * 2];
                        for (int i = 0; i < segs; i++)
                        {
                            double t = (double)i / (segs - 1);
                            double a = (-90 - t * 168) * Math.PI / 180;
                            double w = 0.150 * Math.Pow(1 - t, 1.55);
                            double rm = 0.40 + 0.36 * Math.Pow(t, 0.72);
                            pts[i] = SpriteGen.P(Math.Cos(a) * (rm + w), Math.Sin(a) * (rm + w));
                            pts[segs * 2 - 1 - i] = SpriteGen.P(Math.Cos(a) * (rm - w), Math.Sin(a) * (rm - w));
                        }
                        c.AddPolygon(pts);
                        using (Matrix cm = new Matrix()) { cm.Rotate(120f * k); c.Transform(cm); }
                        r.Union(c);
                        c.Dispose();
                        GraphicsPath eye = new GraphicsPath();
                        Circle(eye, 0.018, -0.41, 0.058);
                        using (Matrix em2 = new Matrix()) { em2.Rotate(120f * k); eye.Transform(em2); }
                        r.Exclude(eye);
                        eye.Dispose();
                    }
                    using (GraphicsPath rings = new GraphicsPath())
                    {
                        RingAt(rings, 0, 0, 0.89, 0.022);
                        RingAt(rings, 0, 0, 0.83, 0.011);
                        RingAt(rings, 0, 0, 0.13, 0.012);
                        for (int i = 0; i < 24; i++)
                        {
                            double ta = Math.PI * 2 * i / 24;
                            double rIn = i % 2 == 0 ? 0.83 : 0.855;
                            SpriteGen.AddLine(rings, Math.Cos(ta) * rIn, Math.Sin(ta) * rIn, Math.Cos(ta) * 0.89, Math.Sin(ta) * 0.89, 0.009);
                        }
                        r.Union(rings);
                    }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "lantern":
                {
                    p.AddBezier(SpriteGen.P(-0.36, -0.78), SpriteGen.P(-0.72, -0.58), SpriteGen.P(-0.62, 0.24), SpriteGen.P(-0.34, 0.68));
                    p.AddLine(SpriteGen.P(-0.34, 0.68), SpriteGen.P(0.34, 0.68));
                    p.AddBezier(SpriteGen.P(0.34, 0.68), SpriteGen.P(0.62, 0.24), SpriteGen.P(0.72, -0.58), SpriteGen.P(0.36, -0.78));
                    p.AddBezier(SpriteGen.P(0.36, -0.78), SpriteGen.P(0.16, -0.88), SpriteGen.P(-0.16, -0.88), SpriteGen.P(-0.36, -0.78));
                    p.CloseFigure();
                    Region r = new Region(p);
                    using (GraphicsPath rim = new GraphicsPath(FillMode.Winding))
                    {
                        rim.AddRectangle(new RectangleF(-0.38f, 0.66f, 0.76f, 0.11f));
                        rim.AddPolygon(new PointF[] { SpriteGen.P(-0.08, 0.77), SpriteGen.P(0.08, 0.77), SpriteGen.P(0.04, 0.92), SpriteGen.P(-0.04, 0.92) });
                        r.Union(rim);
                    }
                    using (GraphicsPath cut = new GraphicsPath(FillMode.Winding))
                    {
                        cut.AddEllipse(-0.26f, -0.36f, 0.52f, 0.78f);
                        r.Exclude(cut);
                    }
                    using (GraphicsPath flame = new GraphicsPath(FillMode.Winding))
                    {
                        flame.AddBezier(SpriteGen.P(0, -0.22), SpriteGen.P(0.18, 0.04), SpriteGen.P(0.14, 0.30), SpriteGen.P(0, 0.34));
                        flame.AddBezier(SpriteGen.P(0, 0.34), SpriteGen.P(-0.14, 0.30), SpriteGen.P(-0.18, 0.04), SpriteGen.P(0, -0.22));
                        flame.CloseFigure();
                        r.Union(flame);
                    }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "pumpkin":
                {
                    p.AddEllipse(-0.84f, -0.54f, 0.76f, 1.24f);
                    p.AddEllipse(0.08f, -0.54f, 0.76f, 1.24f);
                    p.AddEllipse(-0.52f, -0.60f, 1.04f, 1.36f);
                    p.AddPolygon(new PointF[] { SpriteGen.P(-0.10, -0.56), SpriteGen.P(-0.04, -0.88), SpriteGen.P(0.14, -0.84), SpriteGen.P(0.10, -0.56) });
                    Region r = new Region(p);
                    using (GraphicsPath cut = new GraphicsPath(FillMode.Winding))
                    {
                        cut.AddPolygon(new PointF[] { SpriteGen.P(-0.46, -0.06), SpriteGen.P(-0.26, -0.34), SpriteGen.P(-0.12, -0.04) });
                        cut.AddPolygon(new PointF[] { SpriteGen.P(0.46, -0.06), SpriteGen.P(0.26, -0.34), SpriteGen.P(0.12, -0.04) });
                        cut.AddPolygon(new PointF[] { SpriteGen.P(-0.09, 0.12), SpriteGen.P(0, -0.04), SpriteGen.P(0.09, 0.12) });
                        cut.AddPolygon(new PointF[] {
                            SpriteGen.P(-0.52, 0.24), SpriteGen.P(-0.32, 0.34), SpriteGen.P(-0.20, 0.22), SpriteGen.P(0, 0.36),
                            SpriteGen.P(0.20, 0.22), SpriteGen.P(0.32, 0.34), SpriteGen.P(0.52, 0.24),
                            SpriteGen.P(0.36, 0.52), SpriteGen.P(0.16, 0.42), SpriteGen.P(0, 0.56), SpriteGen.P(-0.16, 0.42), SpriteGen.P(-0.36, 0.52)
                        });
                        r.Exclude(cut);
                    }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "candy":
                {
                    p.AddEllipse(-0.46f, -0.40f, 0.92f, 0.80f);
                    p.AddPolygon(new PointF[] { SpriteGen.P(-0.40, 0), SpriteGen.P(-0.88, -0.38), SpriteGen.P(-0.76, 0), SpriteGen.P(-0.88, 0.38) });
                    p.AddPolygon(new PointF[] { SpriteGen.P(0.40, 0), SpriteGen.P(0.88, -0.38), SpriteGen.P(0.76, 0), SpriteGen.P(0.88, 0.38) });
                    Region r = new Region(p);
                    using (GraphicsPath cut = new GraphicsPath(FillMode.Winding))
                    {
                        SpriteGen.AddArc(cut, 0.24, -40, 150, 0.08);
                        r.Exclude(cut);
                    }
                    p.Dispose();
                    SpriteGen.SetRegion(r);
                    return new GraphicsPath();
                }
                case "anchor":
                {
                    RingAt(p, 0, -0.68, 0.14, 0.085);
                    p.AddRectangle(new RectangleF(-0.065f, -0.56f, 0.13f, 1.32f));
                    p.AddRectangle(new RectangleF(-0.40f, -0.40f, 0.80f, 0.12f));
                    SpriteGen.AddArc(p, 0.62, 22, 136, 0.13);
                    p.AddPolygon(new PointF[] { SpriteGen.P(-0.58, 0.24), SpriteGen.P(-0.76, 0.02), SpriteGen.P(-0.38, 0.14) });
                    p.AddPolygon(new PointF[] { SpriteGen.P(0.58, 0.24), SpriteGen.P(0.76, 0.02), SpriteGen.P(0.38, 0.14) });
                    p.AddPolygon(new PointF[] { SpriteGen.P(-0.14, 0.70), SpriteGen.P(0.14, 0.70), SpriteGen.P(0, 0.90) });
                    return p;
                }
            }
            p.Dispose();
            return null;
        }

        // ---- sheets ----

        // A grid slot is a texture name the game already has a frame grid for. Embedding our own art under that name
        // is the only way to get more than one frame out of a custom texture; see references/ptfx-format.md.
        public class Slot { public string Name; public int Cols, Rows; public Slot(string n, int c, int r) { Name = n; Cols = c; Rows = r; } }

        public static readonly Slot[] Slots = new Slot[] {
            new Slot("ptfx_fishes", 2, 2), new Slot("ptfx_casino_chips", 2, 2), new Slot("ptfx_flower_petals", 2, 2), new Slot("ptfx_rubble", 2, 2), new Slot("ptfx_cig_smoke_sheet", 2, 2),
            new Slot("ptfx_muzzle_core_02", 3, 3), new Slot("ptfx_smoke_static_rgba", 3, 3),
            new Slot("ptfx_insects_rgb", 4, 4), new Slot("ptfx_multi_sheet_004_debris", 4, 4), new Slot("ptfx_multi_sheet_003_debris", 4, 4), new Slot("ptfx_multi_sheet_002_debris", 4, 4),
            new Slot("ptfx_bubbles_trail_anim", 5, 5), new Slot("ptfx_flipbook_fire_rgb", 5, 5),
            new Slot("ptfx_smoke_billow_anim_rgba", 6, 6), new Slot("ptfx_smoke_thin_anim", 6, 6),
            new Slot("ptfx_steam_anim", 7, 7), new Slot("ptfx_blood_spray", 7, 7), new Slot("ptfx_smoke_wispy_anim", 7, 7)
        };

        // Frame grids of the game's sheets, each read off the texture itself (columns, rows).
        static readonly string[] Grids = new string[] {
            "ptfx_bubbles_sheet 2 2", "ptfx_casino_chips 2 2", "ptfx_embers_rgb 2 2", "ptfx_flower_petals 2 2", "ptfx_glow_rgb 2 2", "ptfx_sparks 2 2",
            "ptfx_sparks_arcing_anim 2 2", "ptfx_water_jets 2 2", "ptfx_cig_smoke_sheet 2 2", "ptfx_fishes 2 2", "ptfx_flare 2 2", "ptfx_rubble 2 2",
            "ptfx_smoke_new_plumes 2 2", "ptfx_water_splashes_sheet 2 2", "ptfx_water_splashes_sheet_b 2 2", "ptfx_gloop 2 2", "ptfx_glass_dots_sheet 2 2",
            "ptfx_fine_debris_sheet 2 2",
            "ptfx_bullet_tracer 4 1", "ptfx_bush_twigs 4 1", "ptfx_grass_blades 4 1", "ptfx_fire_tail 4 1", "ptfx_water_dripping_rgb 4 1",
            "ptfx_blood_spurt 8 1", "ptfx_blood_squibs 8 1", "ptfx_muzzle_02 1 2",
            "ptfx_smoke_static_rgba 3 3", "ptfx_muzzle_core_02 3 3",
            "ptfx_multi_sheet_002_debris 4 4", "ptfx_multi_sheet_003_debris 4 4", "ptfx_multi_sheet_004_debris 4 4", "ptfx_muzzle_core_rgb 4 4", "ptfx_insects_rgb 4 4",
            "ptfx_flipbook_fire_rgb 5 5", "ptfx_bubbles_trail_anim 5 5", "ptfx_fire_v2 5 10",
            "ptfx_smoke_thin_anim 6 6", "ptfx_smoke_billow_anim_rgba 6 6", "ptfx_water_splash_kick 6 6",
            "ptfx_smoke_wispy_anim 7 7", "ptfx_steam_anim 7 7", "ptfx_blood_spray 7 7"
        };

        public static bool GameGrid(string name, out int cols, out int rows)
        {
            cols = rows = 1;
            foreach (string g in Grids)
            {
                string[] p = g.Split(' ');
                if (!string.Equals(p[0], name, StringComparison.OrdinalIgnoreCase)) continue;
                cols = int.Parse(p[1]); rows = int.Parse(p[2]);
                return true;
            }
            return false;
        }

        public static string GridTable()
        {
            System.Text.StringBuilder sb = new System.Text.StringBuilder();
            foreach (string g in Grids) { string[] p = g.Split(' '); sb.AppendLine(p[0].PadRight(34) + p[1] + "x" + p[2]); }
            return sb.ToString();
        }

        public static Slot FindSlot(string name)
        {
            foreach (Slot s in Slots) if (string.Equals(s.Name, name, StringComparison.OrdinalIgnoreCase)) return s;
            return null;
        }

        public static void ParseGrid(object v, out int cols, out int rows)
        {
            cols = rows = 2;
            List<object> l = v as List<object>;
            if (l != null && l.Count >= 2) { cols = (int)Json.ToDouble(l[0]); rows = (int)Json.ToDouble(l[1]); return; }
            string s = v as string;
            if (s != null)
            {
                string[] parts = s.ToLowerInvariant().Split('x');
                if (parts.Length == 2 && int.TryParse(parts[0], out cols) && int.TryParse(parts[1], out rows)) return;
                throw new InvalidDataException("sheet grid must look like \"4x4\": " + s);
            }
            if (v != null) { cols = rows = (int)Json.ToDouble(v); }
        }

        static object Lerp(object range, double t)
        {
            List<object> l = range as List<object>;
            if (l == null || l.Count < 2) return range;
            double a = Json.ToDouble(l[0]), b = Json.ToDouble(l[1]);
            return a + (b - a) * t;
        }

        // The sprite description for one frame of a sheet.
        public static JObj FrameGen(JObj sheet, int index, int count)
        {
            List<object> cells = sheet.Arr("cells");
            JObj gen;
            if (cells != null && cells.Count > 0)
            {
                object c = cells[index % cells.Count];
                JObj cj = c as JObj;
                if (cj != null) gen = cj.Clone();
                else { gen = new JObj(); gen.Add("shape", Convert.ToString(c)); }
                JObj common = sheet.Obj("sprite");
                if (common != null) foreach (KeyValuePair<string, object> kv in common.Items) if (!gen.Has(kv.Key)) gen.Set(kv.Key, kv.Value);
            }
            else
            {
                JObj fb = sheet.Obj("flipbook");
                if (fb == null) throw new InvalidDataException("a sheet needs \"cells\": [...] or \"flipbook\": { shape ... }");
                gen = fb.Clone();
                JObj an = sheet.Obj("animate");
                double t = count <= 1 ? 0 : (double)index / (count - 1);
                bool loops = sheet.Num("loop", 0) != 0;
                if (loops) t = (double)index / count;
                if (an != null)
                    foreach (KeyValuePair<string, object> kv in an.Items)
                    {
                        if (kv.Key == "seed") { gen.Set("seed", gen.Num("seed", 7) + index * 13); continue; }
                        gen.Set(kv.Key, Lerp(kv.Value, t));
                    }
                else gen.Set("phase", t);
            }
            return gen;
        }

        public static Bitmap RenderSheetTexture(JObj sheet, int cols, int rows, out int frames)
        {
            int size = (int)sheet.Num("size", cols >= 6 ? 1024 : cols >= 3 ? 512 : 256);
            if (size < 64 || size > 2048 || (size & (size - 1)) != 0) throw new InvalidDataException("sheet size must be a power of two between 64 and 2048");
            List<object> cells = sheet.Arr("cells");
            frames = cols * rows;
            int have = cells != null && cells.Count > 0 ? (sheet.Num("repeat", 1) != 0 ? frames : Math.Min(frames, cells.Count)) : (int)Math.Min(frames, sheet.Num("count", frames));
            float cw = (float)size / cols, ch = (float)size / rows;
            int cellPx = 16;
            while (cellPx < Math.Max(cw, ch)) cellPx *= 2;
            float pad = (float)sheet.Num("pad", 0.04);
            Bitmap bmp = new Bitmap(size, size, PixelFormat.Format32bppArgb);
            using (Graphics gr = Graphics.FromImage(bmp))
            {
                gr.Clear(Color.Transparent);
                gr.InterpolationMode = InterpolationMode.HighQualityBicubic;
                gr.PixelOffsetMode = PixelOffsetMode.HighQuality;
                for (int i = 0; i < have; i++)
                {
                    JObj gen = FrameGen(sheet, i, have);
                    gen.Set("size", (double)cellPx);
                    using (Bitmap cell = SpriteGen.Render(gen))
                    {
                        int cx = i % cols, cy = i / cols;
                        gr.SetClip(new RectangleF(cx * cw, cy * ch, cw, ch));
                        gr.DrawImage(cell, new RectangleF(cx * cw + cw * pad, cy * ch + ch * pad, cw * (1 - 2 * pad), ch * (1 - 2 * pad)), new RectangleF(0, 0, cellPx, cellPx), GraphicsUnit.Pixel);
                        gr.ResetClip();
                    }
                }
            }
            frames = have;
            return bmp;
        }
    }
}
