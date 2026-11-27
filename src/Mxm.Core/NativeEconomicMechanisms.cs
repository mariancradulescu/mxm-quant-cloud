namespace Mxm.Core;

// Distinct causal hypotheses. These are development rules, not certified edges.
// Execution, funding, sizing, stops and accounting stay in the common engine.
public static class NativeEconomicMechanisms
{
    public const string Follow="M5_FOLLOW", Reverse="M5_REVERSE", Range="RANGE_CONTINUATION",
        Equilibrium="EQUILIBRIUM_REVERSION", Activity="V33_MULTISCALE_ACTIVITY",
        Intermarket="INTERMARKET_DISLOCATION", Transition="PAV1_LOCAL_TRANSITION",
        Scored="SCP1_LOCAL_LIFECYCLE";
    public static readonly string[] All={Follow,Reverse,Range,Equilibrium,Activity,Intermarket,Transition,Scored};
    public const string MonetaryReduce="MONETARY_REDUCE";
    public const string BoundaryValue="BOUNDARY_VALUE", BoundaryReduce="BOUNDARY_VALUE_REDUCE";
    public static readonly string[] Management={"BRACKET","TRANSITION_VALUE","CAPTURE_VALUE",MonetaryReduce,BoundaryValue,BoundaryReduce};

    internal static NativeCausalManagementSelection.Choice SelectManagement(IEnumerable<NativeEurCalibrationOutcome> history,
        string family,int side,NativeEurDecisionContext context,long at,int pairs,int days,decimal penalty)
        =>NativeCausalManagementSelection.Select(history,family,side,context,at,pairs,days,penalty);

    // Conditional comparison at the current executable fee schedule and
    // witnessed funding ceilings, not a promise of future settlement.
    // A partial close must outperform both HOLD and CLOSE over the same
    // continuation uncertainty interval. No extrapolation to missing volumes.
    public static decimal? PartialReductionAdvantage(decimal held, decimal close,
        decimal minimum, decimal maximum, decimal step, decimal meanEurPerUnit,
        decimal uncertaintyEurPerUnit, decimal fullDebit, decimal? remainderDebit,
        decimal fullFee, decimal closeFee, decimal remainderFee)
    {
        if(minimum<=0m||maximum<minimum||step<=0m||uncertaintyEurPerUnit<0m||
            fullDebit<0m||remainderDebit is not decimal debit||debit<0m||
            fullFee<0m||closeFee<0m||remainderFee<0m)return null;
        decimal rest=held-close;
        bool Legal(decimal units)=>units>=minimum&&units<=maximum&&(units-minimum)%step==0m;
        if(!Legal(held)||!Legal(close)||!Legal(rest))return null;
        // The existing common-book partial fill releases reserved risk
        // proportionally. Reject a non-proportional residual cost burden.
        if(debit>fullDebit*rest/held||remainderFee>fullFee*rest/held)return null;
        decimal splitFee=closeFee+remainderFee-fullFee;
        if(splitFee<0m)return null; // inconsistent fee schedule, no inferred credit
        decimal vsClose=rest*(meanEurPerUnit-uncertaintyEurPerUnit)-debit-splitFee;
        decimal vsHold=-close*(meanEurPerUnit+uncertaintyEurPerUnit)+fullDebit-debit-splitFee;
        decimal advantage=Math.Min(vsClose,vsHold);
        return advantage>0m?advantage:null;
    }

    // Compare feasible remaining exposure against immediate CLOSE, without
    // assigning an invented EUR return to released margin or risk. HOLD is
    // excluded only by a witnessed portfolio constraint. Funding ceilings
    // are conservative debits, not cash savings credited to the ledger.
    public static decimal? ConstrainedReductionValue(decimal held,decimal close,
        decimal minimum,decimal maximum,decimal step,decimal meanEurPerUnit,
        decimal uncertaintyEurPerUnit,decimal? remainingDebit,decimal fullFee,
        decimal closeFee,decimal remainingFee,decimal equity,decimal floor,
        decimal otherMargin,decimal otherRisk,decimal marginPerUnit,
        decimal fullRisk,decimal remainingRisk)
    {
        if(minimum<=0m||maximum<minimum||step<=0m||held<=0m||
            equity<=0m||floor<0m||otherMargin<0m||otherRisk<0m||marginPerUnit<=0m||
            fullRisk<0m||remainingRisk<0m||uncertaintyEurPerUnit<0m||
            remainingDebit is not decimal debit||debit<0m||fullFee<0m||closeFee<0m||remainingFee<0m)
            return null;
        decimal remainder=held-close;
        bool Legal(decimal units)=>units>=minimum&&units<=maximum&&(units-minimum)%step==0m;
        if(!Legal(held)||!Legal(close)||!Legal(remainder)||remainingRisk>fullRisk)return null;
        bool Fits(decimal cash,decimal units,decimal risk)=>cash>=floor&&
            otherMargin+units*marginPerUnit<=cash*NativePendingCapitalGate.MaximumMarginFraction&&
            otherRisk+risk<=cash*NativePendingCapitalGate.MaximumAggregateStopFraction&&
            risk<=cash*NativePendingCapitalGate.MaximumTradeStopFraction&&cash-otherRisk-risk>=floor;
        if(Fits(equity,held,fullRisk))return null; // HOLD remains an eligible alternative
        decimal splitFee=closeFee+remainingFee-fullFee;
        if(splitFee<0m||!Fits(equity-splitFee,remainder,remainingRisk))return null;
        decimal lower=remainder*(meanEurPerUnit-uncertaintyEurPerUnit)-debit-splitFee;
        return lower>0m?lower:null;
    }

    internal static NativeBarWindow? Window(Ucp1MarketFrame m,NativeBarTimeframe tf,long at)
        =>m.ClosedBars?.DecisionAt==at?m.ClosedBars.Windows.SingleOrDefault(w=>w.Timeframe==tf&&w.Ready&&
            w.Bars.Length>=3&&w.Bars.All(b=>b.CloseAt<at)):null;
    static decimal TrueRange(NativeClosedMarketBar b,decimal prior)
        =>Math.Max(b.High-b.Low,Math.Max(Math.Abs(b.High-prior),Math.Abs(b.Low-prior)));
    static decimal Atr(NativeClosedMarketBar[] b)
        =>b.Skip(1).Select((x,i)=>TrueRange(x,b[i].Close)).Average();
    static decimal Tick(decimal v,decimal tick,bool up)=>(up?Math.Ceiling(v/tick):Math.Floor(v/tick))*tick;

    // Useful PAV1 component: reward is a completed, adjacent economic transition,
    // not a fixed future-horizon label. The current transition is never its own label.
    // This local price proxy is converted at the current contract/FX for decisions;
    // only funded ledger outcomes qualify NET. No cross-symbol return transfer.
    internal static (decimal Mean,decimal Sem,int Count)? Continuation(Ucp1MarketFrame m,long at,string? timeframe=null,int lookback=0)
    {
        var tf=timeframe is null?NativeBarTimeframe.M15:Enum.Parse<NativeBarTimeframe>(timeframe);
        var w=lookback>0?(m.ClosedBars?.DecisionAt==at?m.EconomicTransitionWindows?.SingleOrDefault(x=>x.Timeframe==tf&&x.Ready&&
            x.Bars.Length>=lookback&&x.Bars.All(b=>b.CloseAt<at)):null):Window(m,tf,at);
        if(w is null)return null;
        var b=lookback>0?w.Bars.TakeLast(lookback).ToArray():w.Bars; int state=Math.Sign(b[^1].Close-b[^2].Close);
        var changes=new List<decimal>();
        for(int i=2;i<b.Length;i++)
            if(b[i-2].CloseAt==b[i-1].OpenAt&&b[i-1].CloseAt==b[i].OpenAt&&
                Math.Sign(b[i-1].Close-b[i-2].Close)==state)
                changes.Add(b[i].Close-b[i-1].Close);
        if(changes.Count<2)return null;
        decimal mean=changes.Average();
        decimal sem=(decimal)Math.Sqrt(changes.Sum(x=>Math.Pow((double)(x-mean),2))/
            (changes.Count*(changes.Count-1d)));
        return (mean,sem,changes.Count);
    }

    // Conditional economic path projection using only adjacent completed
    // bars. Both-boundary ambiguity is treated adversely; a gap through the
    // stop uses the worse open. This is a causal forecast, not a tick fill.
    internal static decimal? BoundaryPathValueEur(int side,decimal now,decimal stop,decimal target,
        decimal open,decimal high,decimal low,decimal close,decimal credit,decimal debit)
    {
        if(side is not (1 or -1)||now<=0m||stop<=0m||target<=0m||
            side*(now-stop)<=0m||side*(target-now)<=0m||low<=0m||
            high<Math.Max(open,close)||low>Math.Min(open,close)||credit<=0m||debit<credit)return null;
        bool stopped=side>0?low<=stop:high>=stop;
        bool reached=side>0?high>=target:low<=target;
        decimal exit=stopped?(side>0?Math.Min(stop,open):Math.Max(stop,open)):reached?target:close;
        decimal change=side*(exit-now);
        return change*(change>=0m?credit:debit);
    }

    internal sealed record BoundaryEstimate(decimal Mean,decimal Sem,int Count,int Days,
        decimal StopProbability,decimal TargetProbability,decimal AmbiguousProbability,
        long HorizonMs,long From,long Through);

    internal static BoundaryEstimate? BoundaryDistributionEur(Ucp1MarketFrame m,long at,
        int side,decimal now,decimal stop,decimal target,string? timeframe=null,
        int minimumSamples=8,int minimumDays=1,bool normalize=true)
    {
        if(minimumSamples<3||minimumDays<1)return null;
        var tf=timeframe is null?NativeBarTimeframe.M15:Enum.Parse<NativeBarTimeframe>(timeframe);
        var w=m.ClosedBars?.DecisionAt==at?m.EconomicTransitionWindows?.Where(x=>x.Timeframe==tf&&x.Ready&&
            x.Bars.Length>=3&&x.Bars.All(v=>v.CloseAt<at)).OrderByDescending(x=>x.Bars.Length).FirstOrDefault():null;
        w??=Window(m,tf,at);
        if(w is null)return null;
        var bars=w.Bars;
        if(bars[^2].CloseAt!=bars[^1].OpenAt)return null;
        int state=Math.Sign(bars[^1].Close-bars[^2].Close);
        decimal currentRange=TrueRange(bars[^1],bars[^2].Close);
        if(currentRange<=0m)return null;
        var values=new List<(decimal Value,long Day,long At)>();
        int stops=0,targets=0,ambiguous=0;
        for(int i=2;i<bars.Length;i++)
        {
            var previous=bars[i-1];var label=bars[i];
            if(bars[i-2].CloseAt!=previous.OpenAt||previous.CloseAt!=label.OpenAt||
                Math.Sign(previous.Close-bars[i-2].Close)!=state)continue;
            decimal priorRange=TrueRange(previous,bars[i-2].Close);
            if(priorRange<=0m)continue;
            // Normalize using the range of the state bar, never the label.
            decimal scale=normalize?currentRange/priorRange:1m;
            decimal Project(decimal x)=>now+(x-previous.Close)*scale;
            var value=BoundaryPathValueEur(side,now,stop,target,Project(label.Open),Project(label.High),
                Project(label.Low),Project(label.Close),m.Quote.EurCredit,m.Quote.EurDebit);
            // Dropping an invalid adverse projection could select away loss
            // mass. An unsupported price-domain extrapolation has no forecast.
            if(value is null)return null;
            if(value is decimal v)
            {
                bool stopped=side>0?Project(label.Low)<=stop:Project(label.High)>=stop;
                bool reached=side>0?Project(label.High)>=target:Project(label.Low)<=target;
                if(stopped)stops++;
                if(reached&&!stopped)targets++;
                if(stopped&&reached)ambiguous++;
                values.Add((v,label.CloseAt/86_400_000L,label.CloseAt));
            }
        }
        var days=values.GroupBy(x=>x.Day).ToArray();
        if(values.Count<minimumSamples||days.Length<minimumDays)return null;
        decimal mean=values.Average(x=>x.Value);
        decimal sem=(decimal)Math.Sqrt(values.Sum(x=>Math.Pow((double)(x.Value-mean),2))/
            (values.Count*(values.Count-1d)));
        if(days.Length>1)
        {
            decimal cluster=(decimal)Math.Sqrt(days.Sum(g=>Math.Pow((double)g.Sum(x=>x.Value-mean),2))*
                days.Length/(days.Length-1d)/(values.Count*(double)values.Count));
            sem=Math.Max(sem,cluster);
        }
        return new(mean,sem,values.Count,days.Length,stops/(decimal)values.Count,
            targets/(decimal)values.Count,ambiguous/(decimal)values.Count,(long)tf*60_000L,
            values.Min(x=>x.At),values.Max(x=>x.At));
    }

    internal static (decimal Mean,decimal Sem,int Count)? BoundaryContinuationEur(Ucp1MarketFrame m,long at,
        int side,decimal now,decimal stop,decimal target,string? timeframe=null,int minimumSamples=8,
        int minimumDays=1,bool normalize=true)
    {
        var value=BoundaryDistributionEur(m,at,side,now,stop,target,timeframe,minimumSamples,minimumDays,normalize);
        return value is null?null:(value.Mean,value.Sem,value.Count);
    }

    internal static NativeEurPayoff? TransitionPayoff(Ucp1MarketFrame m,long at,int side,
        decimal units,decimal cost,string? timeframe=null,int lookback=0)
    {
        if(Continuation(m,at,timeframe,lookback) is not { } transition)return null;
        var q=m.Quote;
        decimal mean=side*transition.Mean*units;
        decimal gross=mean*(mean>=0m?q.EurCredit:q.EurDebit),width=transition.Sem*units*q.EurDebit;
        return new(transition.Count,0,gross,gross-width,gross-cost,gross-width-cost,
            0m,gross-width-cost,gross+width-cost)
            {Cohort="PAV1_LOCAL_ADJACENT_PRICE_PROXY_NOT_REALIZED_LIFECYCLE"};
    }

    internal static NativeIntegratedCandidate[] Describe(string mechanism,Ucp1MarketFrame m,long at,
        decimal targetRanges,Ucp1Frame? frame=null,string? geometryTimeframe=null,decimal? stopRanges=null,bool closedStructure=false,
        int structureLookback=0,bool confirmM5=false,int transitionLookback=0)
    {
        if(!All.Contains(mechanism,StringComparer.Ordinal))throw new ArgumentException("ECONOMIC_MECHANISM_UNKNOWN");
        var w=Window(m,NativeBarTimeframe.M5,at);
        if(w is null||m.EurTickSize is not >0m||w.Bars[^1].CloseAt!=m.M5.LastOrDefault()?.CloseAt)
            return Array.Empty<NativeIntegratedCandidate>();
        if(mechanism==Scored)
            return All.Where(x=>x is not (Scored or Transition))
                .SelectMany(x=>Describe(x,m,at,targetRanges,frame,geometryTimeframe,stopRanges,closedStructure,structureLookback,confirmM5)).ToArray();
        var b=w.Bars;decimal tick=m.EurTickSize.Value,atr=Math.Max(tick,Atr(b));
        var geometry=geometryTimeframe is null?w:Window(m,Enum.Parse<NativeBarTimeframe>(geometryTimeframe),at);
        if(geometry is null)return Array.Empty<NativeIntegratedCandidate>();
        var gb=geometry.Bars;decimal geometryAtr=Math.Max(tick,Atr(gb));
        int side=0;decimal? destination=null;
        var h=Window(m,NativeBarTimeframe.H1,at);
        var z=Window(m,NativeBarTimeframe.M15,at);
        int shortDirection=Math.Sign(b[^1].Close-b[^2].Close);
        switch(mechanism)
        {
            case Follow:side=Math.Sign(gb[^1].Close-gb[^2].Close);break;
            case Reverse:side=-Math.Sign(gb[^1].Close-gb[^2].Close);
                if(geometryTimeframe is not null&&side*(gb[^2].Close-gb[^1].Close)>0m)destination=gb[^2].Close;
                break;
            case Range:
                decimal high=gb[..^1].Max(x=>x.High),low=gb[..^1].Min(x=>x.Low);
                side=gb[^1].Close>high?1:gb[^1].Close<low?-1:0;
                if(z is null||h is null||side*(z.Bars[^1].Close-z.Bars[0].Open)<=0m||
                    side*(h.Bars[^1].Close-h.Bars[0].Open)<=0m)side=0;
                break;
            case Equilibrium:
                if(h is null||z is null)break;
                var anchor=geometryTimeframe is null?h:geometry;
                decimal center=anchor.Bars.Average(x=>(x.High+x.Low+x.Close)/3m);
                // Natural equilibrium destination on the registered anchor horizon.
                // In the new mode the observed M15 turn and executable target
                // economics replace the common M5 amplitude threshold.
                side=Math.Sign(center-b[^1].Close);
                int turn=geometryTimeframe is null?shortDirection:Math.Sign(z.Bars[^1].Close-z.Bars[^2].Close);
                if(side!=turn||geometryTimeframe is null&&Math.Abs(center-b[^1].Close)<atr)side=0;
                else destination=center;
                break;
            case Activity:
                // V3.3 impulse/activity is an entry mechanism across distinct
                // completed timeframes, not extra inputs to the V3 estimator.
                var impulses=NativeClosedMarketContext.CoverageWindows.Select(r=>Window(m,r.Timeframe,at))
                    .OfType<NativeBarWindow>().Select(x=>
                    {
                        var p=x.Bars;decimal scale=Atr(p),prior=p[..^1].Average(v=>(decimal)v.TickVolume);
                        return (Move:scale>0m?(p[^1].Close-p[^2].Close)/scale:0m,
                            Active:prior>0m&&p[^1].TickVolume>prior);
                    }).ToArray();
                if(impulses.Length>=3&&impulses.Count(x=>x.Active)>=2)
                {
                    int vote=impulses.Sum(x=>Math.Sign(x.Move));
                    if(Math.Abs(vote)*2>impulses.Length)side=Math.Sign(vote);
                }
                break;
            case Intermarket:
                // Official class and aligned clocks are required. Missing class
                // identity cannot be replaced by an assumed economic relationship.
                if(h is null||frame is null||m.OfficialAssetClass is null)break;
                var relative=geometryTimeframe is null?h:geometry;
                var peers=frame.Markets.Where(p=>p.Symbol!=m.Symbol&&p.OfficialAssetClass==m.OfficialAssetClass)
                    .Select(p=>Window(p,relative.Timeframe,at)).OfType<NativeBarWindow>()
                    .Where(p=>p.ExpectedCloseAt==relative.ExpectedCloseAt).ToArray();
                if(peers.Length<2)break;
                decimal Move(NativeBarWindow p)=>(p.Bars[^1].Close-p.Bars[0].Open)/p.Bars[0].Open;
                decimal peerMove=peers.Average(Move),difference=Move(relative)-peerMove;
                if(Math.Abs(difference)>Atr(relative.Bars)/relative.Bars[^1].Close)
                {
                    side=-Math.Sign(difference);
                    if(geometryTimeframe is not null)
                        destination=relative.Bars[0].Open*(1m+peerMove);
                }
                break;
            case Transition:
                if(Continuation(m,at,geometryTimeframe,transitionLookback) is { } transition&&Math.Abs(transition.Mean)>transition.Sem)
                    side=Math.Sign(transition.Mean);
                break;
        }
        if(side==0)return Array.Empty<NativeIntegratedCandidate>();
        if(confirmM5&&side*shortDirection<=0)return Array.Empty<NativeIntegratedCandidate>();
        decimal entry=side>0?m.Quote.Ask:m.Quote.Bid,exit=side>0?m.Quote.Bid:m.Quote.Ask;
        decimal stop=Tick(exit-side*geometryAtr*(stopRanges??1m),tick,side<0);
        // Reverse uses the preceding closed price as a natural repair
        // destination only when it is still ahead of the executable entry.
        // Otherwise the registered range extension remains a separate hypothesis.
        if(mechanism==Reverse&&destination is decimal repair)
        {
            if(side*(repair-entry)<=0m)destination=null;
            else destination=entry+side*Math.Max(side*(repair-entry),targetRanges*geometryAtr);
        }
        // The alternative stop belongs to the completed signal structure,
        // not to the moving executable entry. Favorable movement can improve
        // reward/risk; adverse entry cannot push the economic destination away.
        if(closedStructure)
        {
            if(structureLookback>gb.Length)return Array.Empty<NativeIntegratedCandidate>();
            var structure=structureLookback>0?gb.TakeLast(structureLookback).ToArray():new[]{gb[^1]};
            decimal boundary=side>0?Math.Min(structure.Min(x=>x.Low),b[^1].Low):Math.Max(structure.Max(x=>x.High),b[^1].High);
            // Swing invalidation and current completed M5 noise have distinct
            // horizons. The buffer is an observed true range, never a fitted
            // duration or an entry-relative stop expansion. Target stays fixed.
            decimal buffer=structureLookback>0?Math.Max(tick,atr):tick;
            stop=Tick(boundary-side*buffer,tick,side<0);
            decimal anchor=gb[^1].Close;
            if(mechanism==Reverse)
            {
                decimal repairDistance=side*(gb[^2].Close-anchor);
                destination=anchor+side*Math.Max(repairDistance,targetRanges*geometryAtr);
            }
            else destination??=anchor+side*targetRanges*geometryAtr;
        }
        decimal target=Tick(destination??entry+side*targetRanges*geometryAtr,tick,side>0);
        return stop>0m&&target>0m&&side*(exit-stop)>0m&&side*(target-entry)>0m&&
            NativeIntegratedLifecycle.ProtectionCompatible(side,stop,target,m)
            ?new[]{new NativeIntegratedCandidate(mechanism,side,stop,target,geometryAtr,b[^1].CloseAt)}
            :Array.Empty<NativeIntegratedCandidate>();
    }

    // Useful SCP1 component: empirical P(win) and conditional upside/downside.
    // Inputs are completed funded lifecycle outcomes with identical management,
    // geometry and instrument. Each calendar day has equal total weight. There
    // is no fallback from unsupported local evidence to unrelated instruments.
    internal static NativeEurPayoff? LifecyclePayoff(IEnumerable<NativeEurCalibrationOutcome> outcomes,
        string family,int side,NativeEurDecisionContext context,long at,decimal risk,decimal cost,
        int minimumEpisodes,int minimumDays,decimal penalty)
    {
        int? regime=context.ClosedStates.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1)?.Direction;
        var rows=outcomes.Where(x=>x.AvailableAt<at&&x.Family==family&&x.Side==side&&x.Context?.Symbol==context.Symbol&&
            x.Context.ClosedStates.SingleOrDefault(s=>s.Timeframe==NativeBarTimeframe.H1)?.Direction==regime).ToArray();
        var days=rows.GroupBy(x=>x.ClosedAt/86_400_000L).ToArray();
        if(rows.Length<minimumEpisodes||days.Length<minimumDays)return null;
        decimal probability=days.Average(g=>(decimal)g.Count(x=>x.GrossEur>0m)/g.Count());
        decimal positive=days.Average(g=>g.Average(x=>Math.Max(0m,x.GrossEur)/x.RiskEur));
        decimal negative=days.Average(g=>g.Average(x=>Math.Min(0m,x.GrossEur)/x.RiskEur));
        decimal win=probability>0m?positive/probability:0m;
        decimal loss=probability<1m?negative/(1m-probability):0m;
        decimal gross=(probability*win+(1m-probability)*loss)*risk;
        decimal net=Math.Min(gross-cost,days.Average(g=>g.Average(x=>x.NetEur/x.RiskEur))*risk);
        decimal Lower(decimal mean,Func<NativeEurCalibrationOutcome,decimal> value)
            =>mean-penalty*(decimal)Math.Sqrt(days.Sum(g=>Math.Pow((double)(g.Average(value)*risk-mean),2))/
                (days.Length*(days.Length-1d)));
        return new(rows.Length,days.Length,gross,Lower(gross,x=>x.GrossEur/x.RiskEur),net,
            Math.Min(Lower(gross,x=>x.GrossEur/x.RiskEur)-cost,Lower(net,x=>x.NetEur/x.RiskEur)),
            days.Average(g=>(decimal)g.Count(x=>x.NetEur>0m)/g.Count()),rows.Min(x=>x.NetEur/x.RiskEur)*risk,
            rows.Max(x=>x.NetEur/x.RiskEur)*risk)
            {Cohort=$"SCP1_SAME_SYMBOL_REGIME/PWIN={probability:G6}/WIN_R={win:G6}/LOSS_R={loss:G6}"};
    }
    // Separate monetary settlement from excursion sampling. All rows are
    // conditional modeled outcomes, not broker execution certifications.
    internal static NativeEurPayoff? EntryQualityPayoff(IEnumerable<NativeEurCalibrationOutcome> outcomes,
        string family,int side,NativeEurDecisionContext context,long at,decimal risk,decimal cost,
        int minimumEpisodes,int minimumDays,decimal penalty,bool costBand)
    {
        var local=outcomes.Where(x=>x.AvailableAt<at&&x.RiskEur>0m&&x.Family==family&&x.Side==side&&
            x.Context?.Symbol==context.Symbol).ToArray();
        if(!costBand)return LifecyclePayoff(local,family,side,context,at,risk,cost,minimumEpisodes,minimumDays,penalty);
        int? regime=context.ClosedStates.SingleOrDefault(x=>x.Timeframe==NativeBarTimeframe.H1)?.Direction;
        local=local.Where(x=>x.Context!.ClosedStates.SingleOrDefault(s=>s.Timeframe==NativeBarTimeframe.H1)?.Direction==regime).ToArray();
        if(local.Length<minimumEpisodes)return null;
        var costs=local.Select(x=>x.Context!.CostRiskFraction).OrderBy(x=>x).ToArray();
        decimal median=costs[costs.Length/2];
        bool lower=context.CostRiskFraction<=median;
        var band=local.Where(x=>(x.Context!.CostRiskFraction<=median)==lower).ToArray();
        var estimate=LifecyclePayoff(band,family,side,context,at,risk,cost,minimumEpisodes,minimumDays,penalty);
        return estimate is null?null:estimate with {Cohort=estimate.Cohort+FormattableString.Invariant($"/CAUSAL_COST_MEDIAN:{median:G29}/LOWER:{lower}")};
    }

    internal sealed record PeerForecast(int SupportedPeers,decimal MeanGrossEur,decimal MeanNetEur,
        decimal WorstGrossLowerEur,decimal WorstNetLowerEur)
    {
        [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
        public decimal? BalancedGrossLowerEur { get; init; }
        [System.Text.Json.Serialization.JsonIgnore(Condition=System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
        public decimal? BalancedNetLowerEur { get; init; }
    }

    // Independent per-instrument forecasts in the same authenticated class.
    // Normalize by ex-ante monetary risk, use the target's actual cost and
    // causal cost band, and never let a target instrument train its own peer
    // prediction. A prediction is a diagnostic, not authorization to trade.
    internal static PeerForecast? LeaveSymbolOutPayoff(IEnumerable<NativeEurCalibrationOutcome> outcomes,
        string family,int side,NativeEurDecisionContext context,long at,decimal risk,decimal cost,
        int minimumEpisodes,int minimumDays,decimal penalty,bool balanced=false)
    {
        if(string.IsNullOrWhiteSpace(context.AssetClass)||risk<=0m)return null;
        var estimates=outcomes.Where(x=>x.AvailableAt<at&&x.RiskEur>0m&&x.Family==family&&x.Side==side&&
            x.Context?.AssetClass==context.AssetClass&&x.Context.Symbol!=context.Symbol)
            .GroupBy(x=>x.Context!.Symbol,StringComparer.Ordinal)
            .Select(g=>EntryQualityPayoff(g,family,side,context with {Symbol=g.Key},at,risk,cost,
                minimumEpisodes,minimumDays,penalty,true)).OfType<NativeEurPayoff>().ToArray();
        if(estimates.Length<2)return null;
        var forecast=new PeerForecast(estimates.Length,estimates.Average(e=>e.GrossMeanEur),estimates.Average(e=>e.NetMeanEur),
            estimates.Min(e=>e.GrossLowerEur),estimates.Min(e=>e.NetLowerEur));
        if(!balanced)return forecast;
        // Equal instrument weights, with both local day uncertainty and
        // between-instrument uncertainty retained. Diagnostic only; preserve
        // the worst-peer comparison and never change native admission gates.
        decimal Dispersion(Func<NativeEurPayoff,decimal> value)
        {
            decimal mean=estimates.Average(value);
            return penalty*(decimal)Math.Sqrt(estimates.Sum(e=>Math.Pow((double)(value(e)-mean),2))/
                (estimates.Length*(estimates.Length-1d)));
        }
        return forecast with
        {
            BalancedGrossLowerEur=estimates.Average(e=>e.GrossLowerEur)-Dispersion(e=>e.GrossMeanEur),
            BalancedNetLowerEur=estimates.Average(e=>e.NetLowerEur)-Dispersion(e=>e.NetMeanEur)
        };
    }
}
