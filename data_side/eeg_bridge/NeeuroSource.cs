#if NEEURO_SDK

using System;
using System.Threading;
using NeeuroOSWindows;

namespace EegBridge
{
    internal sealed class NeeuroSource : IEegSource, SenzeBandConnectInterface.deviceAuthenticationInterface
    {
        public event Action<float[]> RawEeg200ms;
        public event Action<int, int, int> HeartRate;
        public event Action<bool[]> ChannelStatus;
        public event Action<float[]> Impedance;
        public event Action<int> Evoke;
        public event Action<float[,]> BandPower;
        public event Action<string, float> MentalState;
        public event Action<string, bool> Flag;
        public event Action<string, string> Status;

        public string State { get; private set; } = "starting";

        private readonly string _devCode;
        private readonly string _wantedDevice;
        private readonly object _lock = new object();
        private string _connectedId;
        private bool _connecting, _authenticated, _disposed;
        private Timer _retryTimer, _authWatchdog;

        private static SenzeBandWindowsInterface SBWI => SenzeBandWindowsInterface.getSBWIHandler();
        private static SenzeBandConnectInterface SBCI => SenzeBandConnectInterface.getSBCIHandler();

        public NeeuroSource(string devCode, string wantedDevice)
        {
            _devCode = devCode;
            _wantedDevice = wantedDevice;
        }

        public void Begin()
        {
            SetState("starting", "SDK version " + SafeVersion());
            SBWI.replaceBTStatus(on => { if (!on) SetState("error", "Bluetooth is off on this PC"); });

            SBWI.initializeSBWI(OnConnected, OnConnectFailOrDisconnect, _devCode, OnInitialised, OnSdkLog);
        }

        private void OnInitialised()
        {

            SBCI.assignRawData200msDelegate(d => RawEeg200ms?.Invoke(d));
            SBCI.assignChannelDelegate(ch => ChannelStatus?.Invoke(ch));
            SBCI.assignImpedanceDelegate(k => Impedance?.Invoke(k));
            SBCI.assignSPO2HeartRateDelegate(v =>
            {
                if (v != null && v.Length >= 3) HeartRate?.Invoke(v[0], v[1], v[2]);
            });
            SBCI.assignEvokeDelegate(ms => Evoke?.Invoke(ms));
            SBCI.assignABDTDelegate(d => BandPower?.Invoke(d));
            SBCI.assignAttentionDelegate(v => MentalState?.Invoke("attention", v));
            SBCI.assignRelaxationDelegate(v => MentalState?.Invoke("relaxation", v));
            SBCI.assignMentalWorkloadDelegate(v => MentalState?.Invoke("workload", v));
            SBCI.assignSignalReadyDelegate(ok => Flag?.Invoke("signal_ready", ok));
            SBCI.assignConnectionCheckDelegate(ok => Flag?.Invoke("connection_ok", ok));
            SBCI.assignBatteryDelegate(b => Status?.Invoke("battery", b));
            SBCI.assignMCUDelegate(id => Status?.Invoke("device_id", id));

            DeviceAuthentication.instance.AssignAuthenticationStatusCallbacks(this);
            StartScan();
        }

        private void StartScan()
        {
            if (_disposed) return;
            lock (_lock) { _connecting = false; }
            if (SBWI.startScanning(OnScan, OnScanUpdate, () => { }))
            {
                SetState("scanning", _wantedDevice == null ? "will connect to the first SenzeBand found"
                                                           : "looking for " + _wantedDevice);
            }
            else
            {
                SetState("error", "could not start scanning, retrying in 3 s");
                RetryIn(3000, StartScan);
            }
        }

        private void OnScan(ScannedDeviceClass dev, bool addDevice)
        {
            if (!addDevice || dev == null) return;
            Console.WriteLine($"[sdk] found '{dev.deviceName}' id={dev.deviceID} addr={dev.deviceAddress} connected={dev.isConnected}");

            if (_wantedDevice != null && !Matches(dev, _wantedDevice)) return;
            lock (_lock)
            {
                if (_connecting || _connectedId != null) return;
                _connecting = true;
            }
            SetState("connecting", dev.deviceName + " " + dev.deviceID);
            SBWI.connectBT(dev.deviceID);
            SBWI.stopScanning();
        }

        private void OnScanUpdate(ScannedDeviceClass dev) { }

        private static bool Matches(ScannedDeviceClass d, string want) =>
            Contains(d.deviceName, want) || Contains(d.deviceID, want) || Contains(d.deviceAddress, want);

        private static bool Contains(string s, string part) =>
            s != null && s.IndexOf(part, StringComparison.OrdinalIgnoreCase) >= 0;

        private void OnConnected(string address, string id, bool hasExistingConnection)
        {
            if (hasExistingConnection) return;
            lock (_lock) { _connectedId = id; _connecting = false; _authenticated = false; }
            SetState("connected", id);

            _authWatchdog?.Dispose();
            _authWatchdog = new Timer(_ =>
            {
                if (!_authenticated && _connectedId != null)
                {
                    SetState("authenticating", "no result yet, requesting authentication again");
                    DeviceAuthentication.instance.getAuthentication();
                }
            }, null, 8000, 15000);
        }

        private void OnConnectFailOrDisconnect(string address)
        {
            lock (_lock) { _connectedId = null; _connecting = false; _authenticated = false; }
            _authWatchdog?.Dispose();
            SetState("disconnected", address + " (rescanning in 3 s)");
            RetryIn(3000, StartScan);
        }

        public void getAuthenticationResult(string address, string result, string message)
        {
            if (result == "200")
            {
                _authenticated = true;
                long ms = DeviceAuthentication.instance.getAuthenticationValidityPeriod();
                SetState("auth_ok", $"valid for {ms / 1000} s");
                StartEeg();
                SBWI.sendCommand("COMMAND_PPG_START");
            }
            else
            {
                _authenticated = false;
                SetState("auth_fail", $"HTTP {result}: {message} (check developer code + internet)");
            }
        }

        public void timeUp(object obj)
        {
            _authenticated = false;
            SetState("auth_expired", "renewing authentication");
            DeviceAuthentication.instance.getAuthentication();
        }

        public void StartEeg()
        {
            if (SBWI.sendCommand("COMMAND_START")) SetState("streaming", null);
            else SetState("error", "COMMAND_START was not accepted");
        }

        public void StopEeg()
        {
            if (SBWI.sendCommand("COMMAND_STOP")) SetState("stopped", null);
        }

        public void ImpedanceCheck(bool on)
        {
            SBWI.sendCommand(on ? "COMMAND_AC_LEADOFF" : "COMMAND_DC_LEADOFF");
            SetState(on ? "impedance_check" : "streaming", null);
        }

        public void SendEvokeMarker() => SBWI.sendCommand("COMMAND_CMD_FA");

        private void OnSdkLog(string msg)
        {
            if (Environment.GetEnvironmentVariable("EEG_BRIDGE_VERBOSE") == "1")
                Console.WriteLine("[sdk] " + msg);
        }

        private static string SafeVersion()
        {
            try { return SBWI.GetVersion(); } catch { return "?"; }
        }

        private void RetryIn(int ms, Action a)
        {
            _retryTimer?.Dispose();
            _retryTimer = new Timer(_ => a(), null, ms, Timeout.Infinite);
        }

        private void SetState(string state, string detail)
        {
            State = state;
            Status?.Invoke(state, detail);
        }

        public void Dispose()
        {
            _disposed = true;
            _retryTimer?.Dispose();
            _authWatchdog?.Dispose();
            try
            {
                SBWI.sendCommand("COMMAND_STOP");
                SBWI.sendCommand("COMMAND_PPG_STOP");
                if (_connectedId != null) SBWI.disconnectBT(_connectedId);
                SBWI.shutdownSBWI();
            }
            catch (Exception e) { Console.Error.WriteLine("[bridge] shutdown: " + e.Message); }
        }
    }
}
#endif
