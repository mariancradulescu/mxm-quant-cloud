using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using cAlgo.API;
using cAlgo.API.Internals;
using Mxm.Cloud;
using Mxm.Core;

namespace cAlgo.Robots;

public partial class MxmCloud
{
    [Parameter("EUR research policy (NO ORDERS)",DefaultValue="")]
    public string EurResearchPolicy {get;set;}="";
    [Parameter("EUR research first clock UTC",DefaultValue="")]
    public string EurResearchStartUtc {get;set;}="";
    [Parameter("EUR calibration checkpoint JSON",DefaultValue="")]
    public string EurCalibrationJson {get;set;}="";
    [Parameter("EUR calibration SHA-256",DefaultValue="")]
    public string EurCalibrationSha256 {get;set;}="";
    [Parameter("Official EUR funding intervals JSON",DefaultValue="")]
    public string EurFundingIntervalsJson {get;set;}="";
    [Parameter("Official EUR funding intervals SHA-256",DefaultValue="")]
    public string EurFundingIntervalsSha256 {get;set;}="";
    [Parameter("EUR research recovery checkpoint",DefaultValue="")]
    public string EurResearchRecovery {get;set;}="";

    const long EurNativeStep=300_000L;
    const long EurNativeOffset=15_000L;
    const string EurRuntimeStorage="mxm-eur-runtime-v1";
    NativeUnifiedCloudParityAdapter? _eurPolicy;
    long _eurFirstClock,_eurLastSlot;
    string _eurEpoch="";
    string? _eurUnsaved;
    int _eurLastClosed=-1;
    EurNoChargeInterval[] _eurFunding=Array.Empty<EurNoChargeInterval>();
    readonly Dictionary<string,string> _eurClasses=new(StringComparer.Ordinal);

    sealed record EurRecovery(string Epoch,string Engine);
    sealed record EurNoChargeInterval(string Symbol,string AccountBinding,long From,long Through,long AvailableAt,
        string SourceSha256,string? OfficialAssetClass,bool? ShortAllowed);
    sealed record EurNativeMark(NativeObservedContractTerms Terms,long QuoteAt,decimal Bid,decimal Ask,
        NativeEurMarginObservation[] Margin,NativeOriginalFxHop[] QuoteRoute,NativeOriginalFxHop[]? UsdRoute,
        NativeOriginalFxHop[]? FeeRoute);

    static string EurHash(string text)
        =>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();
    static bool EurHashFormat(string s)=>s is {Length:64}&&s.All(Uri.IsHexDigit);

    static T EurVerifiedJson<T>(string json,string digest)
        =>EurHashFormat(digest)&&string.Equals(EurHash(json),digest,StringComparison.OrdinalIgnoreCase)
           ?JsonSerializer.Deserialize<T>(json)??throw new ArgumentException("EUR_CHECKED_JSON_EMPTY")
           :throw new ArgumentException("EUR_CHECKED_JSON_DIGEST");

    static string PackEurRecovery(EurRecovery state)
    {
        using var output=new MemoryStream();
        using(var zip=new GZipStream(output,CompressionLevel.Fastest,leaveOpen:true))
            JsonSerializer.Serialize(zip,state);
        return Convert.ToBase64String(output.ToArray());
    }

    static EurRecovery UnpackEurRecovery(string data)
    {
        using var input=new MemoryStream(Convert.FromBase64String(data));
        using var zip=new GZipStream(input,CompressionMode.Decompress);
        return JsonSerializer.Deserialize<EurRecovery>(zip)??throw new ArgumentException("EUR_RECOVERY_INVALID");
    }

    void StartEurPolicy()
    {
        try
        {
            string mode=EurResearchPolicy.Trim();
            if(mode is not (NativeUnifiedPortfolioEngine.EurFirst or NativeUnifiedPortfolioEngine.EurRank or
                    NativeUnifiedPortfolioEngine.EurContextRank or NativeUnifiedPortfolioEngine.EurGeneralProbe or
                    NativeUnifiedPortfolioEngine.EurGeneralSelect or NativeUnifiedPortfolioEngine.EurGeneralPooled or
                    NativeUnifiedPortfolioEngine.EurGeneralCash))
                throw new ArgumentException("EUR_RUNTIME_POLICY");
            if(Account.Asset.Name!="EUR")throw new ArgumentException("EUR_RUNTIME_ACCOUNT_CURRENCY");
            if(!DateTimeOffset.TryParseExact(EurResearchStartUtc,"yyyy-MM-dd'T'HH:mm:ss'Z'",
                CultureInfo.InvariantCulture,DateTimeStyles.AssumeUniversal,out var start))
                throw new ArgumentException("EUR_RUNTIME_START_CLOCK");
            _eurFirstClock=start.ToUnixTimeMilliseconds();
            if(_eurFirstClock<=0||_eurFirstClock%EurNativeStep!=EurNativeOffset)
                throw new ArgumentException("EUR_RUNTIME_GRID");
            long now=Stamp(Server.TimeInUtc);
            NativeEurCalibration? calibration=null;
            if(mode is NativeUnifiedPortfolioEngine.EurRank or NativeUnifiedPortfolioEngine.EurContextRank or
                NativeUnifiedPortfolioEngine.EurGeneralSelect or NativeUnifiedPortfolioEngine.EurGeneralPooled)
            {
                calibration=EurVerifiedJson<NativeEurCalibration>(EurCalibrationJson,EurCalibrationSha256);
                if(calibration.ObservationThrough>=_eurFirstClock)
                    throw new ArgumentException("EUR_RUNTIME_FUTURE_CALIBRATION");
                foreach(var g in calibration.Outcomes.Select(x=>x.Context).OfType<NativeEurDecisionContext>()
                    .GroupBy(x=>x.Symbol,StringComparer.Ordinal))
                {
                    var classes=g.Select(x=>x.AssetClass).OfType<string>().Distinct().Take(2).ToArray();
                    if(classes.Length==1)_eurClasses[g.Key]=classes[0];
                }
            }
            if(!string.IsNullOrWhiteSpace(EurFundingIntervalsJson))
            {
                _eurFunding=EurVerifiedJson<EurNoChargeInterval[]>(EurFundingIntervalsJson,EurFundingIntervalsSha256);
                if(_eurFunding.Any(x=>x.AccountBinding!=_accountBinding||x.Through<=x.From||
                    x.AvailableAt<=0 || !EurHashFormat(x.SourceSha256)))
                    throw new ArgumentException("EUR_RUNTIME_FUNDING_BINDING");
                foreach(var x in _eurFunding.Where(x=>x.AvailableAt<=now&&x.OfficialAssetClass is not null))
                    _eurClasses[x.Symbol]=x.OfficialAssetClass!;
            }

            _eurEpoch=EurHash(_accountBinding+"|"+mode+"|"+_eurFirstClock+"|"+EurCalibrationSha256.Trim().ToLowerInvariant());
            // cTrader Cloud keeps LocalStorage only for the current run.
            // Preserve the epoch requirement if there is no recoverable snapshot.
            string? storage=null;
            try {storage=LocalStorage.GetString(EurRuntimeStorage,LocalStorageScope.Instance);}
            catch(LocalStorageException) { }
            var adapter=new NativeUnifiedCloudParityAdapter(mode,_accountBinding);
            var recoveries=new[]{storage,EurResearchRecovery}.Where(x=>!string.IsNullOrWhiteSpace(x))
                .Distinct(StringComparer.Ordinal).Select(x=>
                {
                    var saved=UnpackEurRecovery(x!);
                    var state=JsonSerializer.Deserialize<Ucp1Checkpoint>(saved.Engine);
                    if(saved.Epoch!=_eurEpoch||state is null||state.BrokerBinding!=_accountBinding||
                        state.Policy!=mode||state.LastAt>=now||state.LastAt<_eurFirstClock||
                        state.EurCalibration?.LedgerEventChainSha256!=calibration?.LedgerEventChainSha256)
                        throw new ArgumentException("EUR_RUNTIME_RECOVERY_BINDING");
                    return (Saved:saved,State:state);
                }).OrderByDescending(x=>x.State.LastAt).ToArray();
            if(recoveries.Length>0)
            {
                if(recoveries.Length>1&&recoveries[0].State.LastAt==recoveries[1].State.LastAt&&
                    recoveries[0].Saved.Engine!=recoveries[1].Saved.Engine)
                    throw new ArgumentException("EUR_RUNTIME_RECOVERY_CONFLICT");
                adapter.Restore(recoveries[0].Saved.Engine);
                _eurLastSlot=NativeClosedMarketContext.LatestClock(adapter.LastObservationAt,EurNativeStep,EurNativeOffset);
            }
            else
            {
                if(now>_eurFirstClock)throw new ArgumentException("EUR_RUNTIME_CHECKPOINT_REQUIRED_NO_CASH_RESET");
                if(calibration is not null)adapter.LoadEurCalibration(calibration);
            }
            _eurPolicy=adapter;
            Print("MXM EUR observation mode {0}; official no-charge intervals {1}.",
                mode,_eurFunding.Length);
        }
        catch(ArgumentException error) when(error.Message.StartsWith("EUR_RUNTIME_",StringComparison.Ordinal)||
            error.Message.StartsWith("EUR_CHECKED_JSON_",StringComparison.Ordinal))
        {
            _eurPolicy=null;
            Print("MXM EUR observation inactive. {0}",error.Message);
        }
        catch(Exception)
        {
            _eurPolicy=null;
            Print("MXM EUR observation inactive. Checkpoint, calibration or epoch could not be established.");
        }
    }

    static NativeObservedContractTerms? ReadNativeContract(Symbol market,long at)
    {
        int feeType=(int)market.CommissionType+1;
        if(feeType is <1 or >4)return null;
        int pipPosition=0;
        decimal pip=(decimal)market.PipSize;
        while(pip>0m&&pip<1m&&pipPosition<18){pip*=10m;pipPosition++;}
        if(pip!=1m)return null;
        string minimumAsset=market.MinCommissionType==SymbolMinCommissionType.QuoteAsset
            ?market.QuoteAsset.Name:market.MinCommissionAsset?.Name??"";
        int? triple=market.Swap3DaysRollover is DayOfWeek weekday?weekday==DayOfWeek.Sunday?7:(int)weekday:null;
        int? swapType=market.SwapCalculationType switch
        {
            SymbolSwapCalculationType.Pips=>0,
            SymbolSwapCalculationType.Percentage=>1,
            _=>null
        };
        return new(market.Name,market.QuoteAsset.Name,at,(decimal)market.VolumeInUnitsMin,
            (decimal)market.VolumeInUnitsStep,(decimal)market.VolumeInUnitsMax,(decimal)market.LotSize,
            feeType,checked((long)decimal.Round((decimal)market.Commission*(feeType==3?100_000m:100_000_000m))),
            (int)market.MinCommissionType+1,checked((long)decimal.Round((decimal)market.MinCommission*100_000_000m)),
            minimumAsset,checked((int)Math.Round(market.PnLConversionFeeRate*10_000d)),
            swapType,(decimal)market.SwapLong,(decimal)market.SwapShort,pipPosition,
            null,null,triple,null,null,false,false);
    }

    NativeOriginalFxHop? ReadNativeEurHop(string a,string b,long at)
    {
        foreach(string name in new[]{a+b,b+a})
        {
            if(!Symbols.Exists(name))continue;
            var symbol=Symbols.GetSymbol(name);
            string currentBase=symbol.BaseAsset.Name,quote=symbol.QuoteAsset.Name;
            if(((currentBase==a&&quote==b)||(currentBase==b&&quote==a))&&ReadTickAsOf(name,at) is { } tick)
                return new(name,currentBase,quote,tick.At,tick.Bid,tick.Ask,false);
        }
        return null;
    }

    NativeOriginalFxHop[]? ReadNativeEurRoute(string asset,long at)
    {
        if(asset=="EUR")return Array.Empty<NativeOriginalFxHop>();
        if(ReadNativeEurHop(asset,"EUR",at) is { } direct)return new[]{direct};
        return asset!="USD"&&ReadNativeEurHop(asset,"USD",at) is { } first&&
            ReadNativeEurHop("USD","EUR",at) is { } second?new[]{first,second}:null;
    }

    EurNativeMark? ReadNativeEurMark(string name)
    {
        if(!Symbols.Exists(name))return null;
        var symbol=Symbols.GetSymbol(name);
        if(!symbol.MarketHours.IsOpened())return null;
        long time=Stamp(Server.TimeInUtc);
        if(ReadNativeContract(symbol,time) is not {MinimumUnits:>0m,VolumeStepUnits:>0m} terms||
            ReadTickAsOf(name,time) is not { } quote||
            ReadNativeEurRoute(terms.QuoteAsset,time) is not { } route)return null;
        var usd=ReadNativeEurRoute("USD",time);
        var fee=terms.MinimumCommissionAsset is {Length:>0} asset?ReadNativeEurRoute(asset,time):null;
        var volumes=new[]{terms.MinimumUnits,2m*terms.MinimumUnits}.Where(v=>v<=terms.MaximumUnits&&
            (v-terms.MinimumUnits)%terms.VolumeStepUnits==0m);
        var margins=new List<NativeEurMarginObservation>();
        foreach(decimal units in volumes)
        foreach(int side in new[]{1,-1})
        {
            var margin=(decimal)symbol.GetEstimatedMargin(side>0?TradeType.Buy:TradeType.Sell,(double)units);
            long sampled=Stamp(Server.TimeInUtc);
            if(margin<=0m)continue;
            var hash=EurHash(JsonSerializer.Serialize(new {name,time,sampled,side,units,margin}));
            margins.Add(new(side,units,margin,sampled,hash));
        }
        if(margins.Count==0)return null;
        return new(terms,quote.At,quote.Bid,quote.Ask,margins.ToArray(),route,usd,fee);
    }

    EurNoChargeInterval? EurNoCharge(string symbol,long from,long through,long at)
        =>_eurFunding.FirstOrDefault(x=>x.Symbol==symbol&&x.From<=from&&x.Through>=through&&x.AvailableAt<=at);

    Ucp1MarketFrame? BuildNativeEurFrame(EurNativeMark mark,long at)
    {
        var c=mark.Terms;
        if(at<mark.QuoteAt||at-mark.QuoteAt>30_000L || mark.Margin.Any(x=>x.ObservedAt>at))return null;
        NativeOriginalFxRate Rate(string asset,NativeOriginalFxHop[] route)
            =>NativeBrokerContractCosts.ComposeCurrentAlgoQuoteToEur(asset,at,route);
        var fx=Rate(c.QuoteAsset,mark.QuoteRoute);
        decimal minimumMargin=mark.Margin.Max(x=>x.MarginEur/x.Units)*c.MinimumUnits;
        decimal usd=mark.UsdRoute is { } usdRoute?Rate("USD",usdRoute).DebitToEur:0m;
        decimal? fee=mark.FeeRoute is { } feeRoute?Rate(c.MinimumCommissionAsset!,feeRoute).DebitToEur:null;
        var quote=NativeBrokerContractCosts.QuoteCurrentAlgoBothDirections(c,new(at,mark.Bid,mark.Ask,
            fx.CreditToEur,fx.DebitToEur,usd,fee,minimumMargin,c.MinimumUnits,0m)).Quote;
        var closed=ReadClosedMarketBars(c.Symbol,at,mark.QuoteAt,eurDecision:true);
        var symbol=Symbols.GetSymbol(c.Symbol);
        long next=at+EurNativeStep+EurNativeOffset;
        var proof=EurNoCharge(c.Symbol,at,next,at);
        var executable=symbol.IsTradingEnabled&&symbol.TradingMode==SymbolTradingMode.FullAccess
            ?mark.Margin.Where(m=>m.Side>0||proof?.ShortAllowed is true).ToArray():Array.Empty<NativeEurMarginObservation>();
        var offers=proof is null?Array.Empty<NativeFundingOfferEvidence>():executable.Select(m=>
            new NativeFundingOfferEvidence(c.Symbol,m.Side,m.Units,proof.AvailableAt,proof.From,next,
                proof.Through,0m,proof.SourceSha256)).ToArray();
        return new(c.Symbol,quote,c,closed.For(NativeBarTimeframe.M5).Bars,closed.For(NativeBarTimeframe.M15).Bars,
            0m,"CTRADER_NATIVE_OBSERVATION_ONLY") {ClosedBars=closed,EurMargins=executable,FundingOffers=offers,
            OfficialAssetClass=_eurClasses.GetValueOrDefault(c.Symbol),EurNativeClock=true,
            EurTickSize=EurResearchPolicy.Trim() is NativeUnifiedPortfolioEngine.EurGeneralProbe or
                NativeUnifiedPortfolioEngine.EurGeneralSelect or NativeUnifiedPortfolioEngine.EurGeneralPooled or
                NativeUnifiedPortfolioEngine.EurGeneralCash ? (decimal)symbol.TickSize : null};
    }

    void SaveEurCheckpoint()
    {
        if(_eurUnsaved is null)return;
        LocalStorage.SetString(EurRuntimeStorage,_eurUnsaved,LocalStorageScope.Instance);
        LocalStorage.Flush(LocalStorageScope.Instance);
        _eurUnsaved=null;
    }

    void ObserveEurPolicy(string[] researched,Ucp1BrokerFrame broker)
    {
        SaveEurCheckpoint();
        var adapter=_eurPolicy!;
        long begin=Stamp(Server.TimeInUtc);
        long slot=NativeClosedMarketContext.LatestClock(begin,EurNativeStep,EurNativeOffset);
        if(slot<_eurFirstClock||slot<=_eurLastSlot)return;
        var names=adapter.ActiveSymbols.Concat(researched)
            .Concat(ReadOnlyResearchUniverse.Split(',',StringSplitOptions.RemoveEmptyEntries).Select(s=>s.Trim()))
            .Distinct(StringComparer.Ordinal);
        var raw=new List<EurNativeMark>();
        foreach(var name in names)
        {
            try {if(ReadNativeEurMark(name) is { } mark)raw.Add(mark);}
            catch(ArgumentException) { }
            catch(InvalidOperationException) { }
            catch(OverflowException) { }
        }
        long at=Stamp(Server.TimeInUtc);
        if(NativeClosedMarketContext.LatestClock(at,EurNativeStep,EurNativeOffset)!=slot||at<=adapter.LastObservationAt)return;
        var markets=new List<Ucp1MarketFrame>();
        foreach(var mark in raw)
        {
            try {if(BuildNativeEurFrame(mark,at) is { } market)markets.Add(market);}
            catch(ArgumentException) { }
            catch(InvalidOperationException) { }
        }
        var funding=new List<NativeAccruedFundingEvidence>();
        foreach(var x in adapter.FundingExposureSnapshot().Where(x=>x.ClosedAt is null||!x.ExactInLedger))
        {
            long through=x.ClosedAt??at;
            if(through>x.FromExclusive&&EurNoCharge(x.Symbol,x.FromExclusive,through,at) is { } proof)
                funding.Add(new(x.PositionId,x.Symbol,x.Side,x.Units,x.FromExclusive,through,at,0m,null,proof.SourceSha256));
        }
        var result=adapter.Observe(new(at,markets.ToArray(),broker){FundingEvidence=funding.ToArray()});
        _eurLastSlot=slot;
        _eurUnsaved=PackEurRecovery(new(_eurEpoch,adapter.Checkpoint()));
        SaveEurCheckpoint();
        if(result.ModelBook.CompleteRoundTrips!=_eurLastClosed)
        {
            _eurLastClosed=result.ModelBook.CompleteRoundTrips;
            Print("MXM EUR model {0}, closed {1}, held {2}, pending {3}, equity EUR {4}.",
                result.Policy,_eurLastClosed,result.Held,result.Pending,result.FundingCapital?.DemonstrableEquityEur);
        }
    }
}
