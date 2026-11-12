using System.Security.Cryptography;
using System.Text.Json;

namespace Mxm.Core;

// Preregistered development profile shared by the replay and the observation-only cBot.
public static class NativeIntegratedResearch
{
    public static readonly long Boundary=new DateTimeOffset(2026,8,17,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    public const string Universe="AUDUSD,NZDUSD,Copper,Aluminium";
    public static string? Family(string name)=>name switch
    {
        "AUDUSD" or "NZDUSD"=>"FX",
        "Copper" or "Aluminium"=>"METAL",
        _=>null
    };
    public static bool IsSlot(long at)=>at/60000%1440 is 480 or 510 or 840 or 870;
    public static int Holding(string name)=>Family(name)=="FX"?45:60;
    public static string Exit(string name)=>Family(name)=="FX"?
        NativeCausalExitResearch.Chandelier:NativeCausalExitResearch.EquilibriumReversion;

    public static int Direction(NativeProductMarket market,NativeProductMarket[] markets)
    {
        if(Family(market.Symbol)=="FX")
        {
            var peer=markets.FirstOrDefault(x=>x.Symbol==(market.Symbol=="AUDUSD"?"NZDUSD":"AUDUSD"));
            if(peer is null || market.M15.Length<4 || peer.M15.Length<4)return 0;
            var own=market.M15.TakeLast(4).ToArray();
            var other=peer.M15.TakeLast(4).ToArray();
            if(!own.Zip(other,(a,b)=>a.CloseAt==b.CloseAt).All(x=>x) ||
               !own.Zip(own.Skip(1),(a,b)=>a.CloseAt==b.OpenAt).All(x=>x))return 0;
            decimal a=own[^1].Close/own[0].Open-1m,b=other[^1].Close/other[0].Open-1m;
            // Relative leadership in a common FX move. Both legs are
            // separately priced and can be declined by the shared allocator.
            return a*b>0m?Math.Sign(a-b):0;
        }
        if(Family(market.Symbol)!="METAL" || market.M5.Length<7)return 0;
        var bars=market.M5.TakeLast(7).ToArray();
        if(!bars.Zip(bars.Skip(1),(a,b)=>a.CloseAt==b.OpenAt).All(x=>x))return 0;
        var last=bars[^1];
        decimal typicalActivity=bars.Take(6).Average(x=>(decimal)x.TickVolume);
        decimal typicalBody=bars.Take(6).Average(x=>Math.Abs(x.Close-x.Open));
        // Sparse quote updates accompanying unusually large displacement
        // suggest temporary impact. Forecast a partial reversal.
        return typicalActivity>0m && last.TickVolume>0 &&
            last.TickVolume<typicalActivity && Math.Abs(last.Close-last.Open)>typicalBody?
            -Math.Sign(last.Close-last.Open):0;
    }
}

public sealed record NativeIntegratedSnapshot(long Boundary,NativeEntryForecast? Fx,NativeEntryForecast? Metal)
{
    public string Seal()
    {
        byte[] payload=JsonSerializer.SerializeToUtf8Bytes(this);
        return Convert.ToHexString(SHA256.HashData(payload))+"."+Convert.ToBase64String(payload);
    }
    public static NativeIntegratedSnapshot Open(string envelope)
    {
        var parts=envelope.Split('.');
        if(parts.Length!=2 || envelope.Length>10000)throw new ArgumentException("INTEGRATED_MODEL_ENVELOPE");
        byte[] payload=Convert.FromBase64String(parts[1]);
        if(!Convert.ToHexString(SHA256.HashData(payload)).Equals(parts[0],StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("INTEGRATED_MODEL_DIGEST");
        var model=JsonSerializer.Deserialize<NativeIntegratedSnapshot>(payload)
            ??throw new ArgumentException("INTEGRATED_MODEL_EMPTY");
        if(model.Boundary<=0 || new[]{model.Fx,model.Metal}.Any(f=>f is not null &&
            (f.OutcomesKnownThrough>=model.Boundary || f.TrainingDays<4 ||
             f.PositiveGrossProbability is <0m or >1m || f.StandaloneAdverseNetReturn is null ||
             f.IncrementalAdverseNetReturn is null || f.MeanUncertaintyReturn<0m)))
            throw new ArgumentException("INTEGRATED_MODEL_CAUSAL_BOUNDARY");
        return model;
    }
}

public sealed record NativeIntegratedWeek(int QuoteComplete,int FeatureEligible,int PredictionReady,int NetSupported);

public sealed record NativeIntegratedFamilyDiagnostics(int Pairs,decimal GrossBps,decimal CentralNetBps,
    decimal AdverseNetBps,decimal ReverseAdverseNetBps,int PositiveAdversePairs,decimal? Brier);
