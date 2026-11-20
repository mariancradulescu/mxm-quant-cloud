using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

public static class NativeCompletePolicyResearch
{
    sealed record Offer(int Index, string Symbol, int Side);
    sealed record Episode(Ucp1Episode? Trip, bool Opened, bool Censored, bool FinancingUnknown);
    sealed record LabeledObservation(NativeCompleteSample Sample, decimal Scale);

    static bool MayCrossFinancing(Ucp1Episode trip, NativeObservedContractTerms contract)
    {
        if (contract.SwapTimeUtcMinute is not (>=0 and <1440) || contract.SwapPeriodHours != 24) return true;
        long phase = contract.SwapTimeUtcMinute.Value * 60_000L;
        return (trip.CloseAt - phase) / NativeCompletePolicy.Day > (trip.OpenAt - phase) / NativeCompletePolicy.Day;
    }

    static Episode Observe(Ucp1Frame[] frames, Offer offer, long cutoff, string suffix, NativeCompleteModels? models,
        Dictionary<string,NativeObservedContractTerms> contracts, bool closeAtCheckpoint = false)
    {
        var seed = new NativeCompleteProbe(offer.Symbol, offer.Side, frames[offer.Index].At, closeAtCheckpoint);
        var engine = new NativeUnifiedPortfolioEngine(NativeCompletePolicy.Probe + suffix, models: models, probe: seed);
        bool opened = false;
        for (int i = offer.Index; i < frames.Length && frames[i].At < cutoff; i++)
        {
            var frame = frames[i];
            var result = engine.Advance(frame with {
                Markets = frame.Markets.Where(m => m.Symbol == offer.Symbol).ToArray()
            });
            opened |= result.OpenFills > 0;
            if (result.ModelBook.CompleteRoundTrips > 0)
            {
                var trip = engine.CompleteModelTrips.Single();
                return new(trip, true, false, MayCrossFinancing(trip, contracts[offer.Symbol]));
            }
            if (result.Pending == 0 && result.Held == 0) return new(null, opened, false, false);
        }
        return new(null, opened, true, false);
    }

    static bool Known(Episode o) => o.Trip is not null && !o.FinancingUnknown && !o.Trip.CrossedUnknownHistory;

    static LabeledObservation? EntryLabel(Ucp1Frame[] frames, Offer offer, Episode outcome)
    {
        if (!Known(outcome) || outcome.Trip is not { Integrated.CompletePolicy: { } entry } trip) return null;
        return new(new(offer.Symbol, frames[offer.Index].At, trip.CloseAt, entry.Features, trip.NetEur / entry.ScaleEur), entry.ScaleEur);
    }

    static LabeledObservation? PairedHold(Ucp1Frame[] frames, Offer o, long cutoff, string suffix,
        Dictionary<string,NativeObservedContractTerms> contracts)
    {
        var keep = Observe(frames,o,cutoff,suffix,null,contracts);
        if (!Known(keep) || keep.Trip is not { Integrated.CompletePolicy.Hold: { } hold } trip) return null;
        var close = Observe(frames,o,cutoff,suffix,null,contracts,closeAtCheckpoint:true);
        if (!Known(close) || close.Trip is not { Integrated.CompletePolicy.Hold: { } decision } peer ||
            decision.ObservedAt != hold.ObservedAt || peer.OpenAt != trip.OpenAt ||
            !decision.CloseRequested || peer.ExitReason != "MODEL_UNTRANSMITTED_INTEGRATED_OBSERVED_HOLD_VALUE_EXIT")
            return null;
        return new(new(o.Symbol, hold.ObservedAt, Math.Max(trip.CloseAt, peer.CloseAt), hold.Features,
            (trip.NetEur - peer.NetEur) / hold.ScaleEur), hold.ScaleEur);
    }

    static object Accuracy(LabeledObservation[] rows, Func<LabeledObservation,NativeCompletePrediction?> score)
    {
        var samples = rows.Select(x => (x, p:score(x))).Where(x => x.p is not null).ToArray();
        if (samples.Length == 0) return new { Eligible=rows.Length, Evaluated=0 };
        decimal Error((LabeledObservation x, NativeCompletePrediction? p) row)
            => row.p!.Mean - row.x.Sample.OutcomeR*row.x.Scale;
        return new {
            Eligible=rows.Length, Evaluated=samples.Length,
            MeanAbsoluteErrorEur=samples.Average(x=>Math.Abs(Error(x))),
            MeanErrorEur=samples.Average(Error),
            Brier=samples.Average(x=>{
                decimal error=x.p!.PositiveProbability-(x.x.Sample.OutcomeR>0m?1m:0m);
                return error*error;
            }),
            SignAccuracy=(decimal)samples.Count(x=>(x.p!.Mean>0m)==(x.x.Sample.OutcomeR>0m))/samples.Length,
            PredictionMeanEur=samples.Average(x=>x.p!.Mean),
            ActualMeanEur=samples.Average(x=>x.x.Sample.OutcomeR*x.x.Scale),
            EmpiricalP10P90Coverage=(decimal)samples.Count(x=>x.x.Sample.OutcomeR*x.x.Scale>=x.p!.P10 &&
                x.x.Sample.OutcomeR*x.x.Scale<=x.p!.P90)/samples.Length
        };
    }

    static string Week(long at)
    {
        var t=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        return ISOWeek.GetYear(t)+"-W"+ISOWeek.GetWeekOfYear(t).ToString("00",CultureInfo.InvariantCulture);
    }

    static object Book(NativeUnifiedPortfolioEngine engine,long start,long end,
        Dictionary<string,NativeObservedContractTerms> contracts)
    {
        var s=engine.ModelSummary;
        var trips=engine.CompleteModelTrips;
        var curve=engine.CommonBookEquityPath;
        var verified=new NativeFundedLedger();
        var events=engine.OriginalModelEvents;
        foreach (var e in events) verified.Apply(e);
        if (verified.Summary()!=s) throw new InvalidOperationException("COMPLETE_POLICY_NATIVE_LEDGER_MISMATCH");
        var wins=trips.Where(x=>x.NetEur>0m).ToArray();
        var losses=trips.Where(x=>x.NetEur<0m).ToArray();
        var cost=new {
            Commission=trips.Sum(x=>x.Integrated!.CommissionsEur),
            Spread=trips.Sum(x=>x.Integrated!.SpreadEur),
            Slippage=trips.Sum(x=>x.Integrated!.SlippageEur),
            Conversion=trips.Sum(x=>x.Integrated!.ConversionEur)
        };
        decimal gross=trips.Sum(x=>x.GrossEur);
        if(Math.Abs(gross-cost.Commission-cost.Spread-cost.Slippage-cost.Conversion-s.ClosedNetEur)>.000000001m)
            throw new InvalidOperationException("COMPLETE_POLICY_COST_WATERFALL");
        var weekly=Enumerable.Range(0,4).Select(i=>{
            string week=Week(start+i*NativeCompletePolicy.Week);
            var subset=trips.Where(x=>Week(x.CloseAt)==week).ToArray();
            return new {Week=week,Trades=subset.Length,NetEur=subset.Sum(x=>x.NetEur),
                EquityEur=curve.LastOrDefault(x=>Week(x.At)==week&&x.EquityEur is not null)?.EquityEur,Hard21=subset.Length>=21};
        }).ToArray();
        var risk=trips.Select(x=>x.R!.Value).OrderBy(x=>x).ToArray();
        var delays=events.Where(x=>x.Kind=="REQUEST_CLOSE").GroupBy(x=>x.PositionId)
            .ToDictionary(g=>g.Key,g=>g.Last().At,StringComparer.Ordinal);
        var summary=new {
            StartCapitalEur=300m,s.CashEur,s.LiquidationEquityEur,s.ObservedPeakEur,s.MaximumSampledDrawdown,
            s.OpenPositions,s.PendingIntents,s.ClosedNetEur, GrossEur=gross,TotalCostsEur=gross-s.ClosedNetEur,
            Costs=cost,s.CompleteRoundTrips,s.EventChainHash,
            OrdersAdmitted=events.Count(x=>x.Kind=="REQUEST_OPEN"),
            Opened=events.Count(x=>x.Kind=="OPEN_FILL"),
            ExpiredBeforeFill=events.Count(x=>x.Kind=="MODEL_OPEN_INTENT_EXPIRED"),
            ProfitFactor=losses.Length==0?(decimal?)null:wins.Sum(x=>x.NetEur)/-losses.Sum(x=>x.NetEur),
            WinRate=trips.Length==0?(decimal?)null:(decimal)wins.Length/trips.Length,
            ExpectancyEur=trips.Length==0?(decimal?)null:trips.Average(x=>x.NetEur),
            AverageWinEur=wins.Length==0?(decimal?)null:wins.Average(x=>x.NetEur),
            AverageLossEur=losses.Length==0?(decimal?)null:losses.Average(x=>x.NetEur),
            RealizedPayoff=wins.Length==0||losses.Length==0?(decimal?)null:wins.Average(x=>x.NetEur)/-losses.Average(x=>x.NetEur),
            PlannedRewardToRisk=trips.Length==0?(decimal?)null:trips.Average(x=>x.Integrated!.PlannedRewardToRisk),
            MeanR=risk.Length==0?(decimal?)null:risk.Average(),
            P05R=risk.Length==0?(decimal?)null:risk[(int)Math.Floor((risk.Length-1)*.05)],
            WorstR=risk.Length==0?(decimal?)null:risk[0],
            WorstNetEur=trips.Length==0?(decimal?)null:trips.Min(x=>x.NetEur),
            MeanMfeEur=trips.Length==0?(decimal?)null:trips.Average(x=>x.SampledMfeEur),
            MeanMaeEur=trips.Length==0?(decimal?)null:trips.Average(x=>x.SampledMaeEur),
            StopRiskOverruns=trips.Count(x=>x.NetEur < -x.EntryRiskEur),
            StressOverruns=trips.Count(x=>x.NetEur < -x.Integrated!.Thesis!.StressedRiskAtFillEur),
            IncompletePathTrips=trips.Count(x=>x.CrossedUnknownHistory),
            HeldUnknownEquityClocks=curve.Count(x=>x.Held>0&&x.EquityEur is null),
            RolloverWithoutPricedHistoricalFinance=trips.Count(x=>MayCrossFinancing(x,contracts[x.Symbol])),
            MaxMarginEur=curve.Max(x=>x.UsedMarginEur),
            MaxStressedRiskEur=curve.Max(x=>x.PlannedAggregateRiskEur),
            MaxConcurrent=curve.Max(x=>x.Held),
            MinimumObservedEquityEur=curve.Min(x=>x.EquityEur),
            HeldValuedCheckpoints=trips.Count(x=>x.Integrated!.CompletePolicy!.Hold?.EstimatedContinueEur is not null),
            ValuedCheckpointExits=trips.Count(x=>x.ExitReason=="MODEL_UNTRANSMITTED_INTEGRATED_OBSERVED_HOLD_VALUE_EXIT"),
            ExitExecutionDelaysMs=trips.GroupBy(x=>x.CloseAt-delays[x.PositionId]).ToDictionary(x=>x.Key,x=>x.Count()),
            ExitReasons=trips.GroupBy(x=>x.ExitReason).ToDictionary(x=>x.Key,x=>x.Count()),
            BySymbol=trips.GroupBy(x=>x.Symbol).ToDictionary(x=>x.Key,x=>new {Trades=x.Count(),NetEur=x.Sum(y=>y.NetEur)}),
            Weekly=weekly,Hard21Weeks=weekly.Count(x=>x.Hard21)
        };
        return new { Summary=summary,StandardOutcome=engine.OriginalOutcomeReport(start,start,start,end,
            "COMPLETE_POLICY_SOURCE_BOUND_IN_RUN_RECEIPT",includeTrace:false),
            Trips=trips,NonMarkEvents=events.Where(e=>e.Kind!="MARK"),
            SampledEquity=curve,LedgerReconciled=true };
    }

    public static object Run(Ucp1Frame[] frames, long start, long end,
        Dictionary<string,NativeObservedContractTerms> contracts)
    {
        long week=NativeCompletePolicy.Week, day=NativeCompletePolicy.Day;
        if(end-start!=12*week) throw new ArgumentException("COMPLETE_POLICY_FOLD_GEOMETRY");
        var featureStream=new NativeQuoteResidenceStream();
        for(int i=0;i<frames.Length;i++) frames[i]=featureStream.Observe(frames[i]);
        var offers=frames.SelectMany((f,i)=>NativeCompletePolicy.IsDecision(f.At)
                ? f.Markets.SelectMany(m=>NativeCompletePolicy.Describe(m,f.At).Select(s=>new Offer(i,m.Symbol,s.Side)))
                : Enumerable.Empty<Offer>()).ToArray();
        Offer[] Fold(long lo,long hi)=>offers.Where(o=>frames[o.Index].At>=lo&&frames[o.Index].At<hi).ToArray();
        long holdCut=start+2*week, trainCut=start+6*week, calCut=start+8*week;
        var holdOffers=Fold(start,holdCut);
        var fitOffers=Fold(holdCut+day,trainCut);
        var calibrationOffers=Fold(trainCut+day,calCut);
        var finalOffers=Fold(calCut+day,end);

        object Scenario(string suffix)
        {
            LabeledObservation[] Holds(Offer[] stream,long until)
                =>stream.Select(x=>PairedHold(frames,x,until,suffix,contracts)).OfType<LabeledObservation>().ToArray();
            var holdLabels=Holds(holdOffers,holdCut);
            var holding=new NativeCompleteDistribution(holdLabels.Select(x=>x.Sample).ToArray(),false);
            var heldModel=new NativeCompleteModels(holdCut,holding);
            (LabeledObservation[] labels, object counts) Label(Offer[] stream,long until)
            {
                var settlements=stream.Select(o=>(offer:o,episode:Observe(frames,o,until,suffix,heldModel,contracts))).ToArray();
                return (settlements.Select(x=>EntryLabel(frames,x.offer,x.episode)).OfType<LabeledObservation>().ToArray(),
                    new {Opportunities=stream.Length,Opened=settlements.Count(x=>x.episode.Opened),
                        Unfilled=settlements.Count(x=>!x.episode.Opened),RightCensored=settlements.Count(x=>x.episode.Censored),
                        UnknownPath=settlements.Count(x=>x.episode.Trip?.CrossedUnknownHistory==true),
                        UnpricedFinance=settlements.Count(x=>x.episode.FinancingUnknown),
                        Closed=settlements.Count(x=>x.episode.Trip is not null)});
            }
            var training=Label(fitOffers,trainCut);
            var calibration=Label(calibrationOffers,calCut);
            var evaluation=Label(finalOffers,end);
            var train=training.labels.Select(x=>x.Sample).ToArray();
            var cal=calibration.labels.Select(x=>x.Sample).ToArray();
            var entry=new NativeCompleteDistribution(train,false).Calibrate(cal);
            var ablated=new NativeCompleteDistribution(train,true).Calibrate(cal);
            var models=new NativeCompleteModels(calCut,holding,entry,ablated);
            var results=new Dictionary<string,object>(StringComparer.Ordinal);
            var totals=new Dictionary<string,decimal>(StringComparer.Ordinal);
            foreach(var variant in NativeCompletePolicy.Variants)
            {
                var engine=new NativeUnifiedPortfolioEngine(NativeCompletePolicy.Prefix+variant+suffix,models:models);
                foreach(var f in frames.Where(x=>x.At>=calCut+day)) engine.Advance(f);
                totals[variant]=engine.ModelSummary.ClosedNetEur;
                results[variant]=Book(engine,calCut,end,contracts);
            }
            var controls=new[]{"CASH","FIRST","RANDOM","LONG","SHORT","ABLATION"};
            var incremental=totals.ToDictionary(x=>x.Key,x=>controls.ToDictionary(c=>c,c=>x.Value-totals[c]));
            var heldEvaluation=Holds(finalOffers,end);
            var comparable=evaluation.labels.Where(x=>entry.Predict(x.Sample.Features,x.Sample.DecisionAt,x.Scale) is not null &&
                ablated.Predict(x.Sample.Features,x.Sample.DecisionAt,x.Scale) is not null).ToArray();
            var fitValues=train.Select(x=>x.OutcomeR).OrderBy(x=>x).ToArray();
            NativeCompletePrediction? Pooled(LabeledObservation row)
                =>fitValues.Length==0?null:new(fitValues.Average()*row.Scale,fitValues.Average()*row.Scale,
                    (decimal)fitValues.Count(v=>v>0m)/fitValues.Length,fitValues[(int)(.1*(fitValues.Length-1))]*row.Scale,
                    fitValues[fitValues.Length/2]*row.Scale,fitValues[(int)(.9*(fitValues.Length-1))]*row.Scale,
                    fitValues.Length,train.Select(x=>x.DecisionAt/day).Distinct().Count());
            return new { HoldTrainingOffers=holdOffers.Length, HoldPairedTrainingLabels=holdLabels.Length,
                EntryTraining=training.counts, EntryTrainingLabels=train.Length, Calibration=calibration.counts,
                CalibrationLabels=cal.Length, Evaluation=evaluation.counts, EntryEvaluationLabels=evaluation.labels.Length,
                HoldEvaluation=Accuracy(heldEvaluation,x=>holding.Predict(x.Sample.Features,x.Sample.DecisionAt,x.Scale)),
                RankEvaluation=Accuracy(comparable,x=>entry.Predict(x.Sample.Features,x.Sample.DecisionAt,x.Scale)),
                AblationEvaluation=Accuracy(comparable,x=>ablated.Predict(x.Sample.Features,x.Sample.DecisionAt,x.Scale)),
                PooledEvaluation=Accuracy(comparable,Pooled), IncrementalEur=incremental,
                Policies=results, FrozenObservationModel=models };
        }

        var evaluated=new[]{"CENTRAL","ADVERSE"}.AsParallel().AsOrdered().WithDegreeOfParallelism(2)
            .Select(x=>(Name:x,Result:Scenario(x=="ADVERSE"?"_ADVERSE":""))).ToArray();
        return new { Start=start,End=end,HoldCut=holdCut,TrainCut=trainCut,CalibrationCut=calCut,
            EvaluationBegins=calCut+day, EmbargoMs=day,
            Observations=frames.Length, ObservedMarkets=frames.Count(x=>x.Markets.Length>0),
            Scenarios=evaluated.ToDictionary(x=>x.Name,x=>x.Result),
            SourceGloballyExposed=true,Qualification=false,BrokerNetCertified=false,
            ContinuousDrawdownCertified=false,OrdersSubmitted=0,CloudActivated=false };
    }
}
