using System;
using System.Globalization;
using System.Text;

namespace EegBridge
{

    internal static class Json
    {
        public static string Obj(params object[] kv)
        {
            var sb = new StringBuilder("{");
            for (int i = 0; i + 1 < kv.Length; i += 2)
            {
                if (i > 0) sb.Append(',');
                sb.Append(Str((string)kv[i])).Append(':').Append(Val(kv[i + 1]));
            }
            return sb.Append('}').ToString();
        }

        public static string Num(double d) =>
            double.IsNaN(d) || double.IsInfinity(d) ? "null" : d.ToString("R", CultureInfo.InvariantCulture);

        private static string Val(object v)
        {
            if (v == null) return "null";
            if (v is string) return Str((string)v);
            if (v is bool) return (bool)v ? "true" : "false";
            if (v is int) return ((int)v).ToString(CultureInfo.InvariantCulture);
            if (v is float) return Num((float)v);
            if (v is double) return Num((double)v);
            var fa = v as float[];
            if (fa != null) return Arr(fa.Length, i => Num(fa[i]));
            var ia = v as int[];
            if (ia != null) return Arr(ia.Length, i => ia[i].ToString(CultureInfo.InvariantCulture));
            var ba = v as bool[];
            if (ba != null) return Arr(ba.Length, i => ba[i] ? "true" : "false");
            var sa = v as string[];
            if (sa != null) return Arr(sa.Length, i => Str(sa[i]));
            var faa = v as float[][];
            if (faa != null) return Arr(faa.Length, i => Val(faa[i]));
            return Str(v.ToString());
        }

        private static string Arr(int n, Func<int, string> item)
        {
            var sb = new StringBuilder("[");
            for (int i = 0; i < n; i++) { if (i > 0) sb.Append(','); sb.Append(item(i)); }
            return sb.Append(']').ToString();
        }

        private static string Str(string s)
        {
            var sb = new StringBuilder("\"");
            foreach (char c in s)
            {
                if (c == '"' || c == '\\') sb.Append('\\').Append(c);
                else if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                else sb.Append(c);
            }
            return sb.Append('"').ToString();
        }
    }
}
