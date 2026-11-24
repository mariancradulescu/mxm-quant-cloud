using System.Linq;
using cAlgo.API;
using Mxm.Core;
using Mxm.Cloud;

namespace cAlgo.Robots;

[Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
public partial class MxmCloud : Robot
{
    // Adds proactively observed markets before positions exist; no order permission.
    [Parameter("Read-only research universe", DefaultValue = "EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,US500,NAS100,XAUUSD")]
    public string ReadOnlyResearchUniverse { get; set; } = "EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,US500,NAS100,XAUUSD";

    [Parameter("Exploratory EUR300 model replay (NO orders)", DefaultValue = true)]
    public bool EnableExploratoryReplay { get; set; } = true;
    // Active M5 research lanes remain observed at EVERY completed M5 clock.
    // The separate 256-symbol survey rotates only for non-active discovery.
    // This list is a predeclared feasibility watchlist, NOT fitted alpha.
    [Parameter("Active M5 research watchlist (max 16)", DefaultValue =
        "EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,US500,NAS100,XAUUSD")]
    public string ActiveM5ResearchWatchlist { get; set; } =
        "EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,US500,NAS100,XAUUSD";

    // Optional new observation-only calibration. Set a future UTC cutoff to
    // collect complete outcomes before evaluating in the same model episode.
    [Parameter("Calibration cutoff UTC (blank uses legacy)", DefaultValue = "")]
    public string CalibrationCutoffUtc { get; set; } = "";
    [Parameter("Friday inventory development profile (no orders)", DefaultValue = false)]
    public bool FridayInventoryResearch { get; set; }
    [Parameter("Integrated development model envelope (no orders)", DefaultValue = "")]
    public string IntegratedDevelopmentModel { get; set; } = "";
    private bool _integratedResearch;
    private bool _conditionalResearch;
    private bool _discoveryResearch;
    private bool _calibratedResearch;
    [Parameter("UCP1 unified economic observation (NO ORDERS)", DefaultValue = false)]
    public bool EnableUnifiedReadOnlyPolicy {get;set;}
    [Parameter("Full-session integrated policy observation (NO ORDERS)", DefaultValue = false)]
    public bool EnableFullSessionObservation {get;set;}
    [Parameter("Complete policy snapshot (NO ORDERS)", DefaultValue = "")]
    public string CompletePolicySnapshot {get;set;}="";
    private bool _completePolicyObservation;
    [Parameter("SCP1 precommitted score snapshot (NO ORDERS)", DefaultValue = "")]
    public string Scp1FrozenModelEnvelope {get;set;}="";
    private NativeUnifiedCloudParityAdapter? _unifiedPolicy;
    private long _lastUnifiedObservedAt;
    private int _lastUnifiedClosed=-1;
    private NativeProductResearchLoop? _productResearch;
    private int _lastResearchModelTrips = -1;
    private string _lastResearchEconomicStatus = "";
    private string _lastMode = "";
    private bool _transientFault;
    private NativeFundedSession? _fundedSession;
    private string _accountBinding="";
    private string _lastInventory="";
    private string _lastNativeCashFingerprint="";
    private string _lastNativeOpenInventoryFingerprint="";
    private long _nextWarmupPollAt;
    private string _lastWarmupStatus="";
    private string _lastUniverseStatus="";
    private int _readOnlyUniverseSweep;
    private static long Stamp(System.DateTime t)=>new System.DateTimeOffset(System.DateTime.SpecifyKind(t,System.DateTimeKind.Utc)).ToUnixTimeMilliseconds();


    protected override void OnStart()
    {
        // The actual delivered .algo is OBSERVATION ONLY: no order code,
        // no live/demo permission and no external runtime dependencies.
        // Timer resumes native reconciliation after a recoverable exception.
        _accountBinding=System.Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
            System.Text.Encoding.UTF8.GetBytes("ctrader-native-account:"+Account.Number))).ToLowerInvariant();
        // cTrader Cloud LocalStorage is in-memory only and GetString on an
        // unset key may raise LocalStorageException. Do not load any checkpoint
        // as the restart authority. Reconstruct from native broker facts.
        _fundedSession=new NativeFundedSession(_accountBinding);

        if (ObserveStructuralPortfolio)
            StartStructuralObservation();
        else if(EnableFullSessionObservation)
        {
            if(string.IsNullOrWhiteSpace(CompletePolicySnapshot))
                _unifiedPolicy=new NativeUnifiedCloudParityAdapter(NativeIntegratedLifecycle.Economic,_accountBinding);
            else
            {
                try
                {
                    var model=System.Text.Json.JsonSerializer.Deserialize<NativeCompleteModels>(CompletePolicySnapshot);
                    if(model is null || model.AvailableAt<=0L || model.AvailableAt>=Stamp(Server.TimeInUtc) ||
                       model.Entry is null || model.Hold is null ||
                       model.Entry.Samples.Any(x=>x.SettledAt>=model.AvailableAt) ||
                       model.Hold.Samples.Any(x=>x.SettledAt>=model.AvailableAt))
                        throw new System.ArgumentException("COMPLETE_POLICY_SNAPSHOT_NOT_CAUSAL");
                    _unifiedPolicy=new NativeUnifiedCloudParityAdapter(NativeCompletePolicy.Economic,_accountBinding,models:model);
                    _completePolicyObservation=true;
                }
                catch(System.Exception)
                {
                    Print("Complete policy snapshot rejected. Native broker observation remains read-only.");
                }
            }
        }
        else if(EnableUnifiedReadOnlyPolicy)
        {
            if(!string.IsNullOrWhiteSpace(Scp1FrozenModelEnvelope))
            {
                try
                {
                    var score=System.Text.Json.JsonSerializer.Deserialize<Scp1ScoreModel>(
                        Scp1FrozenModelEnvelope);
                    if(score is null || score.Version!=NativeScp1EconomicScorer.Version ||
                       score.TrainingEnd>=Stamp(Server.TimeInUtc) ||
                       score.CalibrationEnd>=Stamp(Server.TimeInUtc) ||
                       !score.MethodSelectedWithoutEvaluation)
                        throw new System.ArgumentException("SCP1_FROZEN_MODEL_NOT_CAUSAL");
                    _unifiedPolicy=new NativeUnifiedCloudParityAdapter(
                        "SCP1_ABSTAIN",_accountBinding,score);
                    Print("MXM SCP1 observation-only common Core: frozen score loaded; method {0}; no trading.",
                        score.Method);
                }
                catch(System.Exception)
                {
                    // No fallback to a fake trained score or unspecified
                    // model; observing real account risk remains active.
                    Print("MXM SCP1 model envelope rejected, financial decisions inactive.");
                }
            }
            else
                _unifiedPolicy=new NativeUnifiedCloudParityAdapter("JOINT",_accountBinding);
        }
        // Independent MODEL_REPLAY capital, never the broker monetary domain.
        // A restart begins a fresh observational simulation, not a cash reset
        // of any broker account; historical recovery requires causal replay.
        if(EnableExploratoryReplay && !EnableUnifiedReadOnlyPolicy && !EnableFullSessionObservation && !ObserveStructuralPortfolio)
        {
            if(!string.IsNullOrWhiteSpace(IntegratedDevelopmentModel))
            {
                try
                {
                    var model=NativeIntegratedSnapshot.Open(IntegratedDevelopmentModel);
                    if(model.Boundary>=Stamp(Server.TimeInUtc))throw new System.ArgumentException("Model not yet causal");
                    _integratedResearch=_calibratedResearch=true;
                    _conditionalResearch=model.Conditional is not null;
                    _discoveryResearch=model.Profile==NativeDiscoveryResearch.Profile;
                    _productResearch=new NativeProductResearchLoop(_discoveryResearch?"DCP1_JOINT":_conditionalResearch?"CDE1_JOINT":"IPC2_JOINT",
                        model.Boundary,model);
                }
                catch(System.Exception)
                {
                    Print("Integrated development model rejected. Prediction remains inactive.");
                }
            }
            else if(string.IsNullOrWhiteSpace(CalibrationCutoffUtc) && !FridayInventoryResearch)
                _productResearch=new NativeProductResearchLoop();
            else if(System.DateTimeOffset.TryParseExact(CalibrationCutoffUtc,"yyyy-MM-dd",
                System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.AssumeUniversal,out var cutoff) &&
                cutoff.ToUnixTimeMilliseconds()>0)
            {
                _calibratedResearch=true;
                _productResearch=new NativeProductResearchLoop(FridayInventoryResearch?"WIR1_JOINT":"CAL1_JOINT",cutoff.ToUnixTimeMilliseconds());
            }
            else Print("MXM calibration cutoff must be a UTC date in yyyy-MM-dd form.");
        }
        if(_productResearch is not null)
            Print("MXM isolated model-only EUR300 research epoch {0}; no Cloud LocalStorage continuity or cumulative profit claim.",
                _productResearch.ModelEpochId);
        Timer.Start(15);
        ObserveNative();
    }

    protected override void OnTimer()
    {
        ObserveNative();
    }

    protected override void OnException(System.Exception exception)
    {
        // Do not log account data, arbitrary exception contents or secrets.
        // A subsequent successful native observation clears transient state.
        _transientFault = true;
        Print("MXM native observation exception; scheduled auto-reconciliation continues.");
    }


    private (decimal Bid,decimal Ask,long At)? ReadTickAsOf(string symbol,long clock)
    {
        var ticks=MarketData.GetTicks(symbol);
        for(int i=ticks.Count-1;i>=0;i--)
        {
            var tick=ticks[i];
            long stamp=Stamp(tick.Time);
            if(stamp>clock)continue;
            if(clock-stamp>30000L || tick.Bid<=0d || tick.Ask<tick.Bid)return null;
            return ((decimal)tick.Bid,(decimal)tick.Ask,stamp);
        }
        return null;
    }

    private NativeProductMarket? ReadProductResearchMarket(string name,long clock,bool fullSession=false)
    {
        // All mappings use CURRENT cTrader platform terms, not retrospectively
        // certified Pepperstone history or guaranteed historical fill prices.
        var market=Symbols.GetSymbol(name);
        if(!market.IsTradingEnabled || !market.MarketHours.IsOpened() ||
            market.Bid<=0 || market.Ask<market.Bid)return null;
        var m5=MarketData.GetBars(TimeFrame.Minute5,name);

        NativeClosedMarketBar[] Prefix(Bars bars,int minutes,int n=NativeCausalWarmup.WindowBars)
        {
            if(bars.Count<n+1 && !fullSession)return System.Array.Empty<NativeClosedMarketBar>();
            int end=fullSession?bars.Count-1:bars.Count-2;
            if(fullSession)
                while(end>=0 && Stamp(bars.OpenTimes[end])+minutes*60000L>=clock)end--;
            int length=System.Math.Min(n,end+1);
            var output=new NativeClosedMarketBar[length];
            for(int j=0;j<length;j++)
            {
                int i=end-length+1+j;
                long open=Stamp(bars.OpenTimes[i]);
                output[j]=new(open,open+(long)minutes*60000L,
                    (decimal)bars.OpenPrices[i],(decimal)bars.HighPrices[i],
                    (decimal)bars.LowPrices[i],(decimal)bars.ClosePrices[i],
                    (long)bars.TickVolumes[i]);
            }
            return output;
        }
        var m5Prefix=Prefix(m5,5,_integratedResearch?3*NativeCausalWarmup.WindowBars+2:
            fullSession?5:NativeCausalWarmup.WindowBars);
        var shortBars=m5Prefix.TakeLast(NativeCausalWarmup.WindowBars).ToArray();
        var mediumBars=_integratedResearch?NativeHistoricalProductReplay.AggregateCompletedM15(m5Prefix)
            .TakeLast(NativeCausalWarmup.WindowBars).ToArray():Prefix(MarketData.GetBars(TimeFrame.Minute15,name),15,
                fullSession?3:NativeCausalWarmup.WindowBars);
        if(!fullSession && (shortBars.Length<NativeCausalWarmup.WindowBars ||
            mediumBars.Length<NativeCausalWarmup.WindowBars))return null;
        var feeType=(int)market.CommissionType+1;
        if(feeType<1 || feeType>4)return null;
        // Price-proportional commissions must use execution BUY/SELL sides.
        // The existing single-fee-attributed model quote is not sufficient
        // for both sides of these contracts: never misprice them.
        if(feeType is 1 or 3 && (!fullSession || market.Commission!=0d))return null;
        int pipPosition=0;
        decimal pip=(decimal)market.PipSize;
        while(pip>0m && pip<1m && pipPosition<18)
        {
            pip*=10m;pipPosition++;
        }
        if(pip!=1m)return null;
        decimal bid=(decimal)market.Bid,ask=(decimal)market.Ask;
        decimal credit,debit;
        if(_integratedResearch || _unifiedPolicy is not null)
        {
            if(market.QuoteAsset.Name!="USD" || ReadTickAsOf(name,clock) is not { } pair ||
               ReadTickAsOf("EURUSD",clock) is not { } conversion)return null;
            (bid,ask)=(pair.Bid,pair.Ask);
            credit=1m/conversion.Ask;
            debit=1m/conversion.Bid;
        }
        else credit=debit=(decimal)AssetConverter.Convert(1d,market.QuoteAsset,Account.Asset);
        string minimumAsset=market.MinCommissionType==SymbolMinCommissionType.QuoteAsset
            ?market.QuoteAsset.Name:market.MinCommissionAsset?.Name ?? "";
        decimal minimum=(decimal)market.VolumeInUnitsMin;
        if(minimum<=0)return null;
        decimal requiredMargin=(decimal)System.Math.Max(
            market.GetEstimatedMargin(TradeType.Buy,market.VolumeInUnitsMin),
            market.GetEstimatedMargin(TradeType.Sell,market.VolumeInUnitsMin));
        var commission=(decimal)market.Commission;
        // CTrader direct fee value -> the PREEXISTING Proto contract wire
        // representation. USD/lot, quote/lot are exact unit mappings.
        long commissionWire=checked((long)decimal.Round(commission*100000000m,0));
        long minWire=checked((long)decimal.Round((decimal)market.MinCommission*100000000m,0));
        int convBps=checked((int)System.Math.Round(
            market.PnLConversionFeeRate*10000d));
        int? triple=market.Swap3DaysRollover.HasValue
            ?(market.Swap3DaysRollover.Value==System.DayOfWeek.Sunday?7:
                (int)market.Swap3DaysRollover.Value):null;
        int? swapType=market.SwapCalculationType switch
        {
            SymbolSwapCalculationType.Pips=>0,
            SymbolSwapCalculationType.Percentage=>1,
            _=>null
        };
        // Algo exposes the current literal rates. Charge time, period, weekend
        // behavior and skip rules stay unknown until an applicable source proves them.
        var terms=new NativeObservedContractTerms(name,market.QuoteAsset.Name,
            clock,minimum,(decimal)market.VolumeInUnitsStep,
            (decimal)market.VolumeInUnitsMax,(decimal)market.LotSize,
            feeType,commissionWire,(int)market.MinCommissionType+1,
            minWire,minimumAsset,convBps,
            swapType,
            (decimal)market.SwapLong,(decimal)market.SwapShort,pipPosition,
            null,null,triple,null,null,false,false);
        var usdFx=NativeBrokerContractCosts.RequiresUsdCommissionRate(terms)
            ?(_integratedResearch || _unifiedPolicy is not null?(credit+debit)/2m:(decimal)AssetConverter.Convert(1d,"USD",Account.Asset)):0m;
        decimal? minAssetFx=minWire>0 && terms.MinimumCommissionType==1 &&
            minimumAsset.Length>0 && minimumAsset!=terms.QuoteAsset && minimumAsset!="USD"
            ?(decimal)AssetConverter.Convert(1d,minimumAsset,Account.Asset):null;
        var context=new NativeMarketCostContext(clock,bid,ask,credit,debit,usdFx,minAssetFx,
            requiredMargin,minimum,(_integratedResearch || _unifiedPolicy is not null)?System.Math.Max(.00001m,(ask-bid)/4m):(ask-bid)/4m);
        var attribution=NativeBrokerContractCosts.QuoteCurrentAlgo(terms,context);
        return new NativeProductMarket(name,shortBars,mediumBars,
            attribution.Quote,terms,context.SlippagePerSideQuote,
            _integratedResearch?NativeIntegratedResearch.Holding(name):
            _calibratedResearch?(FridayInventoryResearch?NativeEntryOutcomeCalibration.InventoryHoldingMinutes:
                NativeEntryOutcomeCalibration.HoldingMinutes):30,false,
            _discoveryResearch?NativeDiscoveryResearch.Exit(name):_conditionalResearch?NativeConditionalResearch.Exit(name):_integratedResearch?NativeIntegratedResearch.Exit(name):
            _calibratedResearch?(FridayInventoryResearch?NativeEntryOutcomeCalibration.InventoryExitPolicy:
                NativeEntryOutcomeCalibration.ExitPolicy):NativeCausalExitResearch.FrozenFixed);
    }

    private Ucp1MarketFrame? ReadFullSessionMarket(string name,long at)
    {
        var existing=ReadProductResearchMarket(name,at,fullSession:true);
        if(existing is null || existing.Contract is not { } contract ||
            ReadTickAsOf("EURUSD",at) is not { } conversion)return null;
        var symbol=Symbols.GetSymbol(name);
        if(symbol.TradingMode!=SymbolTradingMode.FullAccess)return null;
        decimal minimum=contract.MinimumUnits,step=contract.VolumeStepUnits;
        var volumes=new[]{minimum,minimum+step,minimum+3m*step}
            .Where(v=>v<=contract.MaximumUnits).Select(v=>new NativeObservedVolume(v,
                (decimal)symbol.GetEstimatedMargin(TradeType.Buy,(double)v),
                (decimal)symbol.GetEstimatedMargin(TradeType.Sell,(double)v))).ToArray();
        decimal tick=(decimal)symbol.TickSize;
        var platform=MarketData.GetTicks(name);
        long intervalStart=at-NativeIntegratedLifecycle.IntervalMs;
        var samples=new System.Collections.Generic.List<(long At,decimal Bid,decimal Ask)>();
        for(int i=platform.Count-1;i>=0;i--)
        {
            var observation=platform[i];
            long stamp=Stamp(observation.Time);
            if(stamp>at)continue;
            if(observation.Bid<=0d || observation.Ask<observation.Bid)break;
            samples.Add((stamp,(decimal)observation.Bid,(decimal)observation.Ask));
            if(stamp<=intervalStart)break;
        }
        if(samples.Count==0)return null;
        bool complete=samples[^1].At<=intervalStart && samples[^1].At>=intervalStart-30_000L &&
            samples.Zip(samples.Skip(1),(a,b)=>a.At-b.At).All(gap=>gap<=30_000L);
        var path=new NativeObservedQuotePath(samples.Min(x=>x.Bid),samples.Max(x=>x.Bid),
            samples.Min(x=>x.Ask),samples.Max(x=>x.Ask),complete);
        var h1=MarketData.GetBars(TimeFrame.Hour,name);
        var hours=new System.Collections.Generic.List<NativeClosedMarketBar>();
        for(int i=h1.Count-1;i>=0 && hours.Count<6;i--)
        {
            long open=Stamp(h1.OpenTimes[i]);
            long close=open+3_600_000L;
            if(close>=at)continue;
            hours.Add(new(open,close,(decimal)h1.OpenPrices[i],(decimal)h1.HighPrices[i],
                (decimal)h1.LowPrices[i],(decimal)h1.ClosePrices[i],(long)h1.TickVolumes[i]));
        }
        hours.Reverse();
        var quote=NativeIntegratedEconomicPolicy.BuildQuote(contract,at,existing.Quote.Bid,existing.Quote.Ask,
            conversion.Bid,conversion.Ask,volumes,tick);
        bool protectionPercentage=symbol.MinDistanceType==SymbolMinDistanceType.Percentage;
        decimal protectionScale=protectionPercentage?1m:(decimal)symbol.PipSize;
        var context=new NativeIntegratedMarket(hours.ToArray(),volumes,volumes.Any(v=>v.SellMargin>0m),tick,path)
        {
            Protection=new((decimal)symbol.MinStopLossDistance*protectionScale,
                (decimal)symbol.MinTakeProfitDistance*protectionScale,protectionPercentage)
        };
        if (ObserveStructuralPortfolio)
        {
            var closed = ReadClosedMarketBars(name, at, samples[0].At);
            return new(name, quote, contract, closed.For(NativeBarTimeframe.M5).Bars, closed.For(NativeBarTimeframe.M15).Bars,
                NativeIntegratedEconomicPolicy.Slippage(quote.Bid, quote.Ask, tick, false),
                "PLATFORM_MARK_AND_CAUSAL_CLOSED_CONTEXT", context with { H1 = closed.For(NativeBarTimeframe.H1).Bars })
                { ClosedBars = closed };
        }
        return new(name,quote,contract,existing.M5,existing.M15,
            NativeIntegratedEconomicPolicy.Slippage(quote.Bid,quote.Ask,tick,false),
            "OBSERVATIONAL_PLATFORM_MARK_AND_DIRECTIONAL_MARGIN_ESTIMATE",context);
    }

    private void ObserveNative()
    {
        try
        {
            // Native balances are in the deposit asset, not automatically EUR.
            if(Account.Asset.Name!="EUR")
            {
                if(_lastMode!="PROTECTIVE_DEPOSIT_CURRENCY_UNVERIFIED")
                    Print("MXM protective observation: EUR deposit currency not established; no monetary import.");
                _lastMode="PROTECTIVE_DEPOSIT_CURRENCY_UNVERIFIED";
                return;
            }
            var positions=Positions.ToArray();
            var pending=PendingOrders.ToArray();
            var closed=History.ToArray();
            var historicalOrders=HistoricalOrders.ToArray();
            var transactions=Transactions.ToArray();
            var dealRows=positions.SelectMany(p=>p.Deals)
                .Concat(closed.Select(t=>t.ClosingDeal)).SelectMany(d=>d.Closing.Append(d)).ToArray();
            var mappedDeals=dealRows.Where(d=>d.VolumeInUnits>0).Select(d=>new BrokerDealIdentity(
                d.Id.ToString(),d.OrderId.ToString(),d.PositionId.ToString(),d.SymbolName,d.TradeType==TradeType.Buy?1:-1,
                (decimal)d.VolumeInUnits,d.PositionImpact==DealPositionImpact.Closing,Stamp(d.ExecutionTime))).ToArray();
            var mappedOrders=historicalOrders.Select(o=>{
                var related=mappedDeals.Where(d=>d.OrderId==o.Id.ToString()).ToArray();
                bool? closing=related.Length>0&&related.All(d=>d.Closing==related[0].Closing)?related[0].Closing:null;
                return new BrokerOrderIdentity(o.Id.ToString(),"",o.PositionId?.ToString()??"",o.SymbolName,o.TradeType==TradeType.Buy?1:-1,
                    (decimal)o.VolumeInUnits,(decimal)(o.FilledVolumeInUnits??0),closing,o.Status.ToString().ToUpperInvariant(),Stamp(o.FilledTime??o.SubmittedTime),Stamp(o.SubmittedTime));
            }).Concat(pending.Select(o=>new BrokerOrderIdentity(o.Id.ToString(),"","",o.SymbolName,o.TradeType==TradeType.Buy?1:-1,
                (decimal)o.VolumeInUnits,0,null,"ACTIVE",Stamp(Server.TimeInUtc)))).ToArray();
            var mappedPositions=positions.Select(p=>new BrokerPositionIdentity(p.Id.ToString(),p.SymbolName,p.TradeType==TradeType.Buy?1:-1,(decimal)p.VolumeInUnits)).ToArray();
            string inventory=System.Text.Json.JsonSerializer.Serialize(new {mappedPositions,Pending=pending.Select(p=>p.Id).OrderBy(x=>x).ToArray()});
            var broker=new BrokerIdentitySnapshot(_accountBinding,Stamp(Server.TimeInUtc),0,Stamp(Server.TimeInUtc),
                inventory==_lastInventory,false,false,mappedOrders,mappedDeals,mappedPositions);
            _lastInventory=inventory;
            // Native deposit/withdrawal and HistoricalTrade monetary facts are
            // available on cTrader Cloud. Rebuild ONLY a stable, entirely flat
            // prospective EUR300 account from these facts, with cash+NET cross-checked against
            // the broker balance. Never interpret history enumeration as proof of
            // complete lifetime deals, or transaction MaxEquity as an upper bound.
            var cashflows=transactions.Select(t=>new BrokerNativeCashflow(
                t.Id.ToString(),Stamp(t.Time),t.Type.ToString().ToUpperInvariant(),
                (decimal)t.Amount,(decimal)t.Balance,
                t.MaxEquity.HasValue?(decimal)t.MaxEquity.Value:null)).ToArray();
            var settlements=closed.Select(t=>new BrokerNativeClosedTrade(
                t.ClosingDealId.ToString(),t.PositionId.ToString(),t.SymbolName,
                Stamp(t.EntryTime),Stamp(t.ClosingTime),(decimal)t.GrossProfit,
                System.Math.Abs((decimal)t.Commissions),(decimal)t.Swap,
                (decimal)t.NetProfit,(decimal)t.Balance)).ToArray();
            string nativeCashFingerprint=System.Text.Json.JsonSerializer.Serialize(new {
                Cash=Account.Balance,Equity=Account.Equity,Credit=Account.Credit,Margin=Account.Margin,
                Positions=positions.Select(p=>new {p.Id,p.SymbolName,p.VolumeInUnits}).OrderBy(x=>x.Id).ToArray(),
                Pending=pending.Select(p=>p.Id).OrderBy(x=>x).ToArray(),
                Cashflows=cashflows.OrderBy(t=>t.Id).ToArray(),
                Closed=settlements.OrderBy(t=>t.ClosingDealId).ToArray()
            });
            bool cashSnapshotStable=nativeCashFingerprint==_lastNativeCashFingerprint && !_transientFault;
            _lastNativeCashFingerprint=nativeCashFingerprint;
            // Position inventory, unlike floating P&L, can remain stable
            // between market observations. Verify this separately from cash.
            // The current monetary mark must still reconcile within its own read.
            string openInventory=System.Text.Json.JsonSerializer.Serialize(positions
                .Select(p=>new {p.Id,p.SymbolName,p.TradeType,p.VolumeInUnits,
                    p.EntryPrice,p.EntryTime,p.StopLoss,p.TakeProfit})
                .OrderBy(p=>p.Id).ToArray());
            bool openInventoryStable=openInventory==_lastNativeOpenInventoryFingerprint && !_transientFault;
            _lastNativeOpenInventoryFingerprint=openInventory;
            BrokerOpenReadbackReport? open=null;
            if(positions.Length>0)
                open=_fundedSession?.ReconcileBrokerOpen(new BrokerOpenReadback(
                    _accountBinding,Stamp(Server.TimeInUtc),openInventoryStable,
                    (decimal)Account.Balance,(decimal)Account.Equity,(decimal)Account.Margin,
                    (decimal)Account.FreeMargin,(decimal)Account.Credit,pending.Length,
                    positions.Select(p=>new BrokerOpenPositionFact(
                        p.Id.ToString(),p.SymbolName,p.TradeType==TradeType.Buy?1:-1,
                        (decimal)p.VolumeInUnits,Stamp(p.EntryTime),(decimal)p.EntryPrice,
                        (decimal)p.Margin,(decimal)p.NetProfit,
                        (decimal?)p.StopLoss,(decimal?)p.TakeProfit)).ToArray()));
            BrokerFlatReadbackReport? flat=null;
            if(cashSnapshotStable && positions.Length==0 && pending.Length==0)
                flat=_fundedSession?.ReconcileBrokerFlat(new BrokerFlatReadback(
                    _accountBinding,Stamp(Server.TimeInUtc),true,
                    (decimal)Account.Balance,(decimal)Account.Equity,(decimal)Account.Margin,
                    (decimal)Account.Credit,positions.Length,pending.Length,cashflows,settlements));
            var funded=_fundedSession?.Observe(broker,(decimal)Account.Balance);
            // Independent native current marks, never inferred from the monetary
            // book or used to certify missing lifetime history/Cloud persistence.
            long riskAt=Stamp(Server.TimeInUtc);
            var riskPositions=positions.Select(p=>new PositionRiskMark(p.Id.ToString(),p.SymbolName,p.TradeType==TradeType.Buy?1:-1,
                (decimal)p.VolumeInUnits,(decimal)p.NetProfit)).ToArray();
            decimal riskCash=(decimal)Account.Balance,riskEquity=(decimal)Account.Equity,riskMargin=(decimal)Account.Margin,
                riskFree=(decimal)Account.FreeMargin,riskCredit=(decimal)Account.Credit;
            var afterRisk=Positions.ToArray();
            bool stableRisk=afterRisk.Length==riskPositions.Length&&riskPositions.All(p=>afterRisk.Any(q=>q.Id.ToString()==p.PositionId&&q.SymbolName==p.Symbol&&
                (decimal)q.VolumeInUnits==p.Units&&(q.TradeType==TradeType.Buy?1:-1)==p.Side));
            long riskAvailable=Stamp(Server.TimeInUtc);
            string riskHash=System.Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(
                System.Text.Json.JsonSerializer.Serialize(new {riskAt,riskCash,riskEquity,riskMargin,riskFree,riskCredit,riskPositions})))).ToLowerInvariant();
            var risk=_fundedSession?.ObservePortfolio(new PortfolioRiskMark(_accountBinding,"BROKER_PLATFORM_OBSERVATION","PLATFORM_MARK_EQUITY",
                riskAt,riskAvailable,riskCash,riskEquity,riskMargin,riskFree,riskCredit,stableRisk,true,riskPositions,
                null,null,null,.01m,riskHash),riskAvailable);

            // Product-level distinction: the original scanner only inspected
            // the chart and held/pending symbols, so it could never discover a
            // candidate on an unheld market. Resolve the configured broker
            // universe independently, retaining ALL existing exposure lanes.
            var universe=NativeResearchUniverse.Resolve(
                ReadOnlyResearchUniverse,SymbolName,
                positions.Select(x=>x.SymbolName).Concat(pending.Select(x=>x.SymbolName))
                    .Concat(_productResearch?.ActiveSymbols ?? System.Array.Empty<string>()),
                name=>Symbols.Exists(name),sweep:_readOnlyUniverseSweep);
            var symbols=universe.Symbols;
            if (ObserveClosedMarketBars) ReportClosedMarketBars(universe.ResearchSymbols);
            // UCP1 observation-only product path: exactly the same C# Core
            // Advance(frame) and EUR300 MODEL ledger as original-source Replay.
            // The independently observed broker inventory, order identities and
            // account type never become model ORDER/FILL/CANCEL facts.
            if(_unifiedPolicy is not null)
            {
                long current=Stamp(Server.TimeInUtc);
                bool fullSession = EnableFullSessionObservation || ObserveStructuralPortfolio;
                long spacing=fullSession?NativeIntegratedLifecycle.IntervalMs:60_000L;
                long at = ObserveStructuralPortfolio
                    ? NativeClosedMarketContext.LatestClock(current, spacing, NativeIntegratedEconomicPolicy.ClockOffsetMs)
                    : current/spacing*spacing+NativeIntegratedEconomicPolicy.ClockOffsetMs;
                if(at<=current && at>_lastUnifiedObservedAt)
                {
                    _lastUnifiedObservedAt=at;
                    var observations=new System.Collections.Generic.List<Ucp1MarketFrame>();
                    var researchNames = fundedActionSymbols ??
                        (_completePolicyObservation ? new[] { "EURUSD", "GBPUSD", "AUDUSD" } :
                            fullSession
                                ? new[] { "EURUSD", "GBPUSD", "XAUUSD", "SpotBrent", "US500", Symbols.Exists("AAPL") ? "AAPL" : "AAPL.US" }
                                : universe.ResearchSymbols);
                    var sourceNames = _unifiedPolicy.ActiveSymbols.Concat(researchNames)
                        .Distinct(System.StringComparer.Ordinal);
                    if (fundedActionSymbols is null) sourceNames = sourceNames.Take(16);
                    foreach(string name in sourceNames)
                    {
                        try
                        {
                            if(!Symbols.Exists(name))continue;
                            if(fullSession)
                            {
                                var integrated=ReadFullSessionMarket(name,at);
                                if(integrated is not null)observations.Add(integrated);
                                continue;
                            }
                            var m=ReadProductResearchMarket(name,at);
                            if(m is null || m.Contract is null)continue;
                            observations.Add(new Ucp1MarketFrame(name,m.Quote,m.Contract,
                                m.M5,m.M15,m.SlippagePerSideQuote,
                                "ACTUAL_CTRADER_PLATFORM_M5_M15_COMPLETED_BARS_BIDASK_ASOF"));
                        }
                        catch(System.Exception)
                        {
                            // Missing any market source does not justify a
                            // fictitious position fill or a session-close claim.
                        }
                    }
                    // Available, causally completed cTrader M15 context
                    // includes no future bar. On both Cloud/Replay only
                    // actually supplied universe returns contribute breadth.
                    var directions=observations.Select(x=>{
                        var z=x.M15.Where(v=>v.CloseAt<at).TakeLast(2).ToArray();
                        return z.Length==2 && z[0].CloseAt==z[1].OpenAt &&
                            at-z[1].CloseAt<=900000L?
                            System.Math.Sign(z[1].Close-z[0].Close):0;
                    }).Where(x=>x!=0).ToArray();
                    decimal currentBreadth=directions.Length>=4?
                        (decimal)directions.Sum()/directions.Length:0m;
                    var productBroker=new Ucp1BrokerFrame(broker,
                        (decimal)Account.Balance,Account.AccountType.ToString());
                    var unified=_unifiedPolicy.Observe(new Ucp1Frame(at,
                        observations.ToArray(),productBroker,currentBreadth));
                    if(unified.ModelBook.CompleteRoundTrips!=_lastUnifiedClosed)
                    {
                        _lastUnifiedClosed=unified.ModelBook.CompleteRoundTrips;
                        Print("MXM unified read-only native policy: modeled completed {0}; held {1}; pending {2}; cash EUR {3}; broker {4}. NOT broker PNL; no orders.",
                            unified.ModelBook.CompleteRoundTrips,unified.Held,
                            unified.Pending,unified.ModelBook.CashEur,
                            unified.BrokerStatus);
                    }
                }
            }
            string universeStatus=universe.Status+"; candidates "+
                universe.ResearchSymbols.Length+"; unavailable "+universe.Unavailable.Length;
            if(universeStatus!=_lastUniverseStatus)
            {
                Print("MXM read-only multiasset product universe: {0}; never an order admission.",universeStatus);
                _lastUniverseStatus=universeStatus;
            }
            // Recover bounded causal feature prefixes from native broker bars
            // without replaying annual research or loading a local checkpoint.
            // Each lane is independent: missing market history cannot suppress
            // ongoing financial monitoring and risk observation.
            long warmupNow=Stamp(Server.TimeInUtc);
            if(warmupNow>=_nextWarmupPollAt)
            {
                // Do not anchor the M5 scanner to an arbitrary cBot start time.
                // Poll the next completed five-minute boundary plus one timer
                // interval; missing bars are measured in the model receipt.
                _nextWarmupPollAt=(warmupNow/300000L+1L)*300000L+15000L;
                // One deterministic bounded slice per completed polling cycle;
                // all held, pending and model positions are still tracked.
                if(_readOnlyUniverseSweep<int.MaxValue)_readOnlyUniverseSweep++;
                else _readOnlyUniverseSweep=0;
                // Priority lane: execute the active M5 strategy observation
                // before the slower rotating full-universe survey, otherwise
                // 32 x 6 background warmups can delay a 5-minute decision.
                // A real product-shaped research path using current cTrader
                // prices, native contract snapshots and completed M5/M15 bars.
                // Simulated fills happen on later observations only; neither
                // this loop nor its core types contains broker order actions.
                long productClock=_integratedResearch?warmupNow/300000L*300000L+1500L:warmupNow;
                if(_productResearch is not null && productClock<=warmupNow &&
                   (!_integratedResearch || (productClock/3600000L%24 is 8 or 9 or 14 or 15 &&
                     new System.DateTimeOffset(System.DateTime.UnixEpoch).AddMilliseconds(productClock).DayOfWeek
                         is not (System.DayOfWeek.Saturday or System.DayOfWeek.Sunday))))
                {
                    try
                    {
                        var inputs=new System.Collections.Generic.List<NativeProductMarket>();
                        if(Account.BrokerName.Contains("Pepperstone",
                            System.StringComparison.OrdinalIgnoreCase))
                        {
                            var active=(_conditionalResearch?NativeConditionalResearch.Universe:_integratedResearch?NativeIntegratedResearch.Universe:_calibratedResearch?(FridayInventoryResearch?"AUDUSD,GBPUSD,NZDUSD,XAUUSD,Copper":
                                "AUDUSD,GBPUSD,NZDUSD,SpotBrent,XAUUSD"):
                                ActiveM5ResearchWatchlist)
                                .Split(new[]{',',';'},System.StringSplitOptions.TrimEntries|
                                    System.StringSplitOptions.RemoveEmptyEntries)
                                .Distinct(System.StringComparer.Ordinal).ToArray();
                            if(active.Length>16 || active.Any(x=>x.Length>64))
                                throw new System.ArgumentException("ACTIVE_M5_WATCHLIST_INVALID_OR_TOO_LARGE");
                            foreach(var name in active
                                .Concat(_productResearch.ActiveSymbols)
                                .Distinct(System.StringComparer.Ordinal))
                            {
                                try
                                {
                                    if(!Symbols.Exists(name))continue;
                                    var symbol=Symbols.GetSymbol(name);
                                    var feas=NativeResearchMarketCapacity.Screen(new(
                                        name,symbol.IsTradingEnabled,symbol.Bid,symbol.Ask,
                                        symbol.VolumeInUnitsMin,
                                        symbol.GetEstimatedMargin(TradeType.Buy,symbol.VolumeInUnitsMin),
                                        symbol.GetEstimatedMargin(TradeType.Sell,symbol.VolumeInUnitsMin)));
                                    // Active signals must have a currently
                                    // plausible minimum-volume funding route.
                                    if(!_calibratedResearch && !feas.EitherDirectionWithinInitial300 &&
                                        !_productResearch.ActiveSymbols.Contains(name))
                                        continue;
                                    var market=ReadProductResearchMarket(name,productClock);
                                    if(market is not null)inputs.Add(market);
                                }
                                catch(System.Exception)
                                {
                                    // Explicitly report missed observation
                                    // later; broker risk monitoring stays live.
                                }
                            }
                        }
                        // Explicitly process every observed clock even when
                        // no valid candidates exist, so missing marks cannot
                        // become fabricated close or profitable executions.
                        var report=_productResearch.Advance(productClock,inputs.ToArray(),
                            EnableUnqualifiedShadowSimulation:!_calibratedResearch);
                        string status=report.ModelClosedRoundTrips+" completed model trips; "+
                            report.AcceptedModelIntents+" conditional research intents; "+
                            report.RejectedIntents+" rejected; cash EUR "+
                            report.ModelCashEur.ToString("0.0000",
                                System.Globalization.CultureInfo.InvariantCulture)+
                            "; sampled floating DD "+
                            (100m*report.ModelMaximumSampledDrawdown).ToString("0.000",
                                System.Globalization.CultureInfo.InvariantCulture)+
                            "%; unobserved M5 slots "+report.ObservedM5SlotsNotScored+
                            "; lag max ms "+report.MaxObservedM5LagMs+
                            "; adverse fully repriced "+report.AdversePathFullyRepriced+
                            "; restart "+report.ContinuityBoundary;
                        if(report.ModelClosedRoundTrips!=_lastResearchModelTrips ||
                            report.LatestSignals.Length>0 ||
                            status!=_lastResearchEconomicStatus)
                        {
                            Print("MXM model-only product research: {0}; no broker NET qualification or orders.",status);
                            _lastResearchModelTrips=report.ModelClosedRoundTrips;
                            _lastResearchEconomicStatus=status;
                        }
                    }
                    catch(System.Exception)
                    {
                        // Broker account cash monitoring remains independent.
                        Print("MXM model-only replay missing current complete market/contract evidence; no broker orders.");
                    }
                }
                int ready=0,total=0,mfaFeatureSlices=0;
                int quoteReady=0,minimumVolumeWithin300=0;
                // Native, account-current terms, not historical fill prices or
                // a 300 EUR funded multi-position portfolio certificate.
                foreach(var candidate in universe.ResearchSymbols)
                {
                    try
                    {
                        var market=Symbols.GetSymbol(candidate);
                        var capacity=NativeResearchMarketCapacity.Screen(new(
                            candidate,market.IsTradingEnabled,
                            market.Bid,market.Ask,market.VolumeInUnitsMin,
                            market.GetEstimatedMargin(TradeType.Buy,market.VolumeInUnitsMin),
                            market.GetEstimatedMargin(TradeType.Sell,market.VolumeInUnitsMin)));
                        if(capacity.QuoteUsable)quoteReady++;
                        if(capacity.EitherDirectionWithinInitial300)minimumVolumeWithin300++;
                    }
                    catch(System.Exception)
                    {
                        // One market's unavailable contract/margin observation
                        // does not suppress account-level cash and risk recovery.
                    }
                }
                var frames=new (TimeFrame Frame,int Minutes,string Name)[]{
                    (TimeFrame.Minute5,5,"M5"),
                    (TimeFrame.Minute15,15,"M15"),(TimeFrame.Minute30,30,"M30"),
                    (TimeFrame.Hour,60,"H1"),
                    (TimeFrame.Hour4,240,"H4"),(TimeFrame.Daily,1440,"D1")};
                foreach(var name in symbols)
                foreach(var frame in frames)
                {
                    total++;
                    try
                    {
                        var bars=MarketData.GetBars(frame.Frame,name);
                        if(bars.Count<NativeCausalWarmup.WindowBars+1)continue;
                        int last=bars.Count-2; // newest bar may still be forming
                        var prefix=new NativeClosedMarketBar[NativeCausalWarmup.WindowBars];
                        for(int j=0;j<prefix.Length;j++)
                        {
                            int i=last-(prefix.Length-1-j);
                            long start=Stamp(bars.OpenTimes[i]);
                            prefix[j]=new NativeClosedMarketBar(start,
                                start+(long)frame.Minutes*60000L,
                                (decimal)bars.OpenPrices[i],(decimal)bars.HighPrices[i],
                                (decimal)bars.LowPrices[i],(decimal)bars.ClosePrices[i],
                                (long)bars.TickVolumes[i]);
                        }
                        if(NativeCausalWarmup.Rebuild(new(name,frame.Name,frame.Minutes,
                            warmupNow,prefix)).Ready)ready++;
                        // The SAME pure Cloud C# feature code is used for
                        // protected Pepperstone/Python parity and compiled cBot.
                        // This is OBSERVATION ONLY. No forecast admission,
                        // native wallet mutation, order placement or cloud launch.
                        if(frame.Minutes==5 && bars.Count>=98)
                        {
                            NativeFamilyBar[] NativePrefix(Bars source)
                            {
                                int end=source.Count-2; // exclude currently forming bar
                                if(end<95)return System.Array.Empty<NativeFamilyBar>();
                                var result=new NativeFamilyBar[96];
                                for(int k=0;k<96;k++)
                                {
                                    int ix=end-95+k;
                                    long closeAt=Stamp(source.OpenTimes[ix])+300000L;
                                    result[k]=new NativeFamilyBar(closeAt,
                                        source.OpenPrices[ix],source.HighPrices[ix],
                                        source.LowPrices[ix],source.ClosePrices[ix],
                                        (long)source.TickVolumes[ix]);
                                }
                                return result;
                            }
                            string peer=name=="US500"?"NAS100":
                                name=="NAS100"?"US500":"";
                            var peerBars=System.Array.Empty<NativeFamilyBar>();
                            if(peer.Length>0)
                            {
                                var peerSource=MarketData.GetBars(TimeFrame.Minute5,peer);
                                if(peerSource.Count>=98)peerBars=NativePrefix(peerSource);
                            }
                            var nativeBars=NativePrefix(bars);
                            long lastClosed=nativeBars[^1].EndAt;
                            // Evaluation never uses the current forming bar.
                            var featureObservation=MultiFamilyNativeFeatures.Evaluate(
                                new NativeFamilyCase(name,peer,lastClosed,nativeBars,peerBars));
                            _=featureObservation.Squeeze+
                              featureObservation.Pullback+
                              featureObservation.VolumeClimax+
                              featureObservation.ReopenGap+
                              featureObservation.IndexDispersion;
                            mfaFeatureSlices++;
                        }
                    }
                    catch(System.Exception)
                    {
                        // Incomplete symbol/timeframe history is a local
                        // observation gap. Retry at the next bounded poll.
                    }
                }

                string warmupStatus=ready+"/"+total+
                    "; market feature slices "+mfaFeatureSlices+
                    "; present-term quotes "+quoteReady+"/"+universe.ResearchSymbols.Length+
                    "; min-volume <=EUR300 single-leg "+minimumVolumeWithin300+
                    " (not jointly funded or cost qualified)";
                if(warmupStatus!=_lastWarmupStatus)
                {
                    Print("MXM native bounded causal feature warmup: {0}; no forecast or orders enabled.",warmupStatus);
                    _lastWarmupStatus=warmupStatus;
                }
            }
            var lanes=symbols.Select(symbol=>new RecoveryLaneEvidence(
                symbol,
                // A price snapshot on another symbol must be checked separately.
                symbol==SymbolName && Symbol.Bid>0 && Symbol.Ask>=Symbol.Bid,
                false, _transientFault, false, false, null, null)).ToArray();
            var snapshot=new RecoveryPortfolioEvidence(
                (decimal)Account.Equity,(decimal)Account.FreeMargin,null,
                // Enumerating native surfaces on a single poll is NOT
                // proof of complete historical in-flight outcome recovery,
                // cashflow reconciliation or certified lifetime equity peak.
                false,false,false,0m,0m,0);
            var result=SelectiveRecovery.Assess(snapshot,lanes);
            var mode=risk?.ReviewReductionIds.Length>0
                ?"PROTECTIVE_RISK_REDUCTION_REVIEW/"+risk.Reason
                :open is not null?open.Status
                :flat?.Adopted==true?flat.Status
                :funded?.Status??result.Status;
            // Missing instance storage is NOT a liveness gate.
            // Flat readback readiness enables causal research/observation only;
            // no certified historic peak or order admission is created.
            if(mode!=_lastMode)
            {
                Print("MXM observation-only recovery: {0}; lanes {1}; native evidence {2}/{3}/{4}/{5}/{6}; orders disabled.",
                    mode,lanes.Length,positions.Length,pending.Length,
                    closed.Length,historicalOrders.Length,transactions.Length);
                _lastMode=mode;
            }
            _transientFault=false; // only the transient observation fault clears
        }
        catch(System.Exception)
        {
            _transientFault=true;
            if(_lastMode!="OBSERVATION_RETRY")
            {
                Print("MXM native observation read unavailable; retry on timer, no orders.");
                _lastMode="OBSERVATION_RETRY";
            }
        }
    }
}
