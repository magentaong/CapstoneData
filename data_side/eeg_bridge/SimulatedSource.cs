using System;
using System.Diagnostics;
using System.Threading;

namespace EegBridge
{

    internal sealed class SimulatedSource : IEegSource
    {
        public event Action<float[]> RawEeg200ms;
        public event Action<bool[]> ChannelStatus;
        public event Action<float[]> Impedance;
        public event Action<int> Evoke;
        public event Action<float[,]> BandPower;
        public event Action<string, float> MentalState;
        public event Action<string, bool> Flag;
        public event Action<string, string> Status;

        public string State { get; private set; } = "starting";

        private const int Fs = 250, PerChannel = 50, Channels = 4;
        private const float UvPerUnit = 0.61f;
        private readonly Random _rng = new Random(0);
        private readonly Stopwatch _clock = new Stopwatch();
        private Timer _timer;
        private volatile bool _streaming, _impedance;
        private long _n, _lastSlow, _stressUntil;
        private double _reaction;

        public void Begin()
        {
            Set("connected", "simulator");
            Set("auth_ok", "simulator");
            _clock.Start();
            _timer = new Timer(_ => Tick(), null, 0, 200);
            StartEeg();
        }

        private void Tick()
        {
            long ms = _clock.ElapsedMilliseconds;
            bool stressed = ms < _stressUntil;

            if (_streaming && !_impedance)
            {
                var data = new float[PerChannel * Channels];
                for (int c = 0; c < Channels; c++)
                    for (int i = 0; i < PerChannel; i++)
                    {
                        double t = (_n + i) / (double)Fs;
                        double uv = (stressed ? 6 : 15) * Math.Sin(2 * Math.PI * 10 * t)
                                  + (stressed ? 10 : 4) * Math.Sin(2 * Math.PI * 20 * t)
                                  + (stressed ? _reaction : 0) * Math.Sin(2 * Math.PI * 2 * t + c)
                                  + Gauss() * 5;
                        data[c * PerChannel + i] = (float)(uv / UvPerUnit);
                    }
                _n += PerChannel;
                RawEeg200ms?.Invoke(data);
            }

            if (ms - _lastSlow >= 1000)
            {
                _lastSlow = ms;
                ChannelStatus?.Invoke(new[] { true, true, true, true });
                Flag?.Invoke("signal_ready", true);
                Flag?.Invoke("connection_ok", true);

                float[] rel = stressed ? new[] { 0.15f, 0.15f, 0.20f, 0.40f, 0.10f }
                                       : new[] { 0.15f, 0.15f, 0.45f, 0.20f, 0.05f };
                var bands = new float[Channels, 5];
                for (int c = 0; c < Channels; c++)
                    for (int b = 0; b < 5; b++) bands[c, b] = rel[b] + (float)(_rng.NextDouble() - 0.5) * 0.02f;
                BandPower?.Invoke(bands);
                MentalState?.Invoke("attention", stressed ? 0.7f : 0.4f);
                MentalState?.Invoke("relaxation", stressed ? 0.2f : 0.6f);
                MentalState?.Invoke("workload", stressed ? 0.8f : 0.3f);
                if (_impedance) Impedance?.Invoke(new[] { 300f + _rng.Next(100), 320f, 410f, 380f });
            }
        }

        private double Gauss()
        {
            double u1 = 1.0 - _rng.NextDouble(), u2 = _rng.NextDouble();
            return Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2);
        }

        public void StartEeg() { _streaming = true; Set("streaming", null); }
        public void StopEeg() { _streaming = false; Set("stopped", null); }
        public void ImpedanceCheck(bool on) { _impedance = on; Set(on ? "impedance_check" : "streaming", null); }
        public void SendEvokeMarker()
        {
            // an evoke marks a game event, the simulated player reacts to about half of them for 6 s
            if (_rng.NextDouble() < 0.5)
            {
                _reaction = 2 + 3 * _rng.NextDouble();
                _stressUntil = _clock.ElapsedMilliseconds + 6000;
            }
            Evoke?.Invoke((int)_clock.ElapsedMilliseconds);
        }

        private void Set(string s, string d) { State = s; Status?.Invoke(s, d); }

        public void Dispose() => _timer?.Dispose();
    }
}
