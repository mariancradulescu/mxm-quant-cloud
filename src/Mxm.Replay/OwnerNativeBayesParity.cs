using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;
using Mxm.Cloud;

// New study command only. Frozen historical commands and results untouched.
public static class OwnerNativeBayesParity
{
    static readonly JsonSerializerOptions Options=new(){PropertyNameCaseInsensitive=true};
    static string Sha(byte[] b)=>Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();
    static void Same(NativeBayesStep replay,NativeBayesStep cloud)
    {
        const decimal tolerance=.000000001m;
        void Eq(decimal a,decimal b,string reason)
        {
            if(Math.Abs(a-b)>tolerance)throw new InvalidOperationException(
                "OWNER_NATIVE_EVENT_PARITY_DIFFERENCE_"+reason);
        }
        Eq(replay.PosteriorUp,cloud.PosteriorUp,"BAYES_MODEL");
        Eq(replay.PriorCloseChange??0,cloud.PriorCloseChange??0,"CAUSAL_FEATURE");
        Eq(replay.Stop??0,cloud.Stop??0,"STOP");
        Eq(replay.Target??0,cloud.Target??0,"TARGET");
        Eq(replay.CashEur,cloud.CashEur,"CASH");
        Eq(replay.LiquidationEquityEur??0,cloud.LiquidationEquityEur??0,"FLOATING_EQUITY");
        Eq(replay.UsedMarginEur??0,cloud.UsedMarginEur??0,"MARGIN");
        Eq(replay.FreeMarginEur??0,cloud.FreeMarginEur??0,"FREE_MARGIN");
        Eq(replay.ClosedNetEur,cloud.ClosedNetEur,"NET");
        Eq(replay.MaximumSampledDrawdown,cloud.MaximumSampledDrawdown,"SAMPLED_DD");
        if(replay.Index!=cloud.Index || replay.At!=cloud.At ||
           replay.ForecastSide!=cloud.ForecastSide ||
           replay.PositiveTransitions!=cloud.PositiveTransitions ||
           replay.NegativeTransitions!=cloud.NegativeTransitions ||
           replay.PriorCloseChange.HasValue!=cloud.PriorCloseChange.HasValue ||
           replay.OpenPositions!=cloud.OpenPositions ||
           replay.PendingIntents!=cloud.PendingIntents ||
           replay.CompleteRoundTrips!=cloud.CompleteRoundTrips ||
           replay.LiquidationEquityEur.HasValue!=cloud.LiquidationEquityEur.HasValue ||
           replay.UsedMarginEur.HasValue!=cloud.UsedMarginEur.HasValue ||
           replay.FreeMarginEur.HasValue!=cloud.FreeMarginEur.HasValue ||
           replay.Stop.HasValue!=cloud.Stop.HasValue ||
           replay.Target.HasValue!=cloud.Target.HasValue ||
           replay.Events.Length!=cloud.Events.Length ||
           replay.Events.Zip(cloud.Events).Any(x=>x.First!=x.Second) ||
           replay.LedgerEventChainHash!=cloud.LedgerEventChainHash ||
           replay.StepSha256!=cloud.StepSha256)
           throw new InvalidOperationException("OWNER_NATIVE_EVENT_PARITY_MATERIAL_TRACE_MISMATCH");
    }
    public static int Run(string input,string output)
    {
        var bytes=File.ReadAllBytes(input);
        var observations=JsonSerializer.Deserialize<NativeBayesObservation[]>(bytes,Options)
            ??throw new ArgumentException("OWNER_NATIVE_EMPTY_EVENT_TAPE");
        if(observations.Length<10||observations.Length>100000)
            throw new ArgumentException("OWNER_NATIVE_EVENT_TAPE_SIZE");
        var replay=new NativeBayesianCommonEpisode();
        var cloud=new NativeCloudResearchParityAdapter();
        var rows=new List<object>();
        decimal peakMargin=0m;
        decimal minimumEquity=300m;
        for(int i=0;i<observations.Length;i++)
        {
            var a=replay.Advance(observations[i],i);
            var b=cloud.ObserveCompletedQuote(observations[i],i);
            Same(a,b);
            peakMargin=Math.Max(peakMargin,a.UsedMarginEur??0m);
            minimumEquity=Math.Min(minimumEquity,a.LiquidationEquityEur??minimumEquity);
            rows.Add(new {Index=i,Time=a.At,
                FeatureDelta=a.PriorCloseChange,Positive=a.PositiveTransitions,
                Negative=a.NegativeTransitions,PosteriorUp=a.PosteriorUp,
                ForecastSide=a.ForecastSide,Stop=a.Stop,Target=a.Target,
                IntentAndFillFacts=a.Events,CashEur=a.CashEur,
                FloatingEquityEur=a.LiquidationEquityEur,MarginEur=a.UsedMarginEur,
                FreeMarginEur=a.FreeMarginEur,
                CompletedTrips=a.CompleteRoundTrips,ClosedNetEur=a.ClosedNetEur,
                SampledDrawdown=a.MaximumSampledDrawdown,
                LedgerEventChainSha256=a.LedgerEventChainHash,
                ReplayStepSha256=a.StepSha256,CloudAdapterStepSha256=b.StepSha256,
                MaxNumericAbsDifference=0m});
        }
        // Prove the comparison actually FAILS on a one-sided input mutation:
        // same clock, altered quote, two independent Core instances.
        var original=observations[0];
        var mutated=original with {Quote=original.Quote with {
            Ask=original.Quote.Ask+.01m}};
        var positiveControl=new NativeBayesianCommonEpisode().Advance(original,0);
        var negativeControl=new NativeCloudResearchParityAdapter()
            .ObserveCompletedQuote(mutated,0);
        bool tamperDetected=false;
        try {Same(positiveControl,negativeControl);}
        catch(InvalidOperationException){tamperDetected=true;}
        if(!tamperDetected)throw new InvalidOperationException(
            "OWNER_NATIVE_NEGATIVE_MUTATION_WAS_NOT_DETECTED");
        var last=replay.CurrentBook;
        var receipt=new {
            Protocol="OWNER_PROSPECTIVE_BAYES_TRANSITION_V1",
            OriginalInputSha256=Sha(bytes),
            SourceClass="SYNTHETIC_NO_ORIGINAL_BROKER_FILL",
            ParityClass="SAME_EVENT_REPLAY_VS_CLOUD_LINKED_SOURCE_ADAPTER_NO_RUNTIME_ACTIVATION",
            NumericToleranceEur="0.000000001",
            EventsCompared=rows.Count,MaterialMismatches=0,
            OneSidedMutationRejected=tamperDetected,
            CloudOrderActions=0,CloudActivated=false,
            NativeSharedCore=true,
            InitialOneBookCapitalEur=300m,
            FinalCashEur=last.CashEur,FinalClosedNetEur=last.ClosedNetEur,
            CompleteTrips=last.CompleteRoundTrips,
            OpenPositions=last.OpenPositions,PendingIntents=last.PendingIntents,
            PeakObservedMarginEur=peakMargin,MinimumObservedEquityEur=minimumEquity,
            MaximumSampledDrawdown=last.MaximumSampledDrawdown,
            ContinuousFloatingDrawdownCertified=false,
            Hard21SystemCertified=false,HistoricalCostsCertified=false,
            IndependentTwelveMonths=false,PositiveEconomicEdgeCertified=false,
            Steps=rows
        };
        var text=JsonSerializer.Serialize(receipt,new JsonSerializerOptions{WriteIndented=true});
        File.WriteAllText(output,text);
        Console.WriteLine("OWNER_NATIVE_BAYES_PARITY_SYNTHETIC_PASS input_sha="+Sha(bytes)+
            " events="+rows.Count+" completed="+last.CompleteRoundTrips+
            " closed_net_eur="+last.ClosedNetEur.ToString(
                System.Globalization.CultureInfo.InvariantCulture));
        return 0;
    }
}
