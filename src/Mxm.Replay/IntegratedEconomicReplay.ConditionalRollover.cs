using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    // This adapter is only reachable from the separate, explicitly
    // pre-registered conditional replay mode. It cannot alter Fresh().
    sealed record Endpoint(long At,long[] RawPrices,bool Conflict);
    sealed record RolloverSide(bool Complete,int Count,int SameTimestampConflictGroups,
        Endpoint? LastBefore,Endpoint? FirstAfter,long? AcquiredAt)
    {
        public NativeConditionalRolloverSide? Prior() =>
            LastBefore is { } b && AcquiredAt is long a &&
            b.Conflict==(b.RawPrices.Length>1) ?
            new(b.At,b.RawPrices,Complete,a):null;
    }
    sealed record RolloverWindow(string Symbol,long Rollover,Dictionary<string,RolloverSide> Sides);
    sealed record ConditionalSource(string SourceRun,string PlaintextSha256,int PriceScale,
        RolloverWindow[] Windows,bool SettlementPriceConventionCertified,
        bool HistoricalTariffContinuityCertified,bool OriginalDecisionRewritten);
    sealed class ConditionalRolloverArchive
    {
        readonly Dictionary<(string,long),RolloverWindow> windows;
        public readonly string Sha256;
        public readonly string OriginalPlaintextSha256;
        public readonly long AcquiredAt;
        public ConditionalRolloverArchive(string path)
        {
            var raw=File.ReadAllBytes(path);
            Sha256=Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant();
            var source=JsonSerializer.Deserialize<ConditionalSource>(raw,
                new JsonSerializerOptions{PropertyNameCaseInsensitive=true})
                ??throw new ArgumentException("CONDITIONAL_ROLLOVER_MISSING");
            if(source.SourceRun!="45549613144"||source.PriceScale!=100000||
                source.SettlementPriceConventionCertified||source.HistoricalTariffContinuityCertified||
                source.OriginalDecisionRewritten||source.PlaintextSha256 is not {Length:64}||
                !source.PlaintextSha256.All(Uri.IsHexDigit)||source.Windows.Length!=24||
                source.Windows.Any(w=>w.Symbol is not ("EURUSD" or "US500")||
                    w.Sides.Count!=2||!w.Sides.ContainsKey("BID")||!w.Sides.ContainsKey("ASK")))
                throw new ArgumentException("CONDITIONAL_ROLLOVER_SOURCE_BINDING");
            OriginalPlaintextSha256=source.PlaintextSha256;
            windows=source.Windows.ToDictionary(w=>(w.Symbol,w.Rollover));
            AcquiredAt=source.Windows.SelectMany(w=>w.Sides.Values).Max(x=>x.AcquiredAt??0L);
            if(AcquiredAt<=0)throw new ArgumentException("CONDITIONAL_ACQUISITION_CLOCK");
        }
        RolloverSide? Side(string symbol,long charge,string side)=>
            windows.GetValueOrDefault((symbol,charge))?.Sides.GetValueOrDefault(side);
        public NativeObservedRolloverQuote Quote(DatedEurTerms terms,int side,long charge)
        {
            var c=terms.Contract;
            var fx=c.QuoteAsset=="EUR"?new NativeOriginalFxRate(1m,1m,Array.Empty<string>()):
                c.QuoteAsset=="USD"?NativeConditionalRollover.UsdToEur(
                    Side("EURUSD",charge,"BID")?.Prior(),Side("EURUSD",charge,"ASK")?.Prior(),charge):null;
            decimal? signed=side>0?c.LongSwap:c.ShortSwap;
            decimal? market=signed.HasValue?NativeConditionalRollover.MarketBid(
                Side(c.Symbol,charge,"BID")?.Prior(),charge,signed.Value):null;
            return new(market,fx);
        }
        public string EvidenceHash(DatedEurTerms t,NativeFundingExposure x,long through,string scenario)
            =>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
                JsonSerializer.Serialize(new {Scenario=scenario,Sha256,OriginalPlaintextSha256,
                    t.Digest,x.PositionId,x.Symbol,x.Side,x.Units,x.FromExclusive,Through=through,AcquiredAt},Json))))
                .ToLowerInvariant();
    }
}
