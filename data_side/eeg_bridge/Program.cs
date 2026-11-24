using System;
using System.Configuration;
using System.Threading;

namespace EegBridge
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            bool simulate = Array.IndexOf(args, "--simulate") >= 0;
            string device = Arg(args, "--device");

            string devCode = Arg(args, "--dev-code")
                          ?? Environment.GetEnvironmentVariable("NEEURO_DEV_CODE")
                          ?? ConfigurationManager.AppSettings["DeveloperCode"];

            IEegSource source;
            if (simulate)
            {
                source = new SimulatedSource();
            }
            else
            {
#if NEEURO_SDK
                if (string.IsNullOrWhiteSpace(devCode) || devCode == "DEVCODE")
                {
                    Console.Error.WriteLine("No developer code. Use: EegBridge.exe --dev-code YOUR_CODE   (or set NEEURO_DEV_CODE)");
                    return 1;
                }
                source = new NeeuroSource(devCode, device);
#else
                Console.Error.WriteLine("Built without the NeeuroOS SDK (lib\\SenzeBandWindowsIPC_ClientDLL.dll missing). Use --simulate.");
                return 1;
#endif
            }

            UdpLink link;
            try { link = new UdpLink(brainPort: 5001, commandPort: 5005); }
            catch (Exception e)
            {
                Console.Error.WriteLine("Could not open UDP port 5005 (is another bridge or sim_band.py running?): " + e.Message);
                return 1;
            }

            source.RawEeg200ms += data => link.Send(Json.Obj("type", "eeg", "data", data));
            source.ChannelStatus += ch => link.Send(Json.Obj("type", "quality", "channels", ch));
            source.Impedance += k => link.Send(Json.Obj("type", "impedance", "kohm", k));
            source.Evoke += ms => link.Send(Json.Obj("type", "evoke", "ms", ms));
            source.BandPower += d => link.Send(Json.Obj("type", "bands", "names", BandNames(d.GetLength(1)), "values", Rows(d)));
            source.MentalState += (name, v) => link.Send(Json.Obj("type", "sdk_state", "name", name, "value", v));
            source.Flag += (name, v) => link.Send(Json.Obj("type", "flag", "name", name, "value", v));
            source.Status += (state, detail) =>
            {
                Console.WriteLine($"[bridge] {state} {detail}");
                link.Send(Json.Obj("type", "status", "state", state, "detail", detail ?? ""));
            };

            link.CommandReceived += cmd =>
            {
                switch (cmd)
                {
                    case "start": source.StartEeg(); break;
                    case "stop": source.StopEeg(); break;
                    case "impedance_on": source.ImpedanceCheck(true); break;
                    case "impedance_off": source.ImpedanceCheck(false); break;
                    case "evoke": source.SendEvokeMarker(); break;
                    case "ping": link.Send(Json.Obj("type", "status", "state", source.State, "detail", "pong")); break;
                    default: Console.WriteLine($"[bridge] unknown command '{cmd}'"); break;
                }
            };

            var quit = new ManualResetEvent(false);
            Console.CancelKeyPress += (s, e) => { e.Cancel = true; quit.Set(); };

            link.Start();
            source.Begin();
            Console.WriteLine("[bridge] running, Ctrl+C to quit");
            quit.WaitOne();

            Console.WriteLine("[bridge] shutting down");
            source.Dispose();
            link.Dispose();
            return 0;
        }

        private static string[] BandNames(int n)
        {
            string[] all = { "delta", "theta", "alpha", "beta", "gamma", "low_alpha", "high_alpha", "low_beta", "high_beta" };
            var names = new string[n];
            for (int i = 0; i < n; i++) names[i] = i < all.Length ? all[i] : "band" + i;
            return names;
        }

        private static float[][] Rows(float[,] d)
        {
            var rows = new float[d.GetLength(0)][];
            for (int c = 0; c < rows.Length; c++)
            {
                rows[c] = new float[d.GetLength(1)];
                for (int b = 0; b < rows[c].Length; b++) rows[c][b] = d[c, b];
            }
            return rows;
        }

        private static string Arg(string[] args, string name)
        {
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }
    }
}
