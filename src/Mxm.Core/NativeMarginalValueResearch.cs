using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

// MVO1 NEW original-source, chronologically updated economic thesis research.
// A position lost to stale observations NEVER frees a shared portfolio slot.
// SOURCE OHLCV is enough for closed-price information, NOT financed broker NET.
public static class NativeMarginalValueResearch
{
    private const long BarMs=900000L;
    private const decimal PriceFactor=100000m;
    private static long U(int y,int m,int d)=>new DateTimeOffset(y,m,d,0,0,0,TimeSpan.Zero).ToUnixTimeMilliseconds();
    private static readonly long TrainingEnd=U(2026,5,17),CalibrationEnd=U(2026,8,17),StudyEnd=U(2026,11,16);
    private static readonly string[] Universe={"AUDUSD","AUS200","EURUSD","GBPUSD","GER40","JPN225",
        "NAS100","UK100","US500","USDCAD","USDJPY","XAUUSD"};
    private static string ClassOf(string s)=>s=="XAUUSD"?"METAL":
        s is "EURUSD" or "GBPUSD" or "USDJPY" or "AUDUSD" or "USDCAD"?"FX":"INDEX";
    private static string Week(long t)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);
    }
    private static string Stage(long t)=>t<TrainingEnd?"DEVELOPMENT_EXPOSED":
        t<CalibrationEnd?"CHRONOLOGICAL_CALIBRATION_EXPOSED":"EVALUATION_GLOBALLY_EXPOSED";
    private sealed record Frame(string Symbol,string AssetClass,long At,
        decimal Close,decimal Open,decimal Atr,decimal Mean16,decimal Mean32,
        decimal High8,decimal Low8,decimal VolumeRatio,decimal Slow16,
        int ReleaseSide,int RepairSide,decimal ReleaseStrength,decimal RepairStrength,
        bool WarmupReady);
    private sealed record Candidate(Frame Data,string Family,int Side,decimal Strength);
    private sealed record Position(string Symbol,string AssetClass,string Family,int Side,
        long EnteredAt,long LastRealMarkAt,decimal EntryClose,decimal EntryAtr,
        decimal ExtremeClose,int ObservedBarsHeld,int GapCount,
        bool HadUnknownFloatingPath,string EntryStage);
    public sealed record ClosedPriceOnlyEpisode(string Policy,string Symbol,string AssetClass,
        string Family,int Side,long EntryAt,long ExitAt,string EntryStage,string ExitStage,
        decimal DirectionalGrossPriceOnlyBps,decimal SameClockLongBps,
        decimal SameClockShortBps,string ExitCause,int HistoricalGapCount,
        bool ContinuousIntraholdRiskUnknown);
    public sealed class StageEvidence
    {
        public string StageName {get;init;}="";
        public int RawProposals {get;set;}
        public int AcceptedModelEntrants {get;set;}
        public int BlockedAlreadyHeld {get;set;}
        public int BlockedByStalePositionMark {get;set;}
        public int BlockedByOccupiedModelSlots {get;set;}
        public int SameClockOppositeSideRejected {get;set;}
        public int CompletedModelExitDecisions {get;set;}
        public int ModelSignalExits {get;set;}
        public int SafetyTimeouts {get;set;}
        public int HeldAcrossStageBoundary {get;set;}
        public int ObservedGapReconciliations {get;set;}
        public int PeakSimultaneousPriceOnlyPositions {get;set;}
        public decimal DirectionalGrossPriceOnlyBpsSum {get;set;}
        public decimal MatchedLongBpsSum {get;set;}
        public decimal MatchedShortBpsSum {get;set;}
        public decimal? MeanPriceOnlyBps {get;set;}
        public decimal? MedianPriceOnlyBps {get;set;}
        public decimal? BreakEvenTotalRoundTripFrictionBps {get;set;}
        public Dictionary<string,int> ExitCauses {get;set;}=new(StringComparer.Ordinal);
        public Dictionary<string,int> CompletionsByAssetClass {get;set;}=new(StringComparer.Ordinal);
        public Dictionary<string,int> CompletionsByWeekPriceOnly {get;set;}=new(StringComparer.Ordinal);
    }
    private sealed record BookEvidence(string Policy,StageEvidence[] Stages,
        int TerminalUnresolvedModelPositions,
        string[] TerminalHeldSymbols,int TotalCompletedModelExitDecisions,
        int CompletedEpisodesCrossingObservationGaps,
        int OpenPositionGapOccurrences,int MaxModelSimultaneousPositions,
        ClosedPriceOnlyEpisode[] CompletedEpisodes,
        decimal? FinancialNetEur=null,decimal? CentralNetEur=null,
        decimal? AdverseNetEur=null,int? FundedCompletedRoundTrips=null,
        bool CertifiedSystemicHard21=false,bool AuthenticEur300CommonLedgerRun=false,
        decimal? ContinuousFloatingDrawdown=null);
    private static Frame[] BuildFrames(Cdh1Input data)
    {
        if(data is null || data.Streams is null || data.Streams.Length!=12 ||
           !data.Streams.Select(s=>s.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
             .SequenceEqual(Universe) ||
           data.Streams.Any(s=>s.Period!="M15"||s.Bars is null||s.Bars.Length<36))
            throw new ArgumentException("MVO1_ORIGINAL_TWELVE_SYMBOLS_M15_REQUIRED");
        var output=new List<Frame>(data.Streams.Sum(s=>s.Bars.Length));
        foreach(var s in data.Streams)
        {
            var bars=s.Bars;
            if(bars.Any(b=>b.End-b.Start!=BarMs||b.Open<=0||b.High<Math.Max(b.Open,b.Close)||
                   b.Low<=0||b.Low>Math.Min(b.Open,b.Close)||b.Volume<0)||
               bars.Zip(bars.Skip(1)).Any(p=>p.Second.Start<p.First.End))
                throw new ArgumentException("MVO1_ORIGINAL_SOURCE_BAR_GEOMETRY");
            string assetClass=ClassOf(s.Symbol);
            for(int i=0;i<bars.Length;i++)
            {
                decimal c=bars[i].Close/PriceFactor,o=bars[i].Open/PriceFactor;
                bool ready=i>=34 && Enumerable.Range(i-3,3).All(j=>bars[j].End==bars[j+1].Start);
                decimal atr=0m,mean16=0m,mean32=0m,high8=0m,low8=0m,volumeRatio=0m,slow=0m;
                int a=0,b=0;decimal ascore=0m,bscore=0m;
                if(ready)
                {
                    for(int j=i-15;j<=i;j++)
                    {
                        decimal high=bars[j].High/PriceFactor,low=bars[j].Low/PriceFactor;
                        decimal previous=bars[j-1].Close/PriceFactor;
                        atr+=Math.Max(high-low,Math.Max(Math.Abs(high-previous),Math.Abs(low-previous)));
                    }
                    atr/=16m;
                    mean16=Enumerable.Range(i-15,16).Average(j=>bars[j].Close/PriceFactor);
                    mean32=Enumerable.Range(i-31,32).Average(j=>bars[j].Close/PriceFactor);
                    high8=Enumerable.Range(i-8,8).Max(j=>bars[j].High/PriceFactor);
                    low8=Enumerable.Range(i-8,8).Min(j=>bars[j].Low/PriceFactor);
                    decimal vol=Enumerable.Range(i-16,16).Average(j=>(decimal)bars[j].Volume);
                    slow=c-bars[i-16].Close/PriceFactor;
                    if(vol>0m&&atr>0m)
                    {
                        volumeRatio=bars[i].Volume/vol;
                        decimal rangeRecent=Enumerable.Range(i-16,16).Max(j=>bars[j].High/PriceFactor)-
                            Enumerable.Range(i-16,16).Min(j=>bars[j].Low/PriceFactor);
                        decimal rangeOlder=Enumerable.Range(i-32,16).Max(j=>bars[j].High/PriceFactor)-
                            Enumerable.Range(i-32,16).Min(j=>bars[j].Low/PriceFactor);
                        bool compressed=rangeOlder>0 && rangeRecent<=.90m*rangeOlder;
                        a=compressed && volumeRatio>=1m&&slow>0&&c>high8&&c>o?1:
                            compressed && volumeRatio>=1m&&slow<0&&c<low8&&c<o?-1:0;
                        decimal lowerTail=Math.Min(o,c)-bars[i].Low/PriceFactor;
                        decimal upperTail=bars[i].High/PriceFactor-Math.Max(o,c);
                        bool calmTrend=Math.Abs(slow)<=6m*atr;
                        b=calmTrend&&volumeRatio>=.8m&&c<=mean32-1.75m*atr&&c>o&&
                            lowerTail>=.5m*Math.Abs(c-o)?1:
                            calmTrend&&volumeRatio>=.8m&&c>=mean32+1.75m*atr&&c<o&&
                            upperTail>=.5m*Math.Abs(c-o)?-1:0;
                        ascore=a!=0?Math.Min(4m,Math.Abs(c-(a==1?high8:low8))/atr):0m;
                        bscore=b!=0?Math.Min(4m,Math.Abs(c-mean32)/atr):0m;
                    }
                }
                output.Add(new Frame(s.Symbol,assetClass,bars[i].End,c,o,atr,mean16,
                    mean32,high8,low8,volumeRatio,slow,a,b,ascore,bscore,ready&&atr>0m));
            }
        }
        return output.OrderBy(x=>x.At).ThenBy(x=>x.Symbol,StringComparer.Ordinal).ToArray();
    }

    private static BookEvidence RunPolicy(string policy,Frame[] all)
    {
        var stages=new[]{"DEVELOPMENT_EXPOSED","CHRONOLOGICAL_CALIBRATION_EXPOSED",
            "EVALUATION_GLOBALLY_EXPOSED"}.ToDictionary(
                s=>s,s=>new StageEvidence{StageName=s},StringComparer.Ordinal);
        foreach(var st in stages.Values)
        {
            long first=st.StageName=="DEVELOPMENT_EXPOSED"?U(2025,11,16):
                st.StageName=="CHRONOLOGICAL_CALIBRATION_EXPOSED"?TrainingEnd:CalibrationEnd;
            long end=st.StageName=="DEVELOPMENT_EXPOSED"?TrainingEnd:
                st.StageName=="CHRONOLOGICAL_CALIBRATION_EXPOSED"?CalibrationEnd:StudyEnd;
            // Enumerate ISO week Mondays aligned to date-independent boundaries;
            // each applicable week occurs, including weeks with zero closures.
            for(long at=first;at<end;at+=BarMs*96*7)
                st.CompletionsByWeekPriceOnly.TryAdd(Week(at),0);
        }
        var positions=new Dictionary<string,Position>(StringComparer.Ordinal);
        var history=new Dictionary<string,(int Count,decimal Sum)>(StringComparer.Ordinal);
        var completed=new List<ClosedPriceOnlyEpisode>();
        int maxPositions=0,totalGaps=0,completedAfterGaps=0;
        string lastStage="DEVELOPMENT_EXPOSED";
        foreach(var clockGroup in all.GroupBy(x=>x.At))
        {
            long at=clockGroup.Key;
            if(at>=StudyEnd)break;
            string stageName=Stage(at);
            if(stageName!=lastStage)
            {
                stages[lastStage].HeldAcrossStageBoundary=positions.Count;
                lastStage=stageName;
            }
            var st=stages[stageName];
            var exited=new HashSet<string>(StringComparer.Ordinal);
            foreach(var bar in clockGroup)
            {
                if(!positions.TryGetValue(bar.Symbol,out var held))continue;
                if(at<=held.LastRealMarkAt)
                    throw new ArgumentException("MVO1_NONCHRONOLOGICAL_HELD_MARK");
                bool gap=at-held.LastRealMarkAt>BarMs;
                if(gap)
                {
                    totalGaps++;st.ObservedGapReconciliations++;
                    held=held with{GapCount=held.GapCount+1,HadUnknownFloatingPath=true};
                    // There is NOT a modeled exit, settlement or freed slot here.
                }
                var verdict=NativeCausalExitResearch.AssessMarginalPriceOnlyThesis(
                    held.Family,held.Side,held.EntryClose,held.EntryAtr,
                    held.ExtremeClose,bar.Close,bar.Mean16,bar.Mean32,
                    bar.High8,bar.Low8,bar.WarmupReady,gap,held.ObservedBarsHeld+1);
                if(!verdict.RequestClose)
                {
                    positions[bar.Symbol]=held with{LastRealMarkAt=at,
                        ObservedBarsHeld=held.ObservedBarsHeld+1,
                        ExtremeClose=verdict.FavorableExtreme};
                    continue;
                }
                decimal signed=(bar.Close/held.EntryClose-1m)*10000m;
                decimal gross=signed*held.Side;
                var trade=new ClosedPriceOnlyEpisode(policy,held.Symbol,held.AssetClass,
                    held.Family,held.Side,held.EnteredAt,at,held.EntryStage,stageName,
                    gross,signed,-signed,verdict.Reason,held.GapCount,
                    held.HadUnknownFloatingPath);
                completed.Add(trade);
                if(held.HadUnknownFloatingPath)completedAfterGaps++;
                st.CompletedModelExitDecisions++;
                if(verdict.Reason.StartsWith("SAFETY_",StringComparison.Ordinal))
                    st.SafetyTimeouts++;
                else st.ModelSignalExits++;
                st.DirectionalGrossPriceOnlyBpsSum+=gross;
                st.MatchedLongBpsSum+=signed;st.MatchedShortBpsSum-=signed;
                string week=Week(at);
                st.CompletionsByWeekPriceOnly[week]=st.CompletionsByWeekPriceOnly.GetValueOrDefault(week)+1;
                st.ExitCauses[verdict.Reason]=st.ExitCauses.GetValueOrDefault(verdict.Reason)+1;
                st.CompletionsByAssetClass[held.AssetClass]=
                    st.CompletionsByAssetClass.GetValueOrDefault(held.AssetClass)+1;
                // Strictly available AFTER this observed close, never a future label.
                string key=held.Family+"/"+held.AssetClass;
                var prior=history.GetValueOrDefault(key);
                history[key]=(prior.Count+1,prior.Sum+gross);
                positions.Remove(bar.Symbol); // ONLY an observed causal price-only exit, NOT broker settlement.
                exited.Add(bar.Symbol);
            }

            var proposals=new List<Candidate>();
            foreach(var bar in clockGroup.Where(x=>x.WarmupReady))
            {
                if(bar.ReleaseSide!=0)
                    proposals.Add(new(bar,"RANGE_RELEASE",bar.ReleaseSide,bar.ReleaseStrength));
                if(bar.RepairSide!=0)
                    proposals.Add(new(bar,"EXHAUSTION_REPAIR",bar.RepairSide,bar.RepairStrength));
            }
            st.RawProposals+=proposals.Count;
            if(proposals.Count==0)continue;

            bool markUnknown=positions.Values.Any(p=>at-p.LastRealMarkAt>BarMs);
            // No speculative free margin when any holding lacks contemporaneous valuation.
            if(markUnknown)
            {
                st.BlockedByStalePositionMark+=proposals.Count;
                continue;
            }
            var admissible=new List<Candidate>();
            foreach(var g in proposals.GroupBy(p=>p.Data.Symbol))
            {
                var sides=g.Select(p=>p.Side).Distinct().ToArray();
                if(sides.Length>1)
                {
                    st.SameClockOppositeSideRejected+=g.Count();continue;
                }
                if(positions.ContainsKey(g.Key)||exited.Contains(g.Key))
                {
                    st.BlockedAlreadyHeld+=g.Count();continue;
                }
                // Competing families on the same symbol count as one slot.
                admissible.AddRange(g);
            }
            decimal Rank(Candidate x)
            {
                var prior=history.GetValueOrDefault(x.Family+"/"+x.Data.AssetClass);
                decimal baseMean=prior.Sum/(16m+prior.Count);
                decimal uncertainty=(decimal)(8d/Math.Sqrt(16d+prior.Count));
                decimal overlap=positions.Values.Any(p=>p.AssetClass==x.Data.AssetClass &&
                    p.Side==x.Side)?2m:0m;
                return baseMean-uncertainty-overlap+.25m*Math.Min(4m,x.Strength);
            }
            IOrderedEnumerable<Candidate> ordered=policy switch
            {
                "MARGINAL_CAUSAL"=>admissible.OrderByDescending(Rank)
                    .ThenBy(c=>c.Data.Symbol,StringComparer.Ordinal)
                    .ThenBy(c=>c.Family,StringComparer.Ordinal),
                "DIVERSIFY_FIRST"=>admissible.OrderBy(c=>positions.Values
                    .Any(h=>h.AssetClass==c.Data.AssetClass)?1:0)
                    .ThenBy(c=>c.Data.Symbol,StringComparer.Ordinal)
                    .ThenBy(c=>c.Family,StringComparer.Ordinal),
                "FIRST_ADMISSIBLE"=>admissible.OrderBy(c=>c.Data.Symbol,StringComparer.Ordinal)
                    .ThenBy(c=>c.Family,StringComparer.Ordinal),
                _=>throw new ArgumentException("MVO1_UNFROZEN_COMPARATOR_POLICY")
            };
            foreach(var candidate in ordered)
            {
                if(positions.ContainsKey(candidate.Data.Symbol))
                {
                    st.BlockedAlreadyHeld++;continue;
                }
                if(positions.Count>=2)
                {
                    st.BlockedByOccupiedModelSlots++;continue;
                }
                var bar=candidate.Data;
                if(bar.Atr<=0m || !bar.WarmupReady)
                    throw new ArgumentException("MVO1_NONCAUSAL_ENTRY_CONTEXT");
                positions.Add(bar.Symbol,new(bar.Symbol,bar.AssetClass,candidate.Family,
                    candidate.Side,bar.At,bar.At,bar.Close,bar.Atr,bar.Close,0,0,
                    false,stageName));
                st.AcceptedModelEntrants++;
                maxPositions=Math.Max(maxPositions,positions.Count);
                st.PeakSimultaneousPriceOnlyPositions=Math.Max(
                    st.PeakSimultaneousPriceOnlyPositions,positions.Count);
            }
        }
        stages[lastStage].HeldAcrossStageBoundary=positions.Count;
        foreach(var st in stages.Values)
        {
            var subset=completed.Where(t=>t.ExitStage==st.StageName)
                .Select(t=>t.DirectionalGrossPriceOnlyBps).OrderBy(x=>x).ToArray();
            st.MeanPriceOnlyBps=subset.Length==0?null:subset.Average();
            st.MedianPriceOnlyBps=subset.Length==0?null:subset[subset.Length/2];
            st.BreakEvenTotalRoundTripFrictionBps=
                st.MeanPriceOnlyBps>0m?st.MeanPriceOnlyBps:null;
        }
        return new(policy,stages.Values.OrderBy(s=>s.StageName=="DEVELOPMENT_EXPOSED"?0:
            s.StageName=="CHRONOLOGICAL_CALIBRATION_EXPOSED"?1:2).ToArray(),
            positions.Count,positions.Keys.OrderBy(x=>x,StringComparer.Ordinal).ToArray(),
            completed.Count,completedAfterGaps,totalGaps,maxPositions,completed.ToArray());
    }

    public static object Evaluate(Cdh1Input input)
    {
        var frames=BuildFrames(input);
        var results=new[]{"FIRST_ADMISSIBLE","DIVERSIFY_FIRST","MARGINAL_CAUSAL"}
            .Select(mode=>RunPolicy(mode,frames)).ToArray();
        return new{
            Study="MVO1_FROZEN_PERSISTENT_CAUSAL_MARGINAL_VALUE_PRICE_ONLY",
            input.SourceRunId,input.ProtocolSha256,input.CiphertextSha256,
            SourceBars=input.Streams.Sum(s=>s.Bars.Length),
            SourceSymbols=Universe,
            SourceAssetClasses=new[]{"FX","INDEX","METAL"},
            ActualCompletedM15BarFrames=frames.Length,
            AllPriorHistoricalPeriodsGloballyExposed=true,
            ResearchModel="ONE_CONTINUOUS_PERSISTENT_POSITION_STATE_PER_POLICY_THREE_COMPARATIVE_ALTERNATIVES",
            SourceGapsNeverReleaseCapacity=true,
            NormalExit="SIGNAL_REGIME_STRUCTURAL_PROTECTION_NOT_HOLD_TIME",
            CapacityOnlyModelSlots=2,
            FinancialCapitalReferenceEur=300m,
            Results=results,
            CashPriceOnlyBps=0m,
            RealizedBrokerNetEur=(decimal?)null,AdverseEurNet=(decimal?)null,
            GenuineFundedClosedTrips=(int?)null,
            SystemicHard21Certified=false,ContinuousFloatingDrawdownEur=(decimal?)null,
            OriginalBidAskFxSwapMarginContinuityAvailable=false,
            NativeEur300FundedLedgerEvaluated=false,
            IndependentTwelveMonthsConfirmed=false,
            OrdersSubmitted=0,CloudActivated=false,EconomicQualification=false
        };
    }
}
