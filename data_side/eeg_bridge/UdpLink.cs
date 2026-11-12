using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace EegBridge
{

    internal sealed class UdpLink : IDisposable
    {
        public event Action<string> CommandReceived;

        private readonly UdpClient _out = new UdpClient();
        private readonly IPEndPoint _brain;
        private readonly UdpClient _in;
        private Thread _listener;
        private volatile bool _running;
        private static readonly Regex CmdRx = new Regex("\"cmd\"\\s*:\\s*\"([a-z_]+)\"", RegexOptions.Compiled);

        public UdpLink(int brainPort, int commandPort)
        {
            _brain = new IPEndPoint(IPAddress.Loopback, brainPort);
            _in = new UdpClient(new IPEndPoint(IPAddress.Loopback, commandPort));
            _in.Client.ReceiveTimeout = 500;
        }

        public void Start()
        {
            _running = true;
            _listener = new Thread(Listen) { IsBackground = true, Name = "cmd-listener" };
            _listener.Start();
        }

        public void Send(string jsonObject)
        {
            double t = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
            string msg = "{\"t\":" + Json.Num(t) + "," + jsonObject.Substring(1);
            byte[] bytes = Encoding.UTF8.GetBytes(msg);
            try { lock (_out) _out.Send(bytes, bytes.Length, _brain); }
            catch (SocketException e) { Console.Error.WriteLine("[bridge] send failed: " + e.Message); }
        }

        private void Listen()
        {
            var any = new IPEndPoint(IPAddress.Any, 0);
            while (_running)
            {
                try
                {
                    string text = Encoding.UTF8.GetString(_in.Receive(ref any));
                    Match m = CmdRx.Match(text);
                    if (m.Success) CommandReceived?.Invoke(m.Groups[1].Value);
                }
                catch (SocketException) {  }
                catch (ObjectDisposedException) { return; }
            }
        }

        public void Dispose()
        {
            _running = false;
            _in.Close();
            _out.Close();
        }
    }
}
