using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace WeaponForge
{
    public class JObj
    {
        public List<KeyValuePair<string, object>> Items = new List<KeyValuePair<string, object>>();

        public int Count { get { return Items.Count; } }

        public void Add(string k, object v) { Items.Add(new KeyValuePair<string, object>(k, v)); }

        public void Set(string k, object v)
        {
            for (int i = 0; i < Items.Count; i++)
                if (Items[i].Key == k) { Items[i] = new KeyValuePair<string, object>(k, v); return; }
            Add(k, v);
        }

        public bool Has(string k)
        {
            for (int i = 0; i < Items.Count; i++) if (Items[i].Key == k) return true;
            return false;
        }

        public object Get(string k)
        {
            for (int i = 0; i < Items.Count; i++) if (Items[i].Key == k) return Items[i].Value;
            return null;
        }

        public void Remove(string k)
        {
            for (int i = Items.Count - 1; i >= 0; i--) if (Items[i].Key == k) Items.RemoveAt(i);
        }

        public string Str(string k) { object o = Get(k); return o == null ? null : Convert.ToString(o, CultureInfo.InvariantCulture); }
        public JObj Obj(string k) { return Get(k) as JObj; }
        public List<object> Arr(string k) { return Get(k) as List<object>; }
        public double Num(string k, double def) { object o = Get(k); return o == null ? def : Json.ToDouble(o); }

        public JObj Clone() { return (JObj)Json.DeepClone(this); }
    }

    public static class Json
    {
        public static object DeepClone(object o)
        {
            JObj j = o as JObj;
            if (j != null)
            {
                JObj c = new JObj();
                foreach (KeyValuePair<string, object> kv in j.Items) c.Add(kv.Key, DeepClone(kv.Value));
                return c;
            }
            List<object> l = o as List<object>;
            if (l != null)
            {
                List<object> c = new List<object>();
                foreach (object x in l) c.Add(DeepClone(x));
                return c;
            }
            return o;
        }

        public static double ToDouble(object o)
        {
            if (o is double) return (double)o;
            if (o is float) return (double)(float)o;
            if (o is bool) return (bool)o ? 1 : 0;
            string s = o as string;
            if (s != null)
            {
                if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) return (double)Convert.ToUInt64(s.Substring(2), 16);
                if (s == "NaN") return double.NaN;
                if (s == "Infinity") return double.PositiveInfinity;
                if (s == "-Infinity") return double.NegativeInfinity;
                return double.Parse(s, CultureInfo.InvariantCulture);
            }
            return Convert.ToDouble(o, CultureInfo.InvariantCulture);
        }

        public static float ToFloat(object o)
        {
            if (o is float) return (float)o;
            return (float)ToDouble(o);
        }

        public static string FloatStr(float f)
        {
            if (float.IsNaN(f)) return "\"NaN\"";
            if (float.IsPositiveInfinity(f)) return "\"Infinity\"";
            if (float.IsNegativeInfinity(f)) return "\"-Infinity\"";
            if (f == 0f) return BitConverter.ToInt32(BitConverter.GetBytes(f), 0) == 0 ? "0" : "-0.0";
            float af = Math.Abs(f);
            if (af >= 1e-5f && af < 1e9f)
            {
                for (int p = 0; p <= 9; p++)
                {
                    string s = f.ToString("F" + p, CultureInfo.InvariantCulture);
                    float back;
                    if (float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out back) && back == f) return s;
                }
            }
            for (int p = 1; p <= 9; p++)
            {
                string s = f.ToString("G" + p, CultureInfo.InvariantCulture);
                float back;
                if (float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out back) && back == f) return s;
            }
            return f.ToString("R", CultureInfo.InvariantCulture);
        }

        static void WriteString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 32 || c > 126) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }

        static bool IsFlat(object o)
        {
            List<object> l = o as List<object>;
            if (l == null) return !(o is JObj);
            foreach (object x in l) if (x is JObj || x is List<object>) return false;
            return true;
        }

        public static string Write(object o, bool pretty)
        {
            StringBuilder sb = new StringBuilder();
            WriteValue(sb, o, pretty, 0);
            return sb.ToString();
        }

        static void Indent(StringBuilder sb, int depth) { sb.Append('\n'); sb.Append(' ', depth * 2); }

        static void WriteValue(StringBuilder sb, object o, bool pretty, int depth)
        {
            if (o == null) { sb.Append("null"); return; }
            if (o is string) { WriteString(sb, (string)o); return; }
            if (o is bool) { sb.Append((bool)o ? "true" : "false"); return; }
            if (o is float) { sb.Append(FloatStr((float)o)); return; }
            if (o is double)
            {
                double d = (double)o;
                if (d == Math.Floor(d) && Math.Abs(d) < 1e15) sb.Append(((long)d).ToString(CultureInfo.InvariantCulture));
                else sb.Append(d.ToString("R", CultureInfo.InvariantCulture));
                return;
            }
            if (o is int || o is long || o is uint || o is ulong || o is short || o is ushort || o is byte || o is decimal)
            {
                sb.Append(Convert.ToString(o, CultureInfo.InvariantCulture));
                return;
            }
            JObj j = o as JObj;
            if (j != null)
            {
                if (j.Count == 0) { sb.Append("{}"); return; }
                sb.Append('{');
                for (int i = 0; i < j.Items.Count; i++)
                {
                    if (i > 0) sb.Append(',');
                    if (pretty) Indent(sb, depth + 1);
                    WriteString(sb, j.Items[i].Key);
                    sb.Append(pretty ? ": " : ":");
                    WriteValue(sb, j.Items[i].Value, pretty, depth + 1);
                }
                if (pretty) Indent(sb, depth);
                sb.Append('}');
                return;
            }
            IEnumerable e = o as IEnumerable;
            if (e != null)
            {
                List<object> l = new List<object>();
                foreach (object x in e) l.Add(x);
                if (l.Count == 0) { sb.Append("[]"); return; }
                bool flat = IsFlat(l);
                sb.Append('[');
                for (int i = 0; i < l.Count; i++)
                {
                    if (i > 0) sb.Append(pretty && flat ? ", " : ",");
                    if (pretty && !flat) Indent(sb, depth + 1);
                    WriteValue(sb, l[i], pretty, depth + 1);
                }
                if (pretty && !flat) Indent(sb, depth);
                sb.Append(']');
                return;
            }
            WriteString(sb, o.ToString());
        }

        public static object Parse(string text)
        {
            int i = 0;
            object v = ParseValue(text, ref i);
            SkipWs(text, ref i);
            if (i < text.Length) throw new FormatException("JSON: unexpected text at position " + i);
            return v;
        }

        static void SkipWs(string s, ref int i)
        {
            while (i < s.Length)
            {
                char c = s[i];
                if (c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '﻿') { i++; continue; }
                if (c == '/' && i + 1 < s.Length && s[i + 1] == '/')
                {
                    while (i < s.Length && s[i] != '\n') i++;
                    continue;
                }
                break;
            }
        }

        static object ParseValue(string s, ref int i)
        {
            SkipWs(s, ref i);
            if (i >= s.Length) throw new FormatException("JSON: unexpected end");
            char c = s[i];
            if (c == '{')
            {
                i++;
                JObj o = new JObj();
                SkipWs(s, ref i);
                if (s[i] == '}') { i++; return o; }
                while (true)
                {
                    SkipWs(s, ref i);
                    if (s[i] != '"') throw new FormatException("JSON: expected a key at position " + i + " near '" + Near(s, i) + "'");
                    string k = ParseString(s, ref i);
                    SkipWs(s, ref i);
                    if (s[i] != ':') throw new FormatException("JSON: expected ':' at position " + i);
                    i++;
                    o.Add(k, ParseValue(s, ref i));
                    SkipWs(s, ref i);
                    if (s[i] == ',') { i++; SkipWs(s, ref i); if (s[i] == '}') { i++; return o; } continue; }
                    if (s[i] == '}') { i++; return o; }
                    throw new FormatException("JSON: expected ',' or '}' at position " + i + " near '" + Near(s, i) + "'");
                }
            }
            if (c == '[')
            {
                i++;
                List<object> l = new List<object>();
                SkipWs(s, ref i);
                if (s[i] == ']') { i++; return l; }
                while (true)
                {
                    l.Add(ParseValue(s, ref i));
                    SkipWs(s, ref i);
                    if (s[i] == ',') { i++; SkipWs(s, ref i); if (s[i] == ']') { i++; return l; } continue; }
                    if (s[i] == ']') { i++; return l; }
                    throw new FormatException("JSON: expected ',' or ']' at position " + i + " near '" + Near(s, i) + "'");
                }
            }
            if (c == '"') return ParseString(s, ref i);
            if (string.CompareOrdinal(s, i, "true", 0, 4) == 0) { i += 4; return true; }
            if (string.CompareOrdinal(s, i, "false", 0, 5) == 0) { i += 5; return false; }
            if (string.CompareOrdinal(s, i, "null", 0, 4) == 0) { i += 4; return null; }
            int st = i;
            while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '-' || s[i] == '+' || s[i] == '.' || s[i] == 'e' || s[i] == 'E')) i++;
            if (i == st) throw new FormatException("JSON: unexpected character '" + c + "' at position " + i);
            return double.Parse(s.Substring(st, i - st), NumberStyles.Float, CultureInfo.InvariantCulture);
        }

        static string Near(string s, int i)
        {
            int a = Math.Max(0, i - 20);
            return s.Substring(a, Math.Min(40, s.Length - a)).Replace("\n", " ").Replace("\r", "");
        }

        static string ParseString(string s, ref int i)
        {
            StringBuilder sb = new StringBuilder();
            i++;
            while (i < s.Length && s[i] != '"')
            {
                char c = s[i++];
                if (c != '\\') { sb.Append(c); continue; }
                char e = s[i++];
                switch (e)
                {
                    case 'n': sb.Append('\n'); break;
                    case 'r': sb.Append('\r'); break;
                    case 't': sb.Append('\t'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'u': sb.Append((char)Convert.ToInt32(s.Substring(i, 4), 16)); i += 4; break;
                    default: sb.Append(e); break;
                }
            }
            i++;
            return sb.ToString();
        }
    }
}
