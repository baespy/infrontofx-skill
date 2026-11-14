using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace WeaponForge
{
    // Reads the textures embedded in a .ypt back into bitmaps, for study sheets and for the preview renderer.
    public static class TexDecode
    {
        const uint DXT1 = 0x31545844, DXT3 = 0x33545844, DXT5 = 0x35545844, ATI1 = 0x31495441, ATI2 = 0x32495441;

        public static List<KeyValuePair<string, TexPayload>> All(YptFile y)
        {
            List<KeyValuePair<string, TexPayload>> res = new List<KeyValuePair<string, TexPayload>>();
            foreach (Node n in y.Nodes)
            {
                if (n.Kind != "Texture") continue;
                TexPayload p = new TexPayload();
                p.Width = n.U16(0x50); p.Height = n.U16(0x52); p.Stride = n.U16(0x56); p.Format = n.U32(0x58); p.Levels = n.Data[0x5D];
                Node dn = n.Target(0x70);
                p.Data = dn == null ? new byte[0] : dn.Data;
                res.Add(new KeyValuePair<string, TexPayload>(n.Label ?? "", p));
            }
            return res;
        }

        public static string FormatName(uint f)
        {
            switch (f)
            {
                case DXT1: return "DXT1";
                case DXT3: return "DXT3";
                case DXT5: return "DXT5";
                case ATI1: return "ATI1";
                case ATI2: return "ATI2";
                case 21: return "A8R8G8B8";
                case 22: return "X8R8G8B8";
                case 28: return "A8";
                case 50: return "L8";
                case 25: return "A1R5G5B5";
                default: return "fmt" + f;
            }
        }

        static void Color565(int c, out int r, out int g, out int b)
        {
            r = ((c >> 11) & 31) * 255 / 31; g = ((c >> 5) & 63) * 255 / 63; b = (c & 31) * 255 / 31;
        }

        static void AlphaBlock(byte[] d, int o, byte[] outA)
        {
            int a0 = d[o], a1 = d[o + 1];
            int[] t = new int[8];
            t[0] = a0; t[1] = a1;
            if (a0 > a1) for (int i = 1; i < 7; i++) t[i + 1] = ((7 - i) * a0 + i * a1) / 7;
            else { for (int i = 1; i < 5; i++) t[i + 1] = ((5 - i) * a0 + i * a1) / 5; t[6] = 0; t[7] = 255; }
            ulong bits = 0;
            for (int i = 0; i < 6; i++) bits |= (ulong)d[o + 2 + i] << (8 * i);
            for (int i = 0; i < 16; i++) outA[i] = (byte)t[(int)((bits >> (3 * i)) & 7)];
        }

        // Returns BGRA, top row first. Null when the format is unknown or the data is short.
        public static byte[] Decode(TexPayload p)
        {
            int w = p.Width, h = p.Height;
            if (w <= 0 || h <= 0 || w > 8192 || h > 8192 || p.Data == null) return null;
            byte[] px = new byte[w * h * 4];
            byte[] d = p.Data;
            uint f = p.Format;
            if (f == DXT1 || f == DXT3 || f == DXT5 || f == ATI1 || f == ATI2)
            {
                int bs = (f == DXT1 || f == ATI1) ? 8 : 16;
                int bw = (w + 3) / 4, bh = (h + 3) / 4;
                if (d.Length < bw * bh * bs) return null;
                byte[] al = new byte[16], al2 = new byte[16];
                int[] cr = new int[4], cg = new int[4], cb = new int[4], ca = new int[4];
                for (int by = 0; by < bh; by++)
                    for (int bx = 0; bx < bw; bx++)
                    {
                        int o = (by * bw + bx) * bs;
                        for (int i = 0; i < 16; i++) al[i] = 255;
                        if (f == ATI1 || f == ATI2)
                        {
                            AlphaBlock(d, o, al);
                            if (f == ATI2) AlphaBlock(d, o + 8, al2);
                            for (int i = 0; i < 16; i++)
                            {
                                int x = bx * 4 + (i & 3), yy = by * 4 + (i >> 2);
                                if (x >= w || yy >= h) continue;
                                int q = (yy * w + x) * 4;
                                px[q] = f == ATI2 ? (byte)255 : al[i]; px[q + 1] = f == ATI2 ? al2[i] : al[i]; px[q + 2] = al[i]; px[q + 3] = 255;
                            }
                            continue;
                        }
                        int co = o;
                        if (f == DXT5) { AlphaBlock(d, o, al); co = o + 8; }
                        else if (f == DXT3) { for (int i = 0; i < 16; i++) al[i] = (byte)(((d[o + i / 2] >> ((i & 1) * 4)) & 15) * 17); co = o + 8; }
                        int c0 = d[co] | (d[co + 1] << 8), c1 = d[co + 2] | (d[co + 3] << 8);
                        Color565(c0, out cr[0], out cg[0], out cb[0]);
                        Color565(c1, out cr[1], out cg[1], out cb[1]);
                        ca[0] = ca[1] = ca[2] = ca[3] = 255;
                        if (c0 > c1 || f != DXT1)
                        {
                            cr[2] = (2 * cr[0] + cr[1]) / 3; cg[2] = (2 * cg[0] + cg[1]) / 3; cb[2] = (2 * cb[0] + cb[1]) / 3;
                            cr[3] = (cr[0] + 2 * cr[1]) / 3; cg[3] = (cg[0] + 2 * cg[1]) / 3; cb[3] = (cb[0] + 2 * cb[1]) / 3;
                        }
                        else
                        {
                            cr[2] = (cr[0] + cr[1]) / 2; cg[2] = (cg[0] + cg[1]) / 2; cb[2] = (cb[0] + cb[1]) / 2;
                            cr[3] = cg[3] = cb[3] = 0; ca[3] = 0;
                        }
                        uint idx = (uint)(d[co + 4] | (d[co + 5] << 8) | (d[co + 6] << 16) | (d[co + 7] << 24));
                        for (int i = 0; i < 16; i++)
                        {
                            int x = bx * 4 + (i & 3), yy = by * 4 + (i >> 2);
                            if (x >= w || yy >= h) continue;
                            int k = (int)((idx >> (2 * i)) & 3);
                            int q = (yy * w + x) * 4;
                            px[q] = (byte)cb[k]; px[q + 1] = (byte)cg[k]; px[q + 2] = (byte)cr[k];
                            px[q + 3] = f == DXT1 ? (byte)ca[k] : al[i];
                        }
                    }
                return px;
            }
            if (f == 21 || f == 22)
            {
                if (d.Length < w * h * 4) return null;
                Buffer.BlockCopy(d, 0, px, 0, w * h * 4);
                if (f == 22) for (int i = 3; i < px.Length; i += 4) px[i] = 255;
                return px;
            }
            if (f == 28 || f == 50)
            {
                if (d.Length < w * h) return null;
                for (int i = 0; i < w * h; i++)
                {
                    byte v = d[i];
                    px[i * 4] = px[i * 4 + 1] = px[i * 4 + 2] = f == 50 ? v : (byte)255;
                    px[i * 4 + 3] = f == 28 ? v : (byte)255;
                }
                return px;
            }
            return null;
        }

        public static Bitmap ToBitmap(TexPayload p)
        {
            byte[] px = Decode(p);
            if (px == null) return null;
            Bitmap bmp = new Bitmap(p.Width, p.Height, PixelFormat.Format32bppArgb);
            BitmapData bd = bmp.LockBits(new Rectangle(0, 0, p.Width, p.Height), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            for (int y = 0; y < p.Height; y++) Marshal.Copy(px, y * p.Width * 4, new IntPtr(bd.Scan0.ToInt64() + (long)y * bd.Stride), p.Width * 4);
            bmp.UnlockBits(bd);
            return bmp;
        }

        // True when the colour channels carry the picture and alpha is flat, which is how the game's *_rgb sheets work.
        public static bool AlphaIsFlat(byte[] bgra)
        {
            int lo = 255, hi = 0;
            for (int i = 3; i < bgra.Length; i += 16) { if (bgra[i] < lo) lo = bgra[i]; if (bgra[i] > hi) hi = bgra[i]; }
            return hi - lo < 8;
        }

        // Writes one PNG per texture, drawn on a dark checker so both alpha sprites and additive RGB sheets read well.
        public static string Export(YptFile y, string outDir, string only)
        {
            StringBuilder sb = new StringBuilder();
            if (!Directory.Exists(outDir)) Directory.CreateDirectory(outDir);
            foreach (KeyValuePair<string, TexPayload> kv in All(y))
            {
                if (!string.IsNullOrEmpty(only) && !string.Equals(only, kv.Key, StringComparison.OrdinalIgnoreCase)) continue;
                TexPayload p = kv.Value;
                string line = kv.Key + " " + p.Width + "x" + p.Height + " " + FormatName(p.Format) + " mips=" + p.Levels;
                using (Bitmap raw = ToBitmap(p))
                {
                    if (raw == null) { sb.AppendLine(line + "  (format not decodable)"); continue; }
                    int scale = Math.Max(1, Math.Max(p.Width, p.Height) / 1024);
                    int ow = p.Width / scale, oh = p.Height / scale;
                    using (Bitmap canvas = new Bitmap(ow, oh, PixelFormat.Format32bppArgb))
                    using (Graphics g = Graphics.FromImage(canvas))
                    {
                        using (SolidBrush a = new SolidBrush(Color.FromArgb(34, 36, 44)), b = new SolidBrush(Color.FromArgb(46, 48, 58)))
                            for (int ty = 0; ty < oh; ty += 16)
                                for (int tx = 0; tx < ow; tx += 16) g.FillRectangle(((tx / 16 + ty / 16) & 1) == 0 ? a : b, tx, ty, 16, 16);
                        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                        g.DrawImage(raw, new Rectangle(0, 0, ow, oh));
                        string safe = kv.Key;
                        foreach (char c in Path.GetInvalidFileNameChars()) safe = safe.Replace(c, '_');
                        string file = Path.Combine(outDir, safe + ".png");
                        canvas.Save(file, ImageFormat.Png);
                        sb.AppendLine(line + "  -> " + file);
                    }
                }
            }
            return sb.ToString();
        }
    }
}
