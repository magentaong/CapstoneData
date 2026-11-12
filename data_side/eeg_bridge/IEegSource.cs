using System;

namespace EegBridge
{

    internal interface IEegSource : IDisposable
    {

        event Action<float[]> RawEeg200ms;

        event Action<int, int, int> HeartRate;
        event Action<bool[]> ChannelStatus;
        event Action<float[]> Impedance;

        event Action<int> Evoke;

        event Action<float[,]> BandPower;

        event Action<string, float> MentalState;

        event Action<string, bool> Flag;

        event Action<string, string> Status;

        string State { get; }

        void Begin();
        void StartEeg();
        void StopEeg();
        void ImpedanceCheck(bool on);
        void SendEvokeMarker();
    }
}
