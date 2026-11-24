using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

// CPE1 genuine CLOSED M5/M15 SOURCE -> existing Core.Advance, no other
// economic engine, no fake BID/ASK history. All 2025-26 data are EXPOSED.
internal sealed record Cpe1SourceInput(V32Tape Tape,Rvc1OriginalFunding[] Funding);

internal static class Cpe1OriginalIntegratedRunner
{
    const long M5=300000L,M15=900000L;
    static readonly decimal[] Stress={1m,1.5m,2m};
    static readonly string[] Policies={"CPE1_ECONOMIC","CPE1_SIMPLE","CPE1_CASH"};
    static readonly JsonSerializerOptions Json=new(){
        NumberHandling=JsonNumberHandling.AllowReadingFromString,
        WriteIndented=true};
    static string Sha(string s)=>Convert.ToHexString(
        SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();

    sealed class Source
    {
        public readonly V32Market Market;
        public readonly V32Bar[] M5Bars,M15Bars;
        public readonly Dictionary<long,V32Bar> OpenM5;
        public readonly List<NativeClosedMarketBar> SeenM5=new(),SeenM15=new();
        int next5,next15;
        public Source(V32Market market)
        {
            Market=market;
            M5Bars=market.Bars.GetValueOrDefault("M5")?.OrderBy(x=>x.OpenAt).ToArray()
                ??Array.Empty<V32Bar>();
            M15Bars=market.Bars.GetValueOrDefault("M15")?.OrderBy(x=>x.OpenAt).ToArray()
                ??Array.Empty<V32Bar>();
            OpenM5=M5Bars.ToDictionary(x=>x.OpenAt);
        }
        static NativeClosedMarketBar Bar(V32Bar b,long width)
            =>new(b.OpenAt,b.OpenAt+width,b.Open,b.High,b.Low,b.Close,b.TickVolume);
        public void Advance(long t)
        {
            while(next5<M5Bars.Length && M5Bars[next5].OpenAt+M5<t)
            {
                SeenM5.Add(Bar(M5Bars[next5++],M5));
                if(SeenM5.Count>5)SeenM5.RemoveAt(0);
            }
            while(next15<M15Bars.Length && M15Bars[next15].OpenAt+M15<t)
            {
                SeenM15.Add(Bar(M15Bars[next15++],M15));
                if(SeenM15.Count>3)SeenM15.RemoveAt(0);
            }
        }
    }
    static NativeObservedContractTerms? Contract(V32Terms? t,
        IReadOnlyDictionary<string,Rvc1OriginalFunding> recovered)
    {
        if(t?.QuoteAsset!="USD" || t.MinimumUnits is not >0m ||
           t.StepUnits is not >0m || t.MaximumUnits is not >0m ||
           t.LotUnits is not >0m || t.CommissionType is null ||
           t.PreciseRateWire is null || t.MinimumCommissionType is null ||
           t.PreciseMinimumWire is null || t.PnlConversionFeeBps is null ||
           t.SpreadBps is not >0m || t.MarginMinimumEur is not >0m)
            return null;
        recovered.TryGetValue(t.Symbol,out var terms);
        bool original=terms?.OriginalBrokerAuthenticated==true &&
            terms.ObservedAtUtcMs==t.ObservedAtUtcMs;
        return new NativeObservedContractTerms(t.Symbol,t.QuoteAsset,
            t.ObservedAtUtcMs,t.MinimumUnits.Value,t.StepUnits.Value,
            t.MaximumUnits.Value,t.LotUnits.Value,t.CommissionType.Value,
            t.PreciseRateWire.Value,t.MinimumCommissionType.Value,
            t.PreciseMinimumWire.Value,t.MinimumCommissionAsset,
            t.PnlConversionFeeBps.Value,t.SwapCalculationType,
            t.LongSwap,t.ShortSwap,t.PipPosition,t.SwapPeriodHours,
            t.SwapTimeUtcMinute,t.TripleSwapWeekday,
            original?terms!.ChargeSwapAtWeekends:null,
            original?terms!.SkipSwapPeriods:null,
            true,false);
    }
    static LedgerQuote? ModeledQuote(V32Bar bar,V32Terms source,
        NativeObservedContractTerms contract,V32Bar fx,decimal multiplier,
        out decimal slippage)
    {
        slippage=0m;
        if(bar.Open<=0m || fx.Open<=0m || source.SpreadBps is not >0m ||
           source.MarginMinimumEur is not >0m)return null;
        // Conditional current-tariff/spread model, NOT historical broker bid/ask.
        decimal spread=bar.Open*source.SpreadBps.Value*multiplier/10000m;
        slippage=spread/2m;
        decimal bid=bar.Open-spread/2m,ask=bar.Open+spread/2m;
        decimal wedge=.00025m*multiplier,fxmid=1m/fx.Open;
        if(bid<=0m||fxmid<=0m||wedge>=1m)return null;
        try
        {
            decimal? assetFx=contract.MinimumCommissionAsset switch{
                null=>null,"USD"=>fxmid,"EUR"=>1m,_=>null};
            var c=NativeBrokerContractCosts.Quote(contract,
                new NativeMarketCostContext(bar.OpenAt,bid,ask,
                    fxmid*(1m-wedge),fxmid*(1m+wedge),fxmid,
                    assetFx,source.MarginMinimumEur.Value,
                    contract.MinimumUnits,slippage));
            return c.Quote with {
                ExitFeePerUnit=c.Quote.ExitFeePerUnit*multiplier,
                ExitFeeFloor=c.Quote.ExitFeeFloor*multiplier,
                LiquidationSlippagePerSide=slippage
            };
        }
        catch(ArgumentException){return null;}
        catch(InvalidOperationException){return null;}
    }

    public static int Run(string sourceFile,string outputFile,string frozenSha)
    {
        if(frozenSha.Length!=64)throw new ArgumentException("CPE1_PROTOCOL_HASH");
        var payload=JsonSerializer.Deserialize<Cpe1SourceInput>(
            File.ReadAllText(sourceFile),Json)
            ??throw new ArgumentException("CPE1_AUTHENTIC_SOURCE_NOT_DESERIALIZED");
        if(payload.Tape.DevelopmentOnly!=true ||
           payload.Tape.SourceRuns.Length!=5 ||
           payload.Tape.Markets.Length<2)
            throw new ArgumentException("CPE1_AUTHENTIC_GLOBALLY_EXPOSED_SCOPE");
        var recovered=payload.Funding.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        var sources=payload.Tape.Markets.Select(x=>new Source(x))
            .ToDictionary(x=>x.Market.Symbol,StringComparer.Ordinal);
        if(!sources.ContainsKey("EURUSD")||!sources.ContainsKey("GBPUSD"))
            throw new ArgumentException("CPE1_FX_SOURCE_IDENTITY");
        var contracts=sources.Values.Select(x=>new {
            Source=x,Contract=Contract(x.Market.Terms,recovered)})
            .Where(x=>x.Contract is not null)
            .ToDictionary(x=>x.Source.Market.Symbol,
                x=>(x.Source,x.Contract!),StringComparer.Ordinal);
        if(!contracts.ContainsKey("EURUSD")||!contracts.ContainsKey("GBPUSD"))
            throw new ArgumentException("CPE1_AUTHENTIC_BASE_FX_UNPRICED");
        var times=sources.Values.SelectMany(x=>x.M5Bars.Select(b=>b.OpenAt))
            .Distinct().OrderBy(x=>x).ToArray();
        if(times.Length<500)throw new ArgumentException("CPE1_SOURCE_TIMESTAMPS_INSUFFICIENT");
        var books=(from stress in Stress from policy in Policies
            select new {Stress=stress,Policy=policy,
                Engine=new NativeUnifiedPortfolioEngine(policy)})
            .ToArray();
        var unknownQuotes=new Dictionary<string,int>(StringComparer.Ordinal);
        var first=times[0];var last=times[^1];
        foreach(long t in times)
        {
            foreach(var source in sources.Values)source.Advance(t);
            if(!sources["EURUSD"].OpenM5.TryGetValue(t,out var conversion))
            {
                foreach(var book in books) book.Engine.Advance(new Ucp1Frame(t,Array.Empty<Ucp1MarketFrame>()));
                continue;
            }
            foreach(var multiplier in Stress)
            {
                var frames=new List<Ucp1MarketFrame>();
                foreach(var pair in contracts.OrderBy(x=>x.Key,StringComparer.Ordinal))
                {
                    var source=pair.Value.Source;
                    if(!source.OpenM5.TryGetValue(t,out var bar))continue;
                    var quote=ModeledQuote(bar,source.Market.Terms!,pair.Value.Item2,
                        conversion,multiplier,out var slip);
                    if(quote is null)
                    {
                        unknownQuotes[pair.Key]=unknownQuotes.GetValueOrDefault(pair.Key)+1;
                        continue;
                    }
                    frames.Add(new Ucp1MarketFrame(pair.Key,quote,pair.Value.Item2,
                        source.SeenM5.ToArray(),source.SeenM15.ToArray(),slip,
                        "GENUINE_CLOSED_BARS_CONDITIONAL_CURRENT_CONTRACT_M5_OPEN"));
                }
                var frame=new Ucp1Frame(t,frames.ToArray());
                foreach(var book in books.Where(x=>x.Stress==multiplier))
                    book.Engine.Advance(frame);
            }
        }
        string Week(long t)
        {
            var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
            return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);
        }
        var weeks=new HashSet<string>(StringComparer.Ordinal);
        for(var day=DateTimeOffset.FromUnixTimeMilliseconds(first).UtcDateTime.Date;
            day<=DateTimeOffset.FromUnixTimeMilliseconds(last).UtcDateTime.Date;
            day=day.AddDays(1))
            weeks.Add(Week(new DateTimeOffset(day,TimeSpan.Zero).ToUnixTimeMilliseconds()));
        var reports=books.Select(x=>{
            var trips=x.Engine.CompleteModelTrips;
            var summary=x.Engine.ModelSummary;
            bool financeKnown=trips.All(p=>p.EconomicEvidence?.ConditionalNetKnown==true);
            bool flat=summary.OpenPositions==0&&summary.PendingIntents==0;
            var gross=trips.Sum(p=>p.GrossEur);
            var nominalNet=trips.Sum(p=>p.NetEur);
            // Per-episode claims REQUIRE original contract financing to have
            // been authenticated and every roll accounted. Censored positions
            // are NOT silently marked at a future hypothetical exit.
            bool certifiedModelBook=flat&&financeKnown &&
                !summary.HistoryEvidenceIncomplete&&
                summary.LiquidationEquityEur is not null;
            var report=x.Engine.OriginalOutcomeReport(first,first+(last-first)/3,
                first+2*(last-first)/3,last,Sha(payload.Tape.ProtocolSha256),false);
            return new {
                x.Policy,x.Stress,
                SourceWeeks=weeks.Count,
                ConditionalClosedGrossEur=gross,
                ConditionalClosedNetBeforeUnknownFinancingEur=nominalNet,
                FinanciallyKnownClosedNetEur=financeKnown?(decimal?)nominalNet:null,
                NetPortfolioCertifiedEur=certifiedModelBook?(decimal?)nominalNet:null,
                Completed=trips.Length,
                GrossWinnerCount=trips.Count(p=>p.GrossEur>0m),
                ClosedUnknownFinancing=trips.Count(p=>p.EconomicEvidence?.ConditionalNetKnown!=true),
                ProjectedRewardRiskMissing=trips.Count(p=>p.EconomicEvidence is null),
                CompletedByWeek=weeks.OrderBy(w=>w,StringComparer.Ordinal)
                    .ToDictionary(w=>w,w=>trips.Count(p=>Week(p.CloseAt)==w)),
                AllEligibleWeeksHARD21=weeks.Count>0&&weeks.All(w=>
                    trips.Count(p=>Week(p.CloseAt)==w)>=21),
                CashEur=summary.CashEur,EquityEur=summary.LiquidationEquityEur,
                SampledDd=summary.MaximumSampledDrawdown,
                Held=summary.OpenPositions,Pending=summary.PendingIntents,
                summary.HistoryEvidenceIncomplete,summary.EventChainHash,
                EntryReasons=trips.GroupBy(p=>p.Family)
                    .ToDictionary(g=>g.Key,g=>g.Count()),
                ExitReasons=trips.GroupBy(p=>p.ExitReason)
                    .ToDictionary(g=>g.Key,g=>g.Count()),
                IndividualEpisodes=trips,
                ConditionalFullEngineReport=report
            };
        }).ToArray();
        var receipt=new {
            Study="CPE1_ONE_IN_EXISTING_NATIVE_UCP1_COMPLETE_CYCLE",
            FrozenProtocolSha256=frozenSha,OriginalSourceRuns=payload.Tape.SourceRuns,
            SourceAllPreviouslyExposed=true,IndependentEvaluation=false,
            GenuineM5SourceClocks=times.Length,WeeksIncludingNoTrade=weeks.Count,
            OfficialFundingRecovered=recovered.Values.Where(x=>
                x.OriginalBrokerAuthenticated&&x.ChargeSwapAtWeekends is not null&&
                x.SkipSwapPeriods is not null).Select(x=>x.Symbol).OrderBy(x=>x).ToArray(),
            UnknownCurrentCostQuotes=unknownQuotes,
            BookSummaries=reports,OrderRequests=0,CloudActivated=false,
            HistoricalExactBrokerFillsCertified=false,
            HistoricalCostContinuityCertified=false,IntrabarDdCertified=false,
            TradingQualification="DEVELOPMENT_EXPOSED_ONLY_NO_BROKER_CERTIFICATION"
        };
        File.WriteAllText(outputFile,JsonSerializer.Serialize(receipt,Json)+"\n");
        return 0;
    }
}
