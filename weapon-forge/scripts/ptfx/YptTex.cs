using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.Runtime.InteropServices;

namespace WeaponForge
{
    public static class SpriteGen
    {
        static readonly string[] BaseShapes = new string[] {
            "glow", "disc", "ring", "sparkle", "streak", "comet", "smoke", "star", "burst", "heart", "petal", "leaf", "diamond", "hex", "triangle", "square",
            "cross", "slash", "crescent", "bolt", "rune", "snowflake", "bubble", "drop", "note", "paw", "butterfly", "flame", "spade", "club", "crown", "claw",
            "crack", "shard", "skull", "feather", "glyph"
        };
        public static readonly string[] Shapes = BuildShapeList();

        static string[] BuildShapeList()
        {
            List<string> l = new List<string>(BaseShapes);
            l.AddRange(SpriteFx.AnalyticShapes);
            l.AddRange(SpriteFx.PathShapes);
            l.Add("image");
            return l.ToArray();
        }

        [ThreadStatic] static Region pendingRegion;
        internal static void SetRegion(Region r) { pendingRegion = r; }

        internal static float Clamp(float v) { return v < 0 ? 0 : v > 1 ? 1 : v; }

        public static Color ParseColor(string s, Color def)
        {
            if (string.IsNullOrEmpty(s)) return def;
            s = s.Trim().TrimStart('#');
            if (s.Length == 3) s = "" + s[0] + s[0] + s[1] + s[1] + s[2] + s[2];
            if (s.Length != 6) throw new FormatException("colour must be #rrggbb: " + s);
            return Color.FromArgb(Convert.ToInt32(s.Substring(0, 2), 16), Convert.ToInt32(s.Substring(2, 2), 16), Convert.ToInt32(s.Substring(4, 2), 16));
        }

        internal static void Blur(float[] a, int w, int h, int r)
        {
            if (r < 1) return;
            float[] t = new float[a.Length];
            for (int pass = 0; pass < 3; pass++)
            {
                for (int y = 0; y < h; y++)
                {
                    float sum = 0;
                    int row = y * w;
                    for (int x = -r; x <= r; x++) sum += a[row + Math.Min(w - 1, Math.Max(0, x))];
                    for (int x = 0; x < w; x++)
                    {
                        t[row + x] = sum / (2 * r + 1);
                        sum += a[row + Math.Min(w - 1, x + r + 1)] - a[row + Math.Max(0, x - r)];
                    }
                }
                for (int x = 0; x < w; x++)
                {
                    float sum = 0;
                    for (int y = -r; y <= r; y++) sum += t[Math.Min(h - 1, Math.Max(0, y)) * w + x];
                    for (int y = 0; y < h; y++)
                    {
                        a[y * w + x] = sum / (2 * r + 1);
                        sum += t[Math.Min(h - 1, y + r + 1) * w + x] - t[Math.Max(0, y - r) * w + x];
                    }
                }
            }
        }

        internal static float Hash(int x, int y, int seed)
        {
            unchecked
            {
                uint h = (uint)(x * 374761393 + y * 668265263 + seed * 1274126177);
                h = (h ^ (h >> 13)) * 1274126177;
                h ^= h >> 16;
                return (h & 0xFFFFFF) / 16777215f;
            }
        }

        internal static float Noise(float x, float y, int seed)
        {
            int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y);
            float fx = x - xi, fy = y - yi;
            fx = fx * fx * (3 - 2 * fx);
            fy = fy * fy * (3 - 2 * fy);
            float a = Hash(xi, yi, seed), b = Hash(xi + 1, yi, seed), c = Hash(xi, yi + 1, seed), d = Hash(xi + 1, yi + 1, seed);
            return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
        }

        internal static float Fbm(float x, float y, int seed)
        {
            float v = 0, amp = 0.5f;
            for (int i = 0; i < 5; i++) { v += amp * Noise(x, y, seed + i * 17); x *= 2.03f; y *= 2.03f; amp *= 0.5f; }
            return v;
        }

        internal static PointF P(double x, double y) { return new PointF((float)x, (float)y); }

        internal static GraphicsPath Polygon(params double[] xy)
        {
            PointF[] p = new PointF[xy.Length / 2];
            for (int i = 0; i < p.Length; i++) p[i] = P(xy[i * 2], xy[i * 2 + 1]);
            GraphicsPath g = new GraphicsPath();
            g.AddPolygon(p);
            return g;
        }

        internal static GraphicsPath Star(int points, double inner, double outer)
        {
            PointF[] p = new PointF[points * 2];
            for (int i = 0; i < points * 2; i++)
            {
                double a = Math.PI * i / points - Math.PI / 2;
                double r = (i % 2 == 0) ? outer : inner;
                p[i] = P(Math.Cos(a) * r, Math.Sin(a) * r);
            }
            GraphicsPath g = new GraphicsPath();
            g.AddPolygon(p);
            return g;
        }

        internal static GraphicsPath Curve(bool closed, float tension, params double[] xy)
        {
            PointF[] p = new PointF[xy.Length / 2];
            for (int i = 0; i < p.Length; i++) p[i] = P(xy[i * 2], xy[i * 2 + 1]);
            GraphicsPath g = new GraphicsPath();
            if (closed) g.AddClosedCurve(p, tension); else g.AddCurve(p, tension);
            return g;
        }

        static void Stroke(GraphicsPath target, Random rnd, double x0, double y0, double x1, double y1, double width, double jag, int depth, bool taperRoot)
        {
            int segs = 18;
            PointF[] pts = new PointF[segs + 1];
            double dx = x1 - x0, dy = y1 - y0;
            double len0 = Math.Sqrt(dx * dx + dy * dy);
            if (len0 < 1e-4) return;
            double nx = -dy, ny = dx;
            double curOff = 0;
            for (int i = 0; i <= segs; i++)
            {
                double t = (double)i / segs;
                double env = Math.Sin(Math.PI * t);
                if (i == 0 || i == segs) curOff = 0;
                else curOff = curOff * 0.45 + (rnd.NextDouble() - 0.5) * jag * (0.55 + 0.75 * env);
                pts[i] = P(x0 + dx * t + nx * curOff, y0 + dy * t + ny * curOff);
            }
            PointF[] poly = new PointF[(segs + 1) * 2];
            for (int i = 0; i <= segs; i++)
            {
                double t = (double)i / segs;
                int i0 = Math.Max(0, i - 1), i1 = Math.Min(segs, i + 1);
                double tx = pts[i1].X - pts[i0].X, ty = pts[i1].Y - pts[i0].Y;
                double tl = Math.Sqrt(tx * tx + ty * ty);
                if (tl < 1e-5) { tx = dx; ty = dy; tl = len0; }
                double pxn = -ty / tl, pyn = tx / tl;
                double prof = taperRoot
                    ? Math.Pow(Math.Sin(Math.PI * Math.Min(0.998, Math.Max(0.002, t))), 0.55)
                    : Math.Pow(1.0 - t * 0.94, 0.85);
                double flicker = (i == 0 || i == segs) ? 0.25 : (0.72 + 0.45 * ((i * 7) % 3 == 0 ? 1.0 : 0.55));
                double hw = Math.Max(0.0012, width * 0.5 * prof * flicker);
                poly[i] = P(pts[i].X + pxn * hw, pts[i].Y + pyn * hw);
                poly[(segs + 1) * 2 - 1 - i] = P(pts[i].X - pxn * hw, pts[i].Y - pyn * hw);
            }
            target.AddPolygon(poly);
            if (depth <= 0) return;
            int branches = 1 + rnd.Next(3);
            for (int b = 0; b < branches; b++)
            {
                int at = 3 + rnd.Next(segs - 5);
                double side = (b % 2 == 0 ? 1 : -1) * (0.32 + rnd.NextDouble() * 0.55);
                double ang = Math.Atan2(dy, dx) + side;
                double blen = len0 * (0.22 + rnd.NextDouble() * 0.28);
                Stroke(target, rnd, pts[at].X, pts[at].Y, pts[at].X + Math.Cos(ang) * blen, pts[at].Y + Math.Sin(ang) * blen, width * 0.46, jag * 1.15, depth - 1, false);
            }
        }

        static void Stroke(GraphicsPath target, Random rnd, double x0, double y0, double x1, double y1, double width, double jag, int depth)
        {
            Stroke(target, rnd, x0, y0, x1, y1, width, jag, depth, false);
        }

        internal static void WidenPath(GraphicsPath line, double width, LineCap startCap, LineCap endCap)
        {
            using (Matrix up = new Matrix(1000f, 0, 0, 1000f, 0, 0)) line.Transform(up);
            using (Pen pen = new Pen(Color.White, (float)(Math.Max(0.002, width) * 1000)))
            {
                pen.StartCap = startCap;
                pen.EndCap = endCap;
                pen.LineJoin = LineJoin.Round;
                line.Widen(pen, null, 0.5f);
            }
            using (Matrix down = new Matrix(0.001f, 0, 0, 0.001f, 0, 0)) line.Transform(down);
        }

        internal static void AddLine(GraphicsPath g, double x0, double y0, double x1, double y1, double width)
        {
            using (GraphicsPath line = new GraphicsPath())
            {
                line.AddLine(P(x0, y0), P(x1, y1));
                WidenPath(line, width, LineCap.Round, LineCap.Round);
                g.AddPath(line, false);
            }
        }

        internal static void AddArc(GraphicsPath g, double r, double startDeg, double sweepDeg, double width)
        {
            using (GraphicsPath line = new GraphicsPath())
            {
                line.AddArc((float)-r, (float)-r, (float)(2 * r), (float)(2 * r), (float)startDeg, (float)sweepDeg);
                WidenPath(line, width, LineCap.Flat, LineCap.Flat);
                g.AddPath(line, false);
            }
        }

        static GraphicsPath ShapePath(string shape, JObj g, Random rnd)
        {
            int points = (int)g.Num("points", 5);
            double inner = g.Num("inner", 0.42);
            double thick = g.Num("thickness", 0.08);
            GraphicsPath p = new GraphicsPath(FillMode.Winding);
            switch (shape)
            {
                case "star": return Star(points, 0.86 * inner, 0.86);
                case "burst": return Star(Math.Max(8, points * 2), 0.86 * Math.Min(inner, 0.25), 0.86);
                case "diamond": return Polygon(0, -0.86, 0.52, 0, 0, 0.86, -0.52, 0);
                case "hex": return Star(3, 0.80, 0.80);
                case "triangle": return Polygon(0, -0.82, 0.74, 0.62, -0.74, 0.62);
                case "square": return Polygon(-0.66, -0.66, 0.66, -0.66, 0.66, 0.66, -0.66, 0.66);
                case "shard": return Polygon(-0.12, -0.88, 0.34, -0.20, 0.16, 0.86, -0.30, 0.18);
                case "cross":
                    p.AddRectangle(new RectangleF(-0.14f, -0.84f, 0.28f, 1.68f));
                    p.AddRectangle(new RectangleF(-0.84f, -0.14f, 1.68f, 0.28f));
                    return p;
                case "heart":
                    p.AddBezier(P(0, 0.80), P(-0.95, 0.10), P(-0.80, -0.82), P(0, -0.34));
                    p.AddBezier(P(0, -0.34), P(0.80, -0.82), P(0.95, 0.10), P(0, 0.80));
                    p.CloseFigure();
                    return p;
                case "petal":
                    p.AddBezier(P(0, -0.86), P(0.62, -0.30), P(0.46, 0.62), P(0, 0.86));
                    p.AddBezier(P(0, 0.86), P(-0.46, 0.62), P(-0.62, -0.30), P(0, -0.86));
                    p.CloseFigure();
                    return p;
                case "leaf":
                    p.AddBezier(P(0, -0.88), P(0.78, -0.40), P(0.40, 0.50), P(0, 0.88));
                    p.AddBezier(P(0, 0.88), P(-0.14, 0.30), P(-0.20, -0.40), P(0, -0.88));
                    p.CloseFigure();
                    return p;
                case "drop":
                    p.AddBezier(P(0, -0.88), P(0.18, -0.30), P(0.56, 0.10), P(0.50, 0.42));
                    p.AddBezier(P(0.50, 0.42), P(0.44, 0.96), P(-0.44, 0.96), P(-0.50, 0.42));
                    p.AddBezier(P(-0.50, 0.42), P(-0.56, 0.10), P(-0.18, -0.30), P(0, -0.88));
                    p.CloseFigure();
                    return p;
                case "flame":
                    p.AddBezier(P(0.04, -0.90), P(0.50, -0.34), P(0.70, 0.12), P(0.46, 0.56));
                    p.AddBezier(P(0.46, 0.56), P(0.26, 0.92), P(-0.30, 0.92), P(-0.48, 0.54));
                    p.AddBezier(P(-0.48, 0.54), P(-0.70, 0.08), P(-0.22, -0.10), P(-0.26, -0.48));
                    p.AddBezier(P(-0.26, -0.48), P(-0.06, -0.30), P(0.02, -0.56), P(0.04, -0.90));
                    p.CloseFigure();
                    return p;
                case "slash":
                {
                    double sweep = g.Num("sweep", 155);
                    int n = 40;
                    PointF[] pts = new PointF[n * 2];
                    double sth = g.Has("thickness") ? thick * 1.35 : 0.085;
                    for (int i = 0; i < n; i++)
                    {
                        double t = (double)i / (n - 1);
                        double a = (-90 - sweep / 2 + sweep * t) * Math.PI / 180;
                        double w = Math.Pow(Math.Sin(Math.PI * Math.Pow(t, 0.78)), 1.35) * sth;
                        pts[i] = P(Math.Cos(a) * 0.85, Math.Sin(a) * 0.85 + 0.24);
                        pts[n * 2 - 1 - i] = P(Math.Cos(a) * (0.85 - w), Math.Sin(a) * (0.85 - w) + 0.24);
                    }
                    p.AddPolygon(pts);
                    for (int k = 0; k < 2; k++)
                    {
                        double rSub = 0.81 - k * 0.045;
                        double swSub = sweep * (0.68 - k * 0.14);
                        using (GraphicsPath trail = new GraphicsPath())
                        {
                            trail.AddArc((float)-rSub, (float)(-rSub + 0.24), (float)(2 * rSub), (float)(2 * rSub), (float)(-90 - swSub * 0.45 + k * 8), (float)swSub);
                            WidenPath(trail, 0.008 + (1 - k) * 0.005, LineCap.Triangle, LineCap.Triangle);
                            p.AddPath(trail, false);
                        }
                    }
                    return p;
                }
                case "crescent":
                {
                    GraphicsPath outer = new GraphicsPath();
                    outer.AddEllipse(-0.80f, -0.80f, 1.60f, 1.60f);
                    Region r = new Region(outer);
                    GraphicsPath cut = new GraphicsPath();
                    cut.AddEllipse(-0.42f, -0.84f, 1.50f, 1.50f);
                    r.Exclude(cut);
                    p.Dispose();
                    outer.Dispose();
                    cut.Dispose();
                    GraphicsPath res = new GraphicsPath();
                    pendingRegion = r;
                    return res;
                }
                case "bolt":
                {
                    double bth = g.Has("thickness") ? thick * 0.42 : 0.026;
                    double jag = g.Num("jag", 0.20);
                    double sx0 = -0.08 + rnd.NextDouble() * 0.16, sx1 = -0.08 + rnd.NextDouble() * 0.16;
                    Stroke(p, rnd, sx0, -0.88, sx1, 0.88, bth, jag, (int)g.Num("branches", 3), true);
                    Stroke(p, rnd, sx0 + 0.03, -0.76, sx1 - 0.03, 0.78, bth * 0.42, jag * 1.35, 1, true);
                    return p;
                }
                case "crack":
                {
                    int rays = 7;
                    double cth = g.Has("thickness") ? thick * 0.34 : 0.024;
                    double[] angles = new double[rays];
                    double[] lengths = new double[rays];
                    for (int i = 0; i < rays; i++)
                    {
                        angles[i] = Math.PI * 2 * i / rays + (rnd.NextDouble() - 0.5) * 0.45;
                        lengths[i] = 0.52 + rnd.NextDouble() * 0.36;
                        Stroke(p, rnd, 0, 0, Math.Cos(angles[i]) * lengths[i], Math.Sin(angles[i]) * lengths[i], cth, 0.16, 2, false);
                    }
                    for (int i = 0; i < rays; i++)
                    {
                        if (rnd.NextDouble() < 0.35) continue;
                        int j = (i + 1) % rays;
                        double r1 = (0.22 + rnd.NextDouble() * 0.34) * Math.Min(lengths[i], lengths[j]);
                        double r2 = r1 * (0.85 + rnd.NextDouble() * 0.30);
                        Stroke(p, rnd, Math.Cos(angles[i]) * r1, Math.Sin(angles[i]) * r1, Math.Cos(angles[j]) * r2, Math.Sin(angles[j]) * r2, cth * 0.36, 0.12, 0, true);
                    }
                    return p;
                }
                case "claw":
                {
                    double cth = g.Has("thickness") ? thick * 0.72 : 0.052;
                    for (int i = -1; i <= 1; i++)
                    {
                        int n = 30;
                        PointF[] blade = new PointF[n * 2];
                        double reach = i == 0 ? 0.90 : 0.78;
                        double xShift = i * 0.31;
                        for (int k = 0; k < n; k++)
                        {
                            double t = (double)k / (n - 1);
                            double y = -reach + 2 * reach * t;
                            double bend = -0.16 * Math.Sin(Math.PI * t) + 0.12 * t;
                            double cx = xShift + bend;
                            double prof = Math.Pow(Math.Sin(Math.PI * t), 1.25);
                            double jag = (k > 3 && k < n - 4 && k % 4 == 0) ? 1.28 : 1.0;
                            double hw = Math.Max(0.001, cth * prof * jag);
                            blade[k] = P(cx + hw * 0.75, y);
                            blade[n * 2 - 1 - k] = P(cx - hw * 1.05, y + hw * 0.18);
                        }
                        p.AddPolygon(blade);
                        Stroke(p, rnd, xShift - 0.08 + i * 0.02, -reach * 0.72, xShift + 0.06 + i * 0.02, reach * 0.76, cth * 0.24, 0.05, 0, true);
                    }
                    return p;
                }
                case "snowflake":
                    for (int i = 0; i < 6; i++)
                    {
                        double a = Math.PI * i / 3;
                        double cx = Math.Cos(a), cy = Math.Sin(a);
                        AddLine(p, 0, 0, cx * 0.86, cy * 0.86, thick * 0.5);
                        foreach (double d in new double[] { 0.42, 0.64 })
                            foreach (double s in new double[] { 1, -1 })
                            {
                                double b = a + s * Math.PI / 3.4;
                                AddLine(p, cx * d, cy * d, cx * d + Math.Cos(b) * 0.20, cy * d + Math.Sin(b) * 0.20, thick * 0.38);
                            }
                    }
                    return p;
                case "rune":
                {
                    double rth = g.Has("thickness") ? thick : 0.055;
                    AddArc(p, 0.86, 0, 360, rth * 0.32);
                    for (int s = 0; s < 4; s++) AddArc(p, 0.90, s * 90 + 10, 52, rth * 0.16);
                    AddArc(p, 0.70, 0, 360, rth * 0.18);
                    AddArc(p, 0.34, 0, 360, rth * 0.22);
                    int sides = Math.Max(3, points);
                    for (int k = 0; k < 2; k++)
                        for (int i = 0; i < sides; i++)
                        {
                            double a0 = Math.PI * 2 * i / sides + k * Math.PI / sides - Math.PI / 2;
                            double a1 = Math.PI * 2 * ((i + (sides > 4 ? 2 : 1)) % sides) / sides + k * Math.PI / sides - Math.PI / 2;
                            AddLine(p, Math.Cos(a0) * 0.70, Math.Sin(a0) * 0.70, Math.Cos(a1) * 0.70, Math.Sin(a1) * 0.70, rth * 0.18);
                            if (sides > 4) break;
                        }
                    if (sides > 4)
                        for (int i = 0; i < sides; i++)
                        {
                            double a0 = Math.PI * 2 * i / sides - Math.PI / 2, a1 = Math.PI * 2 * ((i + 2) % sides) / sides - Math.PI / 2;
                            AddLine(p, Math.Cos(a0) * 0.70, Math.Sin(a0) * 0.70, Math.Cos(a1) * 0.70, Math.Sin(a1) * 0.70, rth * 0.18);
                        }
                    int ticks = 36;
                    for (int i = 0; i < ticks; i++)
                    {
                        double a = Math.PI * 2 * i / ticks;
                        double len = i % 3 == 0 ? 0.095 : 0.042;
                        AddLine(p, Math.Cos(a) * 0.74, Math.Sin(a) * 0.74, Math.Cos(a) * (0.74 + len), Math.Sin(a) * (0.74 + len), rth * 0.15);
                    }
                    return p;
                }
                case "bubble":
                    AddArc(p, 0.78, 0, 360, thick * 0.9);
                    AddArc(p, 0.52, 205, 50, thick * 1.1);
                    return p;
                case "note":
                    p.AddEllipse(-0.52f, 0.28f, 0.56f, 0.44f);
                    p.AddRectangle(new RectangleF(-0.04f, -0.80f, 0.12f, 1.30f));
                    p.AddBezier(P(0.08, -0.80), P(0.50, -0.70), P(0.62, -0.30), P(0.40, 0.00));
                    p.AddBezier(P(0.40, 0.00), P(0.44, -0.30), P(0.30, -0.48), P(0.08, -0.52));
                    p.CloseFigure();
                    return p;
                case "paw":
                    p.AddEllipse(-0.42f, 0.02f, 0.84f, 0.74f);
                    p.AddEllipse(-0.80f, -0.34f, 0.36f, 0.46f);
                    p.AddEllipse(-0.40f, -0.80f, 0.36f, 0.50f);
                    p.AddEllipse(0.04f, -0.80f, 0.36f, 0.50f);
                    p.AddEllipse(0.44f, -0.34f, 0.36f, 0.46f);
                    return p;
                case "butterfly":
                    foreach (int s in new int[] { 1, -1 })
                    {
                        p.AddClosedCurve(new PointF[] { P(0.04 * s, -0.10), P(0.50 * s, -0.78), P(0.90 * s, -0.50), P(0.60 * s, 0.02) }, 0.6f);
                        p.AddClosedCurve(new PointF[] { P(0.04 * s, 0.04), P(0.62 * s, 0.16), P(0.56 * s, 0.70), P(0.18 * s, 0.62) }, 0.6f);
                    }
                    p.AddEllipse(-0.06f, -0.40f, 0.12f, 0.90f);
                    return p;
                case "spade":
                    p.AddBezier(P(0, -0.86), P(0.90, -0.10), P(0.86, 0.60), P(0.10, 0.36));
                    p.AddBezier(P(0.10, 0.36), P(0.16, 0.66), P(0.30, 0.80), P(0.34, 0.86));
                    p.AddLine(P(0.34, 0.86), P(-0.34, 0.86));
                    p.AddBezier(P(-0.34, 0.86), P(-0.30, 0.80), P(-0.16, 0.66), P(-0.10, 0.36));
                    p.AddBezier(P(-0.10, 0.36), P(-0.86, 0.60), P(-0.90, -0.10), P(0, -0.86));
                    p.CloseFigure();
                    return p;
                case "club":
                    p.AddEllipse(-0.30f, -0.86f, 0.60f, 0.60f);
                    p.AddEllipse(-0.80f, -0.30f, 0.60f, 0.60f);
                    p.AddEllipse(0.20f, -0.30f, 0.60f, 0.60f);
                    p.AddPolygon(new PointF[] { P(-0.08, -0.20), P(0.08, -0.20), P(0.30, 0.86), P(-0.30, 0.86) });
                    return p;
                case "crown":
                    return Polygon(-0.80, 0.60, -0.84, -0.50, -0.42, 0.02, 0, -0.80, 0.42, 0.02, 0.84, -0.50, 0.80, 0.60);
                case "skull":
                {
                    GraphicsPath head = new GraphicsPath();
                    head.AddEllipse(-0.66f, -0.84f, 1.32f, 1.24f);
                    head.AddRectangle(new RectangleF(-0.36f, 0.20f, 0.72f, 0.54f));
                    Region r = new Region(head);
                    GraphicsPath cut = new GraphicsPath();
                    cut.AddEllipse(-0.46f, -0.36f, 0.34f, 0.38f);
                    cut.AddEllipse(0.12f, -0.36f, 0.34f, 0.38f);
                    cut.AddPolygon(new PointF[] { P(0, 0.06), P(0.10, 0.28), P(-0.10, 0.28) });
                    cut.AddRectangle(new RectangleF(-0.19f, 0.44f, 0.05f, 0.32f));
                    cut.AddRectangle(new RectangleF(-0.02f, 0.44f, 0.05f, 0.32f));
                    cut.AddRectangle(new RectangleF(0.15f, 0.44f, 0.05f, 0.32f));
                    r.Exclude(cut);
                    head.Dispose();
                    cut.Dispose();
                    p.Dispose();
                    GraphicsPath res = new GraphicsPath();
                    pendingRegion = r;
                    return res;
                }
                case "feather":
                    p.AddBezier(P(0.06, -0.90), P(0.58, -0.40), P(0.44, 0.40), P(0.02, 0.62));
                    p.AddBezier(P(0.02, 0.62), P(-0.44, 0.40), P(-0.50, -0.40), P(0.06, -0.90));
                    p.CloseFigure();
                    p.AddRectangle(new RectangleF(-0.02f, 0.56f, 0.05f, 0.34f));
                    return p;
                case "glyph":
                {
                    string text = g.Str("text") ?? "*";
                    using (FontFamily ff = new FontFamily(g.Str("font") ?? "Segoe UI Symbol"))
                    using (StringFormat sf = new StringFormat(StringFormat.GenericTypographic))
                    {
                        p.AddString(text, ff, (int)(g.Num("bold", 1) != 0 ? FontStyle.Bold : FontStyle.Regular), 1.0f, new PointF(0, 0), sf);
                    }
                    RectangleF b = p.GetBounds();
                    if (b.Width > 0 && b.Height > 0)
                    {
                        float s = 1.64f / Math.Max(b.Width, b.Height);
                        using (Matrix m = new Matrix())
                        {
                            m.Translate(-(b.Left + b.Width / 2) * s, -(b.Top + b.Height / 2) * s);
                            m.Scale(s, s);
                            p.Transform(m);
                        }
                    }
                    return p;
                }
            }
            p.Dispose();
            return SpriteFx.Path(shape, g, rnd);
        }

        static float[] PathMask(string shape, JObj g, int n, Random rnd)
        {
            int ss = n <= 256 ? 3 : 2;
            int big = n * ss;
            float[] mask = new float[n * n];
            using (Bitmap bmp = new Bitmap(big, big, PixelFormat.Format32bppArgb))
            {
                using (Graphics gr = Graphics.FromImage(bmp))
                {
                    gr.SmoothingMode = SmoothingMode.AntiAlias;
                    gr.PixelOffsetMode = PixelOffsetMode.HighQuality;
                    gr.TextRenderingHint = TextRenderingHint.AntiAlias;
                    gr.Clear(Color.Transparent);
                    float fit = (float)g.Num("fit", 0.92);
                    gr.TranslateTransform(big / 2f, big / 2f);
                    gr.RotateTransform((float)g.Num("rotation", 0));
                    gr.ScaleTransform(big / 2f * fit * (float)g.Num("aspect", 1), big / 2f * fit);
                    pendingRegion = null;
                    using (GraphicsPath path = ShapePath(shape, g, rnd))
                    {
                        if (path == null) throw new InvalidDataException("unknown sprite shape '" + shape + "'. Known: " + string.Join(", ", Shapes));
                        using (Brush br = new SolidBrush(Color.White))
                        {
                            Region r = pendingRegion;
                            pendingRegion = null;
                            if (r != null) { gr.FillRegion(br, r); r.Dispose(); }
                            else gr.FillPath(br, path);
                        }
                    }
                }
                BitmapData bd = bmp.LockBits(new Rectangle(0, 0, big, big), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                byte[] raw = new byte[bd.Stride * big];
                Marshal.Copy(bd.Scan0, raw, 0, raw.Length);
                bmp.UnlockBits(bd);
                for (int y = 0; y < n; y++)
                    for (int x = 0; x < n; x++)
                    {
                        int sum = 0;
                        for (int sy = 0; sy < ss; sy++)
                            for (int sx = 0; sx < ss; sx++)
                                sum += raw[(y * ss + sy) * bd.Stride + (x * ss + sx) * 4 + 3];
                        mask[y * n + x] = sum / (255f * ss * ss);
                    }
            }
            return mask;
        }

        static float[] AnalyticMask(string shape, JObj g, int n, Random rnd, int seed)
        {
            float[] m = new float[n * n];
            float soft = (float)g.Num("softness", 2.2);
            float r0 = (float)g.Num("radius", 0.70);
            float th = (float)g.Num("thickness", 0.08);
            double rotRad = g.Num("rotation", 0) * Math.PI / 180;
            float rc = (float)Math.Cos(rotRad), rs = (float)Math.Sin(rotRad), asp = (float)Math.Max(0.05, g.Num("aspect", 1));
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float u0 = (x + 0.5f) / n * 2 - 1, v0 = (y + 0.5f) / n * 2 - 1;
                    float u = (u0 * rc + v0 * rs) / asp, v = -u0 * rs + v0 * rc;
                    float r = (float)Math.Sqrt(u * u + v * v);
                    float val = 0;
                    switch (shape)
                    {
                        case "glow":
                        {
                            float core = (float)Math.Exp(-r * r * 16.5f) * 0.72f;
                            float mid2 = (float)Math.Exp(-r * r * 4.6f) * 0.34f;
                            float veil = (float)Math.Pow(Clamp(1 - r / 0.92f), soft + 0.8f) * 0.16f;
                            float wisp = 0.90f + 0.20f * Fbm(u * 2.8f + 3.1f, v * 2.8f + 7.4f, seed);
                            val = (core + (mid2 + veil) * wisp) * Clamp((0.94f - r) * 6f);
                            break;
                        }
                        case "disc": val = Clamp((0.86f - r) / Math.Max(0.01f, (float)g.Num("edge", 0.10))); break;
                        case "ring":
                        {
                            float rth = g.Has("thickness") ? th : 0.038f;
                            float d = r - r0;
                            float prof = d > 0 ? (float)Math.Exp(-(d * d) / (rth * rth * 0.35f)) : (float)Math.Exp(-(d * d) / (rth * rth * 2.4f));
                            float nz = 0.70f + 0.58f * Fbm(u * 3.6f + 5, v * 3.6f - 2, seed);
                            val = prof * nz * Clamp((0.97f - r) * 10);
                            break;
                        }
                        case "sparkle":
                        {
                            float scaleTh = (float)(g.Has("pinch") ? g.Num("pinch", 0.42) / 0.42 : 1.0) * (th / 0.08f);
                            float wu = 0.0065f + 0.038f * (float)Math.Pow(Clamp(1 - Math.Abs(u)), 2.3) * scaleTh;
                            float wv = 0.0065f + 0.038f * (float)Math.Pow(Clamp(1 - Math.Abs(v)), 2.3) * scaleTh;
                            float spH = (float)(Math.Exp(-Math.Abs(v) / wu) * Math.Pow(Clamp(1 - Math.Abs(u) * 1.05f), 1.45));
                            float spV = (float)(Math.Exp(-Math.Abs(u) / wv) * Math.Pow(Clamp(1 - Math.Abs(v) * 1.05f), 1.45));
                            float du = (u + v) * 0.7071068f, dv = (v - u) * 0.7071068f;
                            float wd1 = 0.0055f + 0.022f * (float)Math.Pow(Clamp(1 - Math.Abs(du) * 1.85f), 2.1) * scaleTh;
                            float wd2 = 0.0055f + 0.022f * (float)Math.Pow(Clamp(1 - Math.Abs(dv) * 1.85f), 2.1) * scaleTh;
                            float spD1 = (float)(Math.Exp(-Math.Abs(dv) / wd1) * Math.Pow(Clamp(1 - Math.Abs(du) * 1.85f), 1.65)) * 0.52f;
                            float spD2 = (float)(Math.Exp(-Math.Abs(du) / wd2) * Math.Pow(Clamp(1 - Math.Abs(dv) * 1.85f), 1.65)) * 0.52f;
                            float core = (float)Math.Exp(-r * r * 38f) + (float)Math.Exp(-r * r * 8.5f) * 0.20f;
                            val = Math.Max(Math.Max(spH, spV), Math.Max(spD1, spD2)) + core * 0.85f;
                            break;
                        }
                        case "streak":
                        {
                            float sth = Math.Max(0.015f, g.Has("thickness") ? th : 0.052f);
                            float sx = u / 0.90f, sy = v / sth;
                            float lenEnv = (float)Math.Pow(Clamp(1 - sx * sx), 1.75);
                            float fil = (float)Math.Exp(-sy * sy * 2.4f) + (float)Math.Exp(-sy * sy * 0.45f) * 0.30f;
                            float flick = 0.82f + 0.32f * Noise(u * 9f + 4, v * 16f, seed);
                            val = fil * lenEnv * flick * Clamp((1 - Math.Abs(u)) * 8);
                            break;
                        }
                        case "comet":
                        {
                            float cth = Math.Max(0.015f, g.Has("thickness") ? th : 0.06f);
                            float t = (u + 1) / 2;
                            float warpY = (Fbm(u * 3.5f + 2, v * 3.5f, seed) - 0.48f) * 0.14f * Clamp(1 - t);
                            float w = cth * (0.10f + 1.25f * t * t);
                            float sy = (v + warpY) / Math.Max(0.008f, w);
                            float head = (float)Math.Exp(-((u - 0.62f) * (u - 0.62f) + v * v) / (cth * cth * 1.6f));
                            float wake = (float)Math.Exp(-sy * sy * 1.5f) * (float)Math.Pow(t, 1.7) * Clamp((0.76f - u) * 9) * (0.65f + 0.65f * Fbm(u * 6f, v * 12f, seed + 5));
                            val = wake * 0.82f + head;
                            break;
                        }
                        case "smoke":
                        {
                            float w1 = Fbm(u * 2.2f + 11, v * 2.2f + 7, seed) - 0.48f;
                            float w2 = Fbm(u * 2.2f - 5, v * 2.2f + 13, seed + 17) - 0.48f;
                            float wu2 = u + w1 * 0.42f, wv2 = v + w2 * 0.42f;
                            float rw = (float)Math.Sqrt(wu2 * wu2 + wv2 * wv2);
                            float nz = Fbm(wu2 * 3.8f + 3, wv2 * 3.8f + 19, seed + 43);
                            float fine = Fbm(wu2 * 8.2f - 7, wv2 * 8.2f + 5, seed + 91);
                            float edge = Clamp(1 - rw * (1.06f + (nz - 0.5f) * 0.75f));
                            val = (float)Math.Pow(edge, 1.45) * Clamp(0.32f + nz * 0.68f + fine * 0.32f) * Clamp((0.96f - r) * 6);
                            break;
                        }
                    }
                    m[y * n + x] = Clamp(val);
                }
            return m;
        }

        public static Bitmap Render(JObj g)
        {
            string shape = g.Str("shape") ?? "glow";
            int n = (int)g.Num("size", 256);
            if (n < 16 || n > 2048 || (n & (n - 1)) != 0) throw new InvalidDataException("sprite size must be a power of two between 16 and 2048");
            int seed = (int)g.Num("seed", 7);
            Random rnd = new Random(seed);
            if (shape == "image")
            {
                using (Bitmap src = new Bitmap(g.Str("file")))
                {
                    bool srcPotW = src.Width >= 16 && src.Width <= 2048 && (src.Width & (src.Width - 1)) == 0;
                    bool srcPotH = src.Height >= 16 && src.Height <= 2048 && (src.Height & (src.Height - 1)) == 0;
                    int outW = g.Has("width") ? (int)g.Num("width", n) : (!g.Has("size") && srcPotW && srcPotH ? src.Width : n);
                    int outH = g.Has("height") ? (int)g.Num("height", n) : (!g.Has("size") && srcPotW && srcPotH ? src.Height : n);
                    if (outW < 16 || outW > 2048 || (outW & (outW - 1)) != 0 || outH < 16 || outH > 2048 || (outH & (outH - 1)) != 0)
                        throw new InvalidDataException("image width/height must be powers of two between 16 and 2048");
                    if (outW == src.Width && outH == src.Height)
                    {
                        Bitmap exact = new Bitmap(outW, outH, PixelFormat.Format32bppArgb);
                        using (Graphics gr = Graphics.FromImage(exact))
                        {
                            gr.CompositingMode = CompositingMode.SourceCopy;
                            gr.InterpolationMode = InterpolationMode.NearestNeighbor;
                            gr.DrawImage(src, new Rectangle(0, 0, outW, outH), 0, 0, src.Width, src.Height, GraphicsUnit.Pixel);
                        }
                        return exact;
                    }
                    Bitmap dst = new Bitmap(outW, outH, PixelFormat.Format32bppArgb);
                    using (Graphics gr = Graphics.FromImage(dst))
                    using (ImageAttributes ia = new ImageAttributes())
                    {
                        ia.SetWrapMode(WrapMode.TileFlipXY);
                        gr.InterpolationMode = InterpolationMode.HighQualityBicubic;
                        gr.PixelOffsetMode = PixelOffsetMode.HighQuality;
                        gr.Clear(Color.Transparent);
                        if (g.Has("width") || g.Has("height"))
                        {
                            gr.DrawImage(src, new Rectangle(0, 0, outW, outH), 0, 0, src.Width, src.Height, GraphicsUnit.Pixel, ia);
                        }
                        else
                        {
                            float s = Math.Min((float)outW / src.Width, (float)outH / src.Height);
                            int dw = Math.Max(1, (int)Math.Round(src.Width * s)), dh = Math.Max(1, (int)Math.Round(src.Height * s));
                            gr.DrawImage(src, new Rectangle((outW - dw) / 2, (outH - dh) / 2, dw, dh), 0, 0, src.Width, src.Height, GraphicsUnit.Pixel, ia);
                        }
                    }
                    return dst;
                }
            }
            bool baseAnalytic = shape == "glow" || shape == "disc" || shape == "ring" || shape == "sparkle" || shape == "streak" || shape == "comet" || shape == "smoke";
            bool fxAnalytic = SpriteFx.IsAnalytic(shape);
            bool analytic = baseAnalytic || fxAnalytic;
            float[] mask = baseAnalytic ? AnalyticMask(shape, g, n, rnd, seed) : fxAnalytic ? SpriteFx.Analytic(shape, g, n, seed) : PathMask(shape, g, n, rnd);
            mask = SpriteFx.Modify(mask, n, g, seed);
            double defGlow = analytic ? 0 : (shape == "bolt" || shape == "crack" || shape == "rune" || shape == "magic_circle" || shape == "slash" || shape == "claw" || shape == "snowflake" || shape == "tomoe" ? 0.024 : 0.015);
            float glowR = (float)g.Num("glow", defGlow);
            float glowS = (float)g.Num("glowStrength", 0.55);
            float[] haloInner = null, haloOuter = null;
            if (glowR > 0)
            {
                haloInner = (float[])mask.Clone();
                Blur(haloInner, n, n, Math.Max(1, (int)(glowR * 0.45f * n)));
                haloOuter = (float[])mask.Clone();
                Blur(haloOuter, n, n, Math.Max(2, (int)(glowR * 1.55f * n)));
            }
            float[] coreMask = (float[])mask.Clone();
            if (!analytic) Blur(coreMask, n, n, Math.Max(1, n / 88));
            bool flatFill = analytic || g.Num("flat", 0) != 0 || g.Num("toon", 0) > 0;
            Color outer = ParseColor(g.Str("color"), Color.White);
            Color inner = ParseColor(g.Str("core"), g.Has("color") ? Color.White : outer);
            bool hasMid = g.Has("mid");
            Color mid = ParseColor(g.Str("mid"), outer);
            float corePow = (float)g.Num("corePower", 1.5);
            float edgeFade = (float)g.Num("edgeFade", shape == "ribbon_line" ? 0.0 : 0.06);
            bool hollow = g.Num("hollow", 0) != 0;
            byte[] px = new byte[n * n * 4];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    int i = y * n + x;
                    float m = mask[i];
                    float u = (x + 0.5f) / n * 2 - 1, v = (y + 0.5f) / n * 2 - 1;
                    if (hollow) m = Clamp(m * 4 * (1 - coreMask[i])) * m;
                    else if (!flatFill && m > 0.01f)
                    {
                        float brush = 0.76f + 0.34f * Fbm(u * 5.5f + 2.3f, v * 5.5f - 1.7f, seed + 71);
                        float rim = Clamp(m - coreMask[i] * 0.52f) * 0.55f;
                        m = Clamp(m * brush + rim);
                    }
                    float bloom = haloInner == null ? 0 : (haloInner[i] * 0.62f + haloOuter[i] * 0.28f) * glowS;
                    float a = Clamp(m + bloom * (1 - m * 0.85f));
                    float border = Math.Max(Math.Abs(u), Math.Abs(v));
                    if (edgeFade > 0) a *= Clamp((1 - border) / edgeFade);
                    float hot = analytic ? m : Clamp(coreMask[i] * 0.72f + m * 0.38f);
                    float t = (float)Math.Pow(hot, corePow);
                    if (hasMid)
                    {
                        Color c0 = t < 0.5f ? outer : mid, c1 = t < 0.5f ? mid : inner;
                        float tt = t < 0.5f ? t * 2 : (t - 0.5f) * 2;
                        px[i * 4 + 0] = (byte)(c0.B + (c1.B - c0.B) * tt);
                        px[i * 4 + 1] = (byte)(c0.G + (c1.G - c0.G) * tt);
                        px[i * 4 + 2] = (byte)(c0.R + (c1.R - c0.R) * tt);
                        px[i * 4 + 3] = (byte)(a * 255f + 0.5f);
                        continue;
                    }
                    px[i * 4 + 0] = (byte)(outer.B + (inner.B - outer.B) * t);
                    px[i * 4 + 1] = (byte)(outer.G + (inner.G - outer.G) * t);
                    px[i * 4 + 2] = (byte)(outer.R + (inner.R - outer.R) * t);
                    px[i * 4 + 3] = (byte)(a * 255f + 0.5f);
                }
            Bitmap bmp = new Bitmap(n, n, PixelFormat.Format32bppArgb);
            BitmapData bd = bmp.LockBits(new Rectangle(0, 0, n, n), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            for (int y = 0; y < n; y++) Marshal.Copy(px, y * n * 4, new IntPtr(bd.Scan0.ToInt64() + (long)y * bd.Stride), n * 4);
            bmp.UnlockBits(bd);
            return bmp;
        }

        public static byte[] Pixels(Bitmap bmp)
        {
            int w = bmp.Width, h = bmp.Height;
            BitmapData bd = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            byte[] px = new byte[w * h * 4];
            for (int y = 0; y < h; y++) Marshal.Copy(new IntPtr(bd.Scan0.ToInt64() + (long)y * bd.Stride), px, y * w * 4, w * 4);
            bmp.UnlockBits(bd);
            return px;
        }

        static byte[] Halve(byte[] px, int w, int h, out int nw, out int nh)
        {
            nw = Math.Max(1, w / 2);
            nh = Math.Max(1, h / 2);
            byte[] o = new byte[nw * nh * 4];
            for (int y = 0; y < nh; y++)
                for (int x = 0; x < nw; x++)
                {
                    int x0 = Math.Min(w - 1, x * 2), x1 = Math.Min(w - 1, x * 2 + 1), y0 = Math.Min(h - 1, y * 2), y1 = Math.Min(h - 1, y * 2 + 1);
                    int[] idx = new int[] { (y0 * w + x0) * 4, (y0 * w + x1) * 4, (y1 * w + x0) * 4, (y1 * w + x1) * 4 };
                    int asum = 0;
                    int[] c = new int[3];
                    foreach (int i in idx)
                    {
                        int a = px[i + 3];
                        asum += a;
                        c[0] += px[i] * a; c[1] += px[i + 1] * a; c[2] += px[i + 2] * a;
                    }
                    int d = (y * nw + x) * 4;
                    if (asum == 0) { o[d] = px[idx[0]]; o[d + 1] = px[idx[0] + 1]; o[d + 2] = px[idx[0] + 2]; o[d + 3] = 0; }
                    else { o[d] = (byte)(c[0] / asum); o[d + 1] = (byte)(c[1] / asum); o[d + 2] = (byte)(c[2] / asum); o[d + 3] = (byte)((asum + 2) / 4); }
                }
            return o;
        }

        static ushort To565(int r, int g, int b) { return (ushort)(((r * 31 + 127) / 255 << 11) | ((g * 63 + 127) / 255 << 5) | ((b * 31 + 127) / 255)); }

        static void Dxt5(byte[] px, int w, int h, MemoryStream ms)
        {
            byte[] block = new byte[16];
            int[] bi = new int[16];
            for (int by = 0; by < Math.Max(1, (h + 3) / 4); by++)
                for (int bx = 0; bx < Math.Max(1, (w + 3) / 4); bx++)
                {
                    int amin = 255, amax = 0;
                    int rmin = 255, gmin = 255, bmin = 255, rmax = 0, gmax = 0, bmax = 0;
                    bool any = false;
                    for (int k = 0; k < 16; k++)
                    {
                        int x = Math.Min(w - 1, bx * 4 + (k & 3)), y = Math.Min(h - 1, by * 4 + (k >> 2));
                        int i = (y * w + x) * 4;
                        bi[k] = i;
                        int a = px[i + 3];
                        if (a < amin) amin = a;
                        if (a > amax) amax = a;
                        if (a == 0) continue;
                        any = true;
                        if (px[i] < bmin) bmin = px[i]; if (px[i] > bmax) bmax = px[i];
                        if (px[i + 1] < gmin) gmin = px[i + 1]; if (px[i + 1] > gmax) gmax = px[i + 1];
                        if (px[i + 2] < rmin) rmin = px[i + 2]; if (px[i + 2] > rmax) rmax = px[i + 2];
                    }
                    if (!any) { rmin = rmax = px[bi[0] + 2]; gmin = gmax = px[bi[0] + 1]; bmin = bmax = px[bi[0]]; }
                    block[0] = (byte)amax;
                    block[1] = (byte)amin;
                    ulong abits = 0;
                    for (int k = 0; k < 16; k++)
                    {
                        int a = px[bi[k] + 3];
                        int code;
                        if (amax == amin) code = 0;
                        else
                        {
                            int t = ((amax - a) * 7 + (amax - amin) / 2) / (amax - amin);
                            code = t == 0 ? 0 : t == 7 ? 1 : t + 1;
                        }
                        abits |= (ulong)code << (3 * k);
                    }
                    for (int k = 0; k < 6; k++) block[2 + k] = (byte)(abits >> (8 * k));
                    ushort c0 = To565(rmax, gmax, bmax), c1 = To565(rmin, gmin, bmin);
                    uint cbits = 0;
                    if (c0 == c1)
                    {
                        if (c0 == 0) { c0 = 1; cbits = 0x55555555; }
                        else { c1 = (ushort)(c0 - 1); }
                    }
                    else
                    {
                        if (c0 < c1) { ushort t = c0; c0 = c1; c1 = t; int q = rmax; rmax = rmin; rmin = q; q = gmax; gmax = gmin; gmin = q; q = bmax; bmax = bmin; bmin = q; }
                        int dr = rmax - rmin, dg = gmax - gmin, db = bmax - bmin;
                        int len = dr * dr + dg * dg + db * db;
                        for (int k = 0; k < 16; k++)
                        {
                            int i = bi[k];
                            int dot = (px[i + 2] - rmin) * dr + (px[i + 1] - gmin) * dg + (px[i] - bmin) * db;
                            int t = len == 0 ? 0 : (dot * 3 + len / 2) / len;
                            if (t < 0) t = 0; if (t > 3) t = 3;
                            uint code = t == 3 ? 0u : t == 0 ? 1u : t == 2 ? 2u : 3u;
                            cbits |= code << (2 * k);
                        }
                    }
                    block[8] = (byte)c0; block[9] = (byte)(c0 >> 8); block[10] = (byte)c1; block[11] = (byte)(c1 >> 8);
                    block[12] = (byte)cbits; block[13] = (byte)(cbits >> 8); block[14] = (byte)(cbits >> 16); block[15] = (byte)(cbits >> 24);
                    ms.Write(block, 0, 16);
                }
        }

        public static TexPayload Encode(Bitmap bmp, string format) { return Encode(bmp, format, 99); }

        public static TexPayload Encode(Bitmap bmp, string format, int maxLevels)
        {
            int w = bmp.Width, h = bmp.Height;
            byte[] px = Pixels(bmp);
            bool dxt = format == null || format.ToUpperInvariant() == "DXT5";
            TexPayload p = new TexPayload();
            p.Width = w;
            p.Height = h;
            p.Format = dxt ? 0x35545844u : 21u;
            p.Stride = dxt ? w : w * 4;
            using (MemoryStream ms = new MemoryStream())
            {
                int levels = 0;
                while (true)
                {
                    if (dxt) Dxt5(px, w, h, ms); else ms.Write(px, 0, w * h * 4);
                    levels++;
                    if (Math.Min(w, h) <= 4 || levels >= maxLevels) break;
                    int nw, nh;
                    px = Halve(px, w, h, out nw, out nh);
                    w = nw;
                    h = nh;
                }
                p.Levels = levels;
                p.Data = ms.ToArray();
            }
            return p;
        }

        public static int RenderSheet(string[] names, JObj[] gens, string path, int cell)
        {
            List<KeyValuePair<string, Bitmap>> items = new List<KeyValuePair<string, Bitmap>>();
            for (int i = 0; i < names.Length; i++) items.Add(new KeyValuePair<string, Bitmap>(names[i], Render(gens[i])));
            SaveSheet(items, path, cell);
            foreach (KeyValuePair<string, Bitmap> kv in items) kv.Value.Dispose();
            return items.Count;
        }

        public static void SaveSheet(List<KeyValuePair<string, Bitmap>> items, string path, int cell)
        {
            int cols = Math.Min(8, Math.Max(1, items.Count));
            int rows = (items.Count + cols - 1) / cols;
            using (Bitmap sheet = new Bitmap(cols * cell, rows * (cell + 18), PixelFormat.Format32bppArgb))
            {
                using (Graphics g = Graphics.FromImage(sheet))
                using (Font f = new Font("Consolas", 9f))
                using (Brush tb = new SolidBrush(Color.FromArgb(230, 230, 230)))
                {
                    g.Clear(Color.FromArgb(26, 26, 30));
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    for (int i = 0; i < items.Count; i++)
                    {
                        int x = (i % cols) * cell, y = (i / cols) * (cell + 18);
                        using (Brush bg = new SolidBrush((i + i / cols) % 2 == 0 ? Color.FromArgb(34, 34, 40) : Color.FromArgb(44, 44, 52))) g.FillRectangle(bg, x, y, cell, cell);
                        g.DrawImage(items[i].Value, x + 4, y + 4, cell - 8, cell - 8);
                        g.DrawString(items[i].Key, f, tb, x + 3, y + cell + 1);
                    }
                }
                sheet.Save(path, ImageFormat.Png);
            }
        }
    }
}
