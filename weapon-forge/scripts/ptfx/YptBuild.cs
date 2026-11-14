using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text;

namespace WeaponForge
{
    public static class PtfxBuild
    {
        public static string RangesPath;

        static JObj LoadSheets(string archetypesPath)
        {
            string p = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(archetypesPath)), "ptfx-sheets.json");
            return File.Exists(p) ? (JObj)Json.Parse(File.ReadAllText(p)) : new JObj();
        }

        public static bool IsDesign(JObj j)
        {
            if (j.Has("emitters") || j.Has("particles")) return false;
            foreach (object o in j.Arr("effects") ?? new List<object>())
            {
                JObj e = o as JObj;
                if (e != null && e.Has("layers")) return true;
            }
            return j.Has("dict");
        }

        public static string Build(string specPath, string defaultsPath, string archetypesPath, string outPath, bool allowDerived, string dumpSpecPath)
        {
            StringBuilder rep = new StringBuilder();
            string baseDir = Path.GetDirectoryName(Path.GetFullPath(specPath));
            JObj input = (JObj)Json.Parse(File.ReadAllText(specPath));
            Defaults defs = Defaults.Load(defaultsPath);
            JObj spec = input;
            List<string> warnings = new List<string>();
            if (IsDesign(input))
            {
                JObj arch = File.Exists(archetypesPath) ? (JObj)Json.Parse(File.ReadAllText(archetypesPath)) : new JObj();
                JObj own = input.Obj("archetypes");
                if (own != null) foreach (KeyValuePair<string, object> kv in own.Items) arch.Set(kv.Key, kv.Value);
                DesignCompiler dc = new DesignCompiler(arch);
                dc.BuiltinSheets = LoadSheets(archetypesPath);
                spec = dc.Expand(input);
                foreach (string s in dc.Summary) rep.AppendLine(s);
                warnings.AddRange(dc.Warnings);
            }
            if (spec.Has("_source") && !allowDerived)
                throw new InvalidOperationException("this spec was decompiled from " + spec.Str("_source") + ". Decompiled specs are study material: rebuilding one copies someone else's effect. Write a design instead, or pass -AllowDerived when the source dictionary is your own work.");
            if (!string.IsNullOrEmpty(dumpSpecPath)) File.WriteAllText(dumpSpecPath, Json.Write(spec, true));

            string dict = spec.Str("name");
            if (Directory.Exists(outPath)) outPath = Path.Combine(outPath, dict + ".ypt");
            if (!string.Equals(Path.GetFileNameWithoutExtension(outPath), dict, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("the file name must equal the dictionary name: expected " + dict + ".ypt, got " + Path.GetFileName(outPath));

            Compiler c = new Compiler(defs);
            c.TextureProvider = delegate (JObj tj, string name) { return DesignCompiler.GenerateTexture(tj, name, baseDir); };
            Node root = c.Run(spec);
            warnings.AddRange(c.Warnings);
            Rsc rsc = YptWriter.Build(root);
            string dir = Path.GetDirectoryName(Path.GetFullPath(outPath));
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
            rsc.Save(outPath);

            YptFile back = YptFile.Parse(outPath);
            string status = back.Status();
            Decompiler d = new Decompiler(back, defs);
            JObj again = d.Run();
            List<string> names = new List<string>();
            foreach (object o in again.Arr("effects") ?? new List<object>())
            {
                JObj e = (JObj)o;
                names.Add(e.Str("Name") + (e.Num("NumLoops", 0) != 0 ? " (looped)" : ""));
            }
            foreach (object o in again.Arr("textures") ?? new List<object>())
            {
                JObj t = (JObj)o;
                rep.AppendLine("texture " + t.Str("name") + " " + t.Num("width", 0) + "x" + t.Num("height", 0) + " " + t.Str("format") + " mips=" + t.Num("levels", 0));
            }
            List<KeyValuePair<string, Bitmap>> art = new List<KeyValuePair<string, Bitmap>>();
            foreach (object o in spec.Arr("textures") ?? new List<object>())
            {
                JObj t = (JObj)o;
                string label = t.Str("name");
                if (label.StartsWith(dict + "_", StringComparison.OrdinalIgnoreCase)) label = label.Substring(dict.Length + 1);
                try
                {
                    if (t.Obj("sheet") != null)
                    {
                        SpriteFx.Slot slot = SpriteFx.FindSlot(t.Str("name"));
                        JObj sh = t.Obj("sheet").Clone();
                        foreach (object co in sh.Arr("cells") ?? new List<object>())
                        {
                            JObj c0 = co as JObj;
                            if (c0 != null && c0.Str("shape") == "image" && c0.Has("file") && !Path.IsPathRooted(c0.Str("file")) && baseDir != null)
                                c0.Set("file", Path.Combine(baseDir, c0.Str("file")));
                        }
                        int n;
                        art.Add(new KeyValuePair<string, Bitmap>((t.Str("sheetName") ?? label) + " " + slot.Cols + "x" + slot.Rows, SpriteFx.RenderSheetTexture(sh, slot.Cols, slot.Rows, out n)));
                    }
                    else if (t.Obj("gen") != null || t.Has("file"))
                    {
                        JObj g = t.Obj("gen") != null ? t.Obj("gen").Clone() : new JObj();
                        if (t.Obj("gen") == null)
                        {
                            g.Add("shape", "image");
                            g.Add("file", t.Str("file"));
                            if (t.Has("size")) g.Add("size", t.Num("size", 256));
                            if (t.Has("width")) g.Add("width", t.Num("width", 256));
                            if (t.Has("height")) g.Add("height", t.Num("height", 256));
                        }
                        if (g.Str("shape") == "image" && g.Has("file") && !Path.IsPathRooted(g.Str("file")) && baseDir != null) g.Set("file", Path.Combine(baseDir, g.Str("file")));
                        art.Add(new KeyValuePair<string, Bitmap>(label, SpriteGen.Render(g)));
                    }
                }
                catch (Exception ex) { warnings.Add("sprite preview of " + label + " failed: " + ex.Message); }
            }
            string artDir = Path.GetDirectoryName(Path.GetFullPath(outPath));
            if (string.Equals(Path.GetFileName(artDir), "stream", StringComparison.OrdinalIgnoreCase))
            {
                artDir = Path.Combine(Path.GetDirectoryName(artDir), "source");
                if (!Directory.Exists(artDir)) Directory.CreateDirectory(artDir);
            }
            try { rep.Append(PtfxPreview.Render(spec, Path.Combine(artDir, dict + ".preview.png"), 8, 240, baseDir)); }
            catch (Exception ex) { warnings.Add("preview failed: " + ex.Message); }
            if (art.Count > 0)
            {
                string sheet = Path.Combine(artDir, dict + ".sprites.png");
                SpriteGen.SaveSheet(art, sheet, 160);
                foreach (KeyValuePair<string, Bitmap> kv in art) kv.Value.Dispose();
                rep.AppendLine("sprite preview " + sheet);
            }
            long size = new FileInfo(outPath).Length;
            if (size > 2 * 1024 * 1024) warnings.Add("file is " + (size / 1024) + " KB; keep a set under 2 MB");
            foreach (string n in names) rep.AppendLine("callable effect: " + n);

            int errors = 0;
            Ranges ranges = Ranges.Load(RangesPath);
            if (ranges == null) warnings.Add("ptfx-ranges.json not found, so the file was not compared with real files; run ptfx.ps1 ranges");
            else
            {
                Decompiler fd = new Decompiler(back, null);
                fd.Full = true;
                LintResult lint = Linter.Check(spec, fd.Run(), ranges);
                foreach (string s in lint.Errors) rep.AppendLine("ERROR " + s);
                foreach (string s in lint.Warnings) warnings.Add(s);
                foreach (string s in lint.Notes) rep.AppendLine("NOTE " + s);
                rep.AppendLine(lint.Summary() + " (compared with " + ranges.Files + " real files)");
                errors = lint.Errors.Count;
            }
            foreach (string w in warnings) rep.AppendLine("WARN " + w);
            if (status != "clean") rep.AppendLine(back.Census());
            string verdict = status != "clean" ? "FAILED-" + status : errors > 0 ? "FAILED-lint" : "ok";
            rep.AppendLine("RESULT " + verdict + " file=" + outPath + " bytes=" + size + " effects=" + names.Count + " errors=" + errors + " warnings=" + warnings.Count + " sys=" + Rsc.DescribeFlags(back.R.SysFlags) + " gfx=" + Rsc.DescribeFlags(back.R.GfxFlags));
            return rep.ToString();
        }

        public static string Preview(string path, string defaultsPath, string archetypesPath, string outPath)
        {
            JObj spec;
            string baseDir = Path.GetDirectoryName(Path.GetFullPath(path));
            if (path.EndsWith(".ypt", StringComparison.OrdinalIgnoreCase))
            {
                Decompiler d = new Decompiler(YptFile.Parse(path), null);
                d.Full = true;
                spec = d.Run();
            }
            else
            {
                spec = (JObj)Json.Parse(File.ReadAllText(path));
                if (IsDesign(spec))
                {
                    JObj arch = File.Exists(archetypesPath) ? (JObj)Json.Parse(File.ReadAllText(archetypesPath)) : new JObj();
                    JObj own = spec.Obj("archetypes");
                    if (own != null) foreach (KeyValuePair<string, object> kv in own.Items) arch.Set(kv.Key, kv.Value);
                    DesignCompiler pdc = new DesignCompiler(arch);
                    pdc.BuiltinSheets = LoadSheets(archetypesPath);
                    spec = pdc.Expand(spec);
                }
            }
            return PtfxPreview.Render(spec, outPath, 8, 240, baseDir);
        }

        public static string Themes(string themesPath)
        {
            JObj themes = (JObj)Json.Parse(File.ReadAllText(themesPath));
            StringBuilder sb = new StringBuilder();
            foreach (KeyValuePair<string, object> kv in themes.Items)
            {
                JObj t = (JObj)kv.Value;
                sb.Append(kv.Key.PadRight(10)).AppendLine(t.Str("about"));
                sb.Append("".PadRight(10)).Append("fits: ").AppendLine(t.Str("families"));
            }
            sb.AppendLine();
            sb.AppendLine("ptfx.ps1 new -Theme <theme> -Name <set id> -Out <folder> [-Colors \"primary=#rrggbb,secondary=#rrggbb\"]");
            return sb.ToString();
        }

        // Writes a ready-to-edit design for one set: the theme's layers, with the set's own dictionary and effect names.
        public static string NewFromTheme(string themesPath, string theme, string name, string colors, string outPath)
        {
            JObj themes = (JObj)Json.Parse(File.ReadAllText(themesPath));
            JObj t = themes.Obj(theme);
            if (t == null)
            {
                List<string> names = new List<string>();
                foreach (KeyValuePair<string, object> kv in themes.Items) names.Add(kv.Key);
                throw new InvalidDataException("unknown theme '" + theme + "'. Themes: " + string.Join(", ", names.ToArray()));
            }
            if (!System.Text.RegularExpressions.Regex.IsMatch(name ?? "", "^[a-z][a-z0-9_]{1,30}$")) throw new InvalidDataException("-Name must be 2-31 chars of a-z, 0-9, _ and start with a letter: " + name);
            JObj pal = t.Obj("palette").Clone();
            if (!string.IsNullOrEmpty(colors))
                foreach (string part in colors.Split(','))
                {
                    string[] kv = part.Split('=');
                    if (kv.Length != 2) throw new InvalidDataException("-Colors must look like \"primary=#ff0000,secondary=#00ff00\"");
                    string key = kv[0].Trim(), val = kv[1].Trim();
                    SpriteGen.ParseColor(val, Color.White);
                    if (!pal.Has(key)) throw new InvalidDataException("the palette of theme '" + theme + "' has no colour named '" + key + "'");
                    pal.Set(key, val.StartsWith("#") ? val : "#" + val);
                }
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("{");
            sb.AppendLine("  \"dict\": \"" + name + "_fx\",");
            sb.AppendLine("  \"theme\": \"" + theme + "\",");
            sb.AppendLine("  \"palette\": " + Json.Write(pal, false) + ",");
            if (t.Obj("sheets") != null) sb.AppendLine("  \"sheets\": " + Json.Write(t.Obj("sheets"), false) + ",");
            sb.AppendLine("  \"effects\": [");
            string[] phases = new string[] { "hold", "hit", "kill" };
            for (int i = 0; i < phases.Length; i++)
            {
                JObj e = t.Obj(phases[i]);
                if (e == null) continue;
                sb.AppendLine("    {");
                sb.AppendLine("      \"name\": \"" + name + "_" + phases[i] + "\"," + (phases[i] == "hold" ? " \"loop\": true," : "") + " \"duration\": " + Json.Write(e.Get("duration"), false) + ",");
                sb.AppendLine("      \"layers\": [");
                List<object> layers = e.Arr("layers");
                for (int k = 0; k < layers.Count; k++) sb.AppendLine("        " + Json.Write(layers[k], false) + (k < layers.Count - 1 ? "," : ""));
                sb.AppendLine("      ]");
                sb.AppendLine("    }" + (i < phases.Length - 1 ? "," : ""));
            }
            sb.AppendLine("  ]");
            sb.AppendLine("}");
            if (Directory.Exists(outPath)) outPath = Path.Combine(outPath, name + ".ptfx.json");
            string dir = Path.GetDirectoryName(Path.GetFullPath(outPath));
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
            if (File.Exists(outPath)) throw new InvalidOperationException(outPath + " already exists; delete it or choose another -Out");
            File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
            return "wrote " + outPath + "\ndictionary " + name + "_fx with effects " + name + "_hold (looped), " + name + "_hit, " + name + "_kill\nnext: edit the palette and layers, then ptfx.ps1 build -Spec \"" + outPath + "\" -Out <weapon_x\\stream>";
        }

        public static string Recipes(string archetypesPath)
        {
            JObj arch = (JObj)Json.Parse(File.ReadAllText(archetypesPath));
            StringBuilder sb = new StringBuilder();
            foreach (KeyValuePair<string, object> kv in arch.Items)
            {
                JObj a = (JObj)kv.Value;
                string kind = a.Has("use") ? "like " + a.Str("use") : a.Has("burst") ? "burst" : a.Has("rate") ? "stream" : "";
                sb.Append(kv.Key.PadRight(18)).Append(kind.PadRight(20)).AppendLine(a.Str("about"));
            }
            sb.AppendLine();
            sb.AppendLine("sprite shapes: " + string.Join(", ", SpriteGen.Shapes));
            sb.AppendLine();
            sb.AppendLine("built-in sheets (use the name as a layer texture):");
            foreach (KeyValuePair<string, object> kv in LoadSheets(archetypesPath).Items)
            {
                JObj s = (JObj)kv.Value;
                sb.Append("  ").Append(kv.Key.PadRight(16)).Append((s.Str("grid") ?? "2x2").PadRight(6)).Append(s.Has("flipbook") ? (s.Num("loop", 0) != 0 ? "loop   " : "frames ") : "icons  ").AppendLine(s.Str("about"));
            }
            return sb.ToString();
        }
    }
}
