using System.Text.Json;
using System.Security.Cryptography;

// Locked RRP1 original market study. Only the forecast family changes.
if(args.Length==3 && args[2]=="--native-rrp1")
{
    try
    {
        var bytes=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions {
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(bytes,parse)
            ??throw new ArgumentException("RRP1_EMPTY_SOURCE");
        var universe=new[]{"EURUSD","NAS100","US500","XAUUSD"};
        if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_RRP1_W39_W44" ||
           !source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(universe) ||
           source.Marks.Any(x=>!universe.Contains(x.Symbol,StringComparer.Ordinal)))
            throw new ArgumentException("RRP1_SOURCE_BINDING");
        var tape=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        Mxm.Core.NativeHistoricalMarketReceipt Run(string mode)=>
            Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
                UnqualifiedShadowMode:true,ResearchMode:mode);
        var joint=Run("RRP1_JOINT");
        var equity=Run("RRP1_EQUITY");
        var gold=Run("RRP1_GOLD");
        var adversePeak=300m;
        var sampledAdverseDrawdown=0m;
        foreach(var mark in joint.SampledEquity)
        {
            if(mark.AdverseEquityEur is not decimal value)continue;
            adversePeak=Math.Max(adversePeak,value);
            sampledAdverseDrawdown=Math.Max(sampledAdverseDrawdown,(adversePeak-value)/adversePeak);
        }
        object Summary(Mxm.Core.NativeHistoricalMarketReceipt r)=>new {
            r.CompletedModelRoundTrips,r.ModelClosedCentralNetEur,r.ModelClosedAdverseNetEur,
            r.ModelTripsPerObservedIsoWeek,r.MaximumObservedMarginEur,r.MaximumSampledCentralDrawdown,
            r.OpenModelPositions,r.PendingModelRequests
        };
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Study="RRP1",SourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
            Receipt=joint,OnlyEquity=Summary(equity),OnlyGold=Summary(gold),
            GoldMarginalCentralEur=joint.ModelClosedCentralNetEur-equity.ModelClosedCentralNetEur,
            GoldMarginalAdverseEur=joint.ModelClosedAdverseNetEur-equity.ModelClosedAdverseNetEur,
            EquityMarginalCentralEur=joint.ModelClosedCentralNetEur-gold.ModelClosedCentralNetEur,
            EquityMarginalAdverseEur=joint.ModelClosedAdverseNetEur-gold.ModelClosedAdverseNetEur,
            MissingAdverseMarks=joint.SampledEquity.Count(x=>!x.AdverseEquityEur.HasValue),
            SampledAdverseDrawdown=sampledAdverseDrawdown,
            CashResetBetweenWeeks=false,Qualification="EXPOSED_SHADOW_REPLAY_ONLY",
            ExpectedWeeks=new[]{"2026-W39","2026-W40","2026-W41","2026-W42","2026-W43","2026-W44"}
        }));
        return 0;
    }
    catch(Exception ex)
    {
        Console.Error.WriteLine("RRP1_NATIVE_REPLAY_REJECTED:"+ex.GetType().Name);
        return 66;
    }
}

// Locked LDP1 original market study. Only the forecast family changes.
if(args.Length==3 && args[2] is ("--native-ldp1" or "--native-ldp1-contracts"))
{
    string stage="input";
    try
    {
        var bytes=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions {
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        if(args[2]=="--native-ldp1-contracts")
        {
            var contracts=JsonSerializer.Deserialize<Mxm.Core.NativeObservedContractTerms[]>(bytes,parse)
                ??throw new ArgumentException("LDP1_CONTRACTS_EMPTY");
            foreach(var contract in contracts)
            {
                stage=contract.Symbol switch {
                    "AUDUSD"=>"AUDUSD", "EURUSD"=>"EURUSD", "NZDUSD"=>"NZDUSD", "XAGUSD"=>"XAGUSD",
                    _=>"unknown-symbol"
                };
                Mxm.Core.NativeBrokerContractCosts.Validate(contract,contract.MinimumUnits);
            }
            File.WriteAllText(args[1],"{}");
            return 0;
        }
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(bytes,parse)
            ??throw new ArgumentException("LDP1_EMPTY_SOURCE");
        var universe=new[]{"AUDUSD","EURUSD","NZDUSD","XAGUSD"};
        if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_LDP1_W26_W30" ||
           !source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(universe) ||
           source.Marks.Any(x=>!universe.Contains(x.Symbol,StringComparer.Ordinal)))
            throw new ArgumentException("LDP1_SOURCE_BINDING");
        stage="quote-adapter";
        var tape=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        Mxm.Core.NativeHistoricalMarketReceipt Run(string mode)
        {
            stage=mode;
            return Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
                UnqualifiedShadowMode:true,ResearchMode:mode);
        }
        var joint=Run("LDP1_JOINT");
        var fx=Run("LDP1_FX");
        var silver=Run("LDP1_SILVER");
        var alwaysLong=Run("LDP1_LONG");
        var alwaysShort=Run("LDP1_SHORT");
        var adversePeak=300m;
        var sampledAdverseDrawdown=0m;
        foreach(var mark in joint.SampledEquity)
        {
            if(mark.AdverseEquityEur is not decimal value)continue;
            adversePeak=Math.Max(adversePeak,value);
            sampledAdverseDrawdown=Math.Max(sampledAdverseDrawdown,(adversePeak-value)/adversePeak);
        }
        object Summary(Mxm.Core.NativeHistoricalMarketReceipt r)=>new {
            r.CompletedModelRoundTrips,r.ModelClosedCentralNetEur,r.ModelClosedAdverseNetEur,
            r.ModelTripsPerObservedIsoWeek,r.MaximumObservedMarginEur,r.MaximumSampledCentralDrawdown,
            r.OpenModelPositions,r.PendingModelRequests
        };
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Study="LDP1",SourceSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
            Receipt=joint,OnlyFx=Summary(fx),OnlySilver=Summary(silver),
            FundedLong=Summary(alwaysLong),FundedShort=Summary(alwaysShort),
            SilverMarginalCentralEur=joint.ModelClosedCentralNetEur-fx.ModelClosedCentralNetEur,
            SilverMarginalAdverseEur=joint.ModelClosedAdverseNetEur-fx.ModelClosedAdverseNetEur,
            FxMarginalCentralEur=joint.ModelClosedCentralNetEur-silver.ModelClosedCentralNetEur,
            FxMarginalAdverseEur=joint.ModelClosedAdverseNetEur-silver.ModelClosedAdverseNetEur,
            MissingAdverseMarks=joint.SampledEquity.Count(x=>!x.AdverseEquityEur.HasValue),
            SampledAdverseDrawdown=sampledAdverseDrawdown,
            CashResetBetweenWeeks=false,Qualification="EXPOSED_SHADOW_REPLAY_ONLY",
            ExpectedWeeks=new[]{"2026-W26","2026-W27","2026-W28","2026-W29","2026-W30"}
        }));
        return 0;
    }
    catch(Exception ex)
    {
        var reason=System.Text.RegularExpressions.Regex.IsMatch(ex.Message,@"\A[A-Z][A-Z0-9_]{2,100}\z")
            ?ex.Message:ex.GetType().Name;
        Console.Error.WriteLine("LDP1_NATIVE_REPLAY_REJECTED:"+stage+":"+reason);
        return 66;
    }
}

// Original Pepperstone SOURCE-FROZEN SpotBrent / AMD.US W42-W43 multiclass
// economic development, using existing NativeHistoricalProductReplay.
// Never orders, never Cloud, no unexposed confirmation or historic fee certification.
if(args.Length==3 && args[2]=="--native-original-openapi-brent-amd-w42w43")
{
    try
    {
        var bytes=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions{
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            bytes,parse)??throw new ArgumentException("BRENT_AMD_W42W43_EMPTY_SOURCE");
        if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_OPENAPI_2026_W42_W43_BRENT_AMD_PREDECLARED"||
           !source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
               .SequenceEqual(new[]{"AMD.US","EURUSD","SpotBrent"})||
           source.Marks.Any(x=>!new[]{"AMD.US","EURUSD","SpotBrent"}
               .Contains(x.Symbol,StringComparer.Ordinal)))
            throw new ArgumentException("BRENT_AMD_W42W43_UNAUTHORISED_SYMBOL_OR_SOURCE");
        var tape=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        var joint=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"BRENT_AMD_JOINT_W42W43");
        var onlyHk=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"ONLY_BRENT_W42W43");
        var onlyBrent=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"ONLY_AMD_W42W43");
        var chronology=joint.SampledEquity.GroupBy(x=>{
            var d=DateTimeOffset.FromUnixTimeMilliseconds(x.At).UtcDateTime;
            return System.Globalization.ISOWeek.GetYear(d)+"-W"+
                System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
        }).OrderBy(x=>x.Key,StringComparer.Ordinal).Select(g=>{
            var first=g.First();var last=g.Last();
            return new {
                Week=g.Key,FirstSampleAtMs=first.At,LastSampleAtMs=last.At,
                SampledCentralEquityChangeEur=
                    last.CentralEquityEur-first.CentralEquityEur,
                SampledAdverseEquityChangeEur=
                    last.AdverseEquityEur-first.AdverseEquityEur,
                FirstSampledCentralEquityEur=first.CentralEquityEur,
                LastSampledCentralEquityEur=last.CentralEquityEur,
                FirstSampledAdverseEquityEur=first.AdverseEquityEur,
                LastSampledAdverseEquityEur=last.AdverseEquityEur,
                ModelCompletedRoundTripsCumulative=last.ClosedModelRoundTrips,
                NoCashReset=true,NotIndependentConfirmation=true
            };
        }).ToArray();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Protocol="research/brent_amd_w42_w43_protocol.json",
            Window="2026_W42_W43_EXPOSED_BRENT_AMD_MULTI_CLASS_RESEARCH_NOT_CONFIRMATION",
            OriginalMarketSourceSha256=Convert.ToHexString(
                SHA256.HashData(bytes)).ToLowerInvariant(),
            Receipt=joint,ChronologicalWeeklySampledEconomics=chronology,
            FundedAblations=new {
                OnlyBrentDrivePullback=onlyHk,
                OnlyAMDLateCashBreakout=onlyBrent,
                MarginalBrentNetEur=
                    joint.ModelClosedCentralNetEur-onlyBrent.ModelClosedCentralNetEur,
                MarginalAMDNetEur=
                    joint.ModelClosedCentralNetEur-onlyHk.ModelClosedCentralNetEur,
                SeparateFullEUR300AblationsNeverSummed=true,
                IndependentSupportClaimed=false
            },
            DirectionalBenchmarks=new {
                FlatCashEur=0m,
                JointMatchedLongNetEur=joint.MatchedLongBenchmarkNetEur,
                JointMatchedShortNetEur=joint.MatchedShortBenchmarkNetEur,
                JointOppositeSignalNetEur=joint.MatchedOppositeSignalBenchmarkNetEur,
                IncrementalVsBestLongShortFlat=joint.IncrementalVsBestConstantSideEur,
                IncrementalVsOppositeSignal=joint.IncrementalVsOppositeSignalEur,
                EntryExitClocksAndSelectedVolumeMatched=true,
                NeverExtraCapitalWallet=true
            },
            EURUSDConversionContextOnly=true,
            CurrentContractObservedAtMs=source.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            FirstHistoricalQuoteAtMs=source.Marks.Min(x=>x.At),
            CurrentTermsAppliedRetrospectively=
                source.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            NoHistoricalCommissionContinuityCertified=true,
            BrokerNetCertified=false,IndependentConfirmation=false,
            ContinuousDrawdownCertified=false,OriginalBrokerFill=false,
            OrdersSubmitted=0,CloudActivated=false
        }));
        return 0;
    }
    catch(Exception ex)
    {
        Console.Error.WriteLine("BRENT_AMD_W42W43_NATIVE_REPLAY_REJECTED:"+
            ex.GetType().Name);
        return 60;
    }
}

// Original Pepperstone SOURCE-FROZEN HK50 / SpotBrent W40-W41 multiclass
// economic development, using existing NativeHistoricalProductReplay.
// Never orders, never Cloud, no unexposed confirmation or historic fee certification.
if(args.Length==3 && args[2]=="--native-original-openapi-hk50-spotbrent-w40w41")
{
    try
    {
        var bytes=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions{
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            bytes,parse)??throw new ArgumentException("HK_BRENT_W40W41_EMPTY_SOURCE");
        if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_OPENAPI_2026_W40_W41_HK_BRENT_PREDECLARED"||
           !source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
               .SequenceEqual(new[]{"EURUSD","HK50","SpotBrent"})||
           source.Marks.Any(x=>!new[]{"EURUSD","HK50","SpotBrent"}
               .Contains(x.Symbol,StringComparer.Ordinal)))
            throw new ArgumentException("HK_BRENT_W40W41_UNAUTHORISED_SYMBOL_OR_SOURCE");
        var tape=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        var joint=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"HK_BRENT_JOINT_W40W41");
        var onlyHk=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"HK_ONLY_W40W41");
        var onlyBrent=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"BRENT_ONLY_W40W41");
        var chronology=joint.SampledEquity.GroupBy(x=>{
            var d=DateTimeOffset.FromUnixTimeMilliseconds(x.At).UtcDateTime;
            return System.Globalization.ISOWeek.GetYear(d)+"-W"+
                System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
        }).OrderBy(x=>x.Key,StringComparer.Ordinal).Select(g=>{
            var first=g.First();var last=g.Last();
            return new {
                Week=g.Key,FirstSampleAtMs=first.At,LastSampleAtMs=last.At,
                SampledCentralEquityChangeEur=
                    last.CentralEquityEur-first.CentralEquityEur,
                SampledAdverseEquityChangeEur=
                    last.AdverseEquityEur-first.AdverseEquityEur,
                FirstSampledCentralEquityEur=first.CentralEquityEur,
                LastSampledCentralEquityEur=last.CentralEquityEur,
                FirstSampledAdverseEquityEur=first.AdverseEquityEur,
                LastSampledAdverseEquityEur=last.AdverseEquityEur,
                ModelCompletedRoundTripsCumulative=last.ClosedModelRoundTrips,
                NoCashReset=true,NotIndependentConfirmation=true
            };
        }).ToArray();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Protocol="research/hk50_spotbrent_w40_w41_protocol.json",
            Window="2026_W40_W41_EXPOSED_HK_INDEX_BRENT_EU_RESEARCH_NOT_CONFIRMATION",
            OriginalMarketSourceSha256=Convert.ToHexString(
                SHA256.HashData(bytes)).ToLowerInvariant(),
            Receipt=joint,ChronologicalWeeklySampledEconomics=chronology,
            FundedAblations=new {
                OnlyHK50OpenRangeReversal=onlyHk,
                OnlySpotBrentEuExpansion=onlyBrent,
                MarginalHK50NetEur=
                    joint.ModelClosedCentralNetEur-onlyBrent.ModelClosedCentralNetEur,
                MarginalSpotBrentNetEur=
                    joint.ModelClosedCentralNetEur-onlyHk.ModelClosedCentralNetEur,
                SeparateFullEUR300AblationsNeverSummed=true,
                IndependentSupportClaimed=false
            },
            DirectionalBenchmarks=new {
                FlatCashEur=0m,
                JointMatchedLongNetEur=joint.MatchedLongBenchmarkNetEur,
                JointMatchedShortNetEur=joint.MatchedShortBenchmarkNetEur,
                JointOppositeSignalNetEur=joint.MatchedOppositeSignalBenchmarkNetEur,
                IncrementalVsBestLongShortFlat=joint.IncrementalVsBestConstantSideEur,
                IncrementalVsOppositeSignal=joint.IncrementalVsOppositeSignalEur,
                EntryExitClocksAndSelectedVolumeMatched=true,
                NeverExtraCapitalWallet=true
            },
            EURUSDConversionContextOnly=true,
            CurrentContractObservedAtMs=source.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            FirstHistoricalQuoteAtMs=source.Marks.Min(x=>x.At),
            CurrentTermsAppliedRetrospectively=
                source.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            NoHistoricalCommissionContinuityCertified=true,
            BrokerNetCertified=false,IndependentConfirmation=false,
            ContinuousDrawdownCertified=false,OriginalBrokerFill=false,
            OrdersSubmitted=0,CloudActivated=false
        }));
        return 0;
    }
    catch(Exception ex)
    {
        Console.Error.WriteLine("HK_BRENT_W40W41_NATIVE_REPLAY_REJECTED:"+
            ex.GetType().Name);
        return 60;
    }
}

// Original read-only Pepperstone NatGas/AUDUSD research. New mechanisms are
// preregistered in natgas_audusd_w38_w39_protocol.json before ANY source request.
// Existing C# NativeHistoricalProductReplay: one shared EUR300 model capital,
// three fully funded ablations; no historical broker fill or tariff certification.
if(args.Length==3 && args[2]=="--native-original-openapi-natgas-audusd-w38w39")
{
    try
    {
        var bytes=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions {
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            bytes,parse)??throw new ArgumentException("NG_AUD_W38W39_EMPTY_SOURCE");
        if(source.SourceLabel!="ORIGINAL_PEPPERSTONE_OPENAPI_2026_W38_W39_NG_AUD_PREDECLARED"||
           !source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
                .SequenceEqual(new[]{"AUDUSD","EURUSD","NatGas"})||
           source.Marks.Any(x=>!new[]{"AUDUSD","EURUSD","NatGas"}
                .Contains(x.Symbol,StringComparer.Ordinal)))
            throw new ArgumentException("NG_AUD_W38W39_UNAUTHORISED_SYMBOL_OR_SOURCE");
        var tape=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        var joint=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"NG_AUD_JOINT_W38W39");
        var onlyNg=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"NG_ONLY_W38W39");
        var onlyAud=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"AUD_ONLY_W38W39");
        var chronology=joint.SampledEquity.GroupBy(x=>{
            var d=DateTimeOffset.FromUnixTimeMilliseconds(x.At).UtcDateTime;
            return System.Globalization.ISOWeek.GetYear(d)+"-W"+
                System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
        }).OrderBy(x=>x.Key,StringComparer.Ordinal).Select(g=>{
            var first=g.First();var last=g.Last();
            return new {
                Week=g.Key,FirstSampleAtMs=first.At,LastSampleAtMs=last.At,
                FirstSampledCentralEquityEur=first.CentralEquityEur,
                LastSampledCentralEquityEur=last.CentralEquityEur,
                SampledCentralEquityChangeEur=
                    last.CentralEquityEur-first.CentralEquityEur,
                FirstSampledAdverseEquityEur=first.AdverseEquityEur,
                LastSampledAdverseEquityEur=last.AdverseEquityEur,
                SampledAdverseEquityChangeEur=
                    last.AdverseEquityEur-first.AdverseEquityEur,
                ModelCompletedRoundTripsCumulative=last.ClosedModelRoundTrips,
                NoCashReset=true,NotIndependentConfirmation=true
            };
        }).ToArray();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Protocol="research/natgas_audusd_w38_w39_protocol.json",
            Window="2026_W38_W39_EXPOSED_NEW_MULTICLASS_DEVELOPMENT_NOT_CONFIRMATION",
            OriginalMarketSourceSha256=Convert.ToHexString(
                SHA256.HashData(bytes)).ToLowerInvariant(),
            Receipt=joint,
            ChronologicalWeeklySampledEconomics=chronology,
            FundedAblations=new {
                OnlyNatGasCompression=onlyNg,
                OnlyAUDUSDAsiaSweep=onlyAud,
                MarginalNatGasNetEur=
                    joint.ModelClosedCentralNetEur-onlyAud.ModelClosedCentralNetEur,
                MarginalAUDUSDNetEur=
                    joint.ModelClosedCentralNetEur-onlyNg.ModelClosedCentralNetEur,
                SeparateFullEUR300AblationsNeverSummed=true,
                IndependentSupportClaimed=false
            },
            DirectionalBenchmarks=new {
                CashEur=0m, JointMatchedLongNetEur=joint.MatchedLongBenchmarkNetEur,
                JointMatchedShortNetEur=joint.MatchedShortBenchmarkNetEur,
                JointOppositeEachSignalNetEur=joint.MatchedOppositeSignalBenchmarkNetEur,
                IncrementalVsBestConstantSideEur=joint.IncrementalVsBestConstantSideEur,
                IncrementalVsOppositeSignalEur=joint.IncrementalVsOppositeSignalEur,
                SameFundedSignalEntryExitClocksAndUnits=true,
                DescriptiveUnfundedCounterfactualsNeverIndependentWallets=true
            },
            EURUSDConversionContextOnly=true,
            FirstHistoricalQuoteAtMs=source.Marks.Min(x=>x.At),
            CurrentBrokerContractFirstObservedMs=
                source.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            CurrentContractTermsRetrospectivelyApplied=
                source.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            NoHistoricalCommissionContinuityCertified=true,
            BrokerNetCertified=false,IndependentConfirmation=false,
            BrokerOrderFillsCertified=false,OriginalBrokerSourceOnlyInCollector=true,
            OrdersSubmitted=0,CloudActivated=false
        }));
        return 0;
    }
    catch(Exception ex)
    {
        Console.Error.WriteLine("NG_AUD_W38W39_NATIVE_REPLAY_REJECTED:"+
            ex.GetType().Name);
        return 59;
    }
}


// US indices research, preregistered BEFORE original Pepperstone W20/W21
// historical read-only requests. No orders, Cloud activation, or historic
// commission continuity claim. One original-funded EUR300 ledger per replay.
if(args.Length==3 && (args[2]=="--native-original-openapi-us-index-w20w21" ||
    args[2]=="--native-original-openapi-nas100-w32w33"))
{
    try
    {
        // Only the historical dates and source label differ. The existing
        // frozen W20/W21 signal, session, benchmark and funded selector are
        // called unchanged. This new window is NOT an independent holdout.
        bool frozenReplication=args[2]=="--native-original-openapi-nas100-w32w33";
        var bytes=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions {
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            bytes,parse)??throw new ArgumentException("INDEX_W20W21_EMPTY_SOURCE");
        if(source.SourceLabel!=
            (frozenReplication ?
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W32_W33_NAS_REPLICATION_EXPOSED" :
              "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W20_W21_US_INDEX_PREDECLARED")||
           !source.Bars.Select(x=>x.Symbol)
                .OrderBy(x=>x,StringComparer.Ordinal)
                .SequenceEqual(new[]{"EURUSD","NAS100","US500"})||
           source.Marks.Any(x=>!new[]{"EURUSD","NAS100","US500"}
                .Contains(x.Symbol,StringComparer.Ordinal)))
            throw new ArgumentException("INDEX_W20W21_UNAUTHORISED_SYMBOL_OR_SOURCE");
        var tape=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        var joint=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"US_INDEX_JOINT_W20W21");
        var onlyNas=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"US_INDEX_NAS_ONLY_W20W21");
        var onlySp=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"US_INDEX_SP_ONLY_W20W21");
        var chronology=joint.SampledEquity.GroupBy(x=>{
            var d=DateTimeOffset.FromUnixTimeMilliseconds(x.At).UtcDateTime;
            return System.Globalization.ISOWeek.GetYear(d)+"-W"+
                System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
        }).OrderBy(x=>x.Key,StringComparer.Ordinal).Select(g=>{
            var first=g.First();var last=g.Last();
            return new {
                Week=g.Key,FirstSampleAtMs=first.At,LastSampleAtMs=last.At,
                FirstSampledCentralEquityEur=first.CentralEquityEur,
                LastSampledCentralEquityEur=last.CentralEquityEur,
                SampledCentralEquityChangeEur=
                    last.CentralEquityEur-first.CentralEquityEur,
                FirstSampledAdverseEquityEur=first.AdverseEquityEur,
                LastSampledAdverseEquityEur=last.AdverseEquityEur,
                SampledAdverseEquityChangeEur=
                    last.AdverseEquityEur-first.AdverseEquityEur,
                ModelCompletedRoundTripsCumulative=last.ClosedModelRoundTrips,
                NoCashReset=true,NotIndependentConfirmation=true
            };
        }).ToArray();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Protocol=(frozenReplication ?
                "research/nas100_frozen_w32_w33_replication_protocol.json" :
                "research/us_index_w20_w21_protocol.json"),
            Window=(frozenReplication ?
                "2026_W32_W33_EXPOSED_FROZEN_REPLICATION_NOT_INDEPENDENT" :
                "2026_W20_W21_EXPOSED_DEVELOPMENT_SELECTION_NOT_CONFIRMATION"),
            FrozenOriginalW20W21NasAndUS500Logic=true,
            FixedSessionUtc="14:30–19:00 UTC; in US summer DST this is post-open, NOT the NYSE open",
            OriginalMarketSourceSha256=Convert.ToHexString(
                SHA256.HashData(bytes)).ToLowerInvariant(),
            Receipt=joint,
            ChronologicalWeeklySampledEconomics=chronology,
            FundedAblations=new {
                OnlyNAS100RelativeDispersion=onlyNas,
                OnlyUS500H1VolatilityPersistence=onlySp,
                MarginalNAS100NetEur=
                    joint.ModelClosedCentralNetEur-onlySp.ModelClosedCentralNetEur,
                MarginalUS500NetEur=
                    joint.ModelClosedCentralNetEur-onlyNas.ModelClosedCentralNetEur,
                SeparateFullEUR300AblationsNeverSummed=true,
                ClaimedIndependentEconomicSupport=false
            },
            EURUSDConversionContextOnly=true,
            CurrentBrokerContractFirstObservedMs=
                source.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            FirstHistoricalQuoteAtMs=source.Marks.Min(x=>x.At),
            CurrentContractTermsRetrospectivelyApplied=
                source.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            NoHistoricalCommissionContinuityCertified=true,
            BrokerNetCertified=false,IndependentConfirmation=false,
            BrokerOrderFillsCertified=false,OriginalBrokerSourceOnlyInCollector=true,
            OrdersSubmitted=0,CloudActivated=false
        }));
        return 0;
    }
    catch(Exception ex)
    {
        Console.Error.WriteLine("US_INDEX_W20W21_NATIVE_REPLAY_REJECTED:"+
            ex.GetType().Name);
        return 58;
    }
}

// Preregistered W24/W25 ETHUSD wick/SpotCrude session-tick economics.
// Same existing original read-only Pepperstone adapter and EUR300 funded
// NativeHistoricalProductReplay, never trading orders or Cloud activation.
if(args.Length==3 && args[2]=="--native-original-openapi-crypto-crude-w24w25")
{
    try
    {
        var bytes=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions {
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var original=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            bytes,parse)??throw new ArgumentException("CRYPTO_CRUDE_SOURCE_NULL");
        if(original.SourceLabel!=
            "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W24_W25_CRYPTO_CRUDE_PREDECLARED"||
           !original.Bars.Select(x=>x.Symbol)
                .OrderBy(x=>x,StringComparer.Ordinal)
                .SequenceEqual(new[]{"ETHUSD","EURUSD","SpotCrude"})||
           original.Marks.Any(x=>!new[]{"ETHUSD","EURUSD","SpotCrude"}
                .Contains(x.Symbol,StringComparer.Ordinal)))
            throw new ArgumentException("CRYPTO_CRUDE_SOURCE_PROTOCOL_MISMATCH");
        var tape=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(original);
        var joint=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"CRYPTO_CRUDE_W24W25");
        var onlyCrypto=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"ONLY_CRYPTO_W24W25");
        var onlyCrude=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:true,ResearchMode:"ONLY_CRUDE_W24W25");
        var weeks=joint.SampledEquity.GroupBy(x=>{
            var d=DateTimeOffset.FromUnixTimeMilliseconds(x.At).UtcDateTime;
            return System.Globalization.ISOWeek.GetYear(d)+"-W"+
                System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
        }).OrderBy(g=>g.Key,StringComparer.Ordinal).Select(g=>{
            var first=g.First();var last=g.Last();
            return new{
                Week=g.Key,FirstMarkAtMs=first.At,LastMarkAtMs=last.At,
                FirstSampledEquityEur=first.CentralEquityEur,
                LastSampledEquityEur=last.CentralEquityEur,
                WeekSampledEquityDifferenceEur=
                    last.CentralEquityEur-first.CentralEquityEur,
                FirstAdverseSampledEquityEur=first.AdverseEquityEur,
                LastAdverseSampledEquityEur=last.AdverseEquityEur,
                WeekSampledAdverseDifferenceEur=
                    last.AdverseEquityEur-first.AdverseEquityEur,
                CumulativeCompleteModelRoundTrips=last.ClosedModelRoundTrips,
                IndependentConfirmation=false,SingleBookNoCashReset=true
            };
        }).ToArray();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new{
            Protocol="research/crypto_crude_w24_w25_protocol.json",
            Window="2026-W24_W25_GLOBALLY_EXPOSED_DEV_SELECTION_NOT_INDEPENDENT",
            OriginalSourceSha256=Convert.ToHexString(
                SHA256.HashData(bytes)).ToLowerInvariant(),
            OriginalSourceAuthenticationOnlyCollector=true,
            BrokerHistoricTariffContinuityCertified=false,
            EURUSDReferenceIsNotTraded=true,
            JointReceipt=joint,
            // Python public receipt maps this exact stable field name.
            Receipt=joint,
            ChronologicalWeeklyMarks=weeks,
            FundedAblations=new {
                OnlyETHUSDWick=onlyCrypto,
                OnlySpotCrudeSessionDrift=onlyCrude,
                MarginalETHUSDWickNetEur=
                    joint.ModelClosedCentralNetEur-onlyCrude.ModelClosedCentralNetEur,
                MarginalSpotCrudeSessionNetEur=
                    joint.ModelClosedCentralNetEur-onlyCrypto.ModelClosedCentralNetEur,
                OneJointEUR300ModelNeverSumOfAblationWallets=true,
                AllAblationsEUR300IsolatedCounterfactualOnly=true,
                ClaimedIndependentEconomicSupport=false
            },
            CurrentBrokerContractFirstObservedAtMs=
                original.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            FirstOriginalPriceMarkMs=original.Marks.Min(x=>x.At),
            ContractTermsAppliedRetrospectively=
                original.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            HistoricalFillsModeledNotReal=true,
            BrokerNetCertified=false,IndependentConfirmation=false,
            OrdersSubmitted=0,CloudActivated=false
        }));
        return 0;
    }
    catch(Exception e)
    {
        Console.Error.WriteLine("ORIGINAL_CRYPTO_CRUDE_REPLAY_REJECTED:"+
            e.GetType().Name);
        return 58;
    }
}

// Cross-asset W30/W31 economic research, registered before source results.
// Reuses EXISTING original historical converter and native EUR300 funded
// portfolio; never broker orders, Cloud, invented DOM, or recycled closed
// W36/W37 / W45 research models.
if(args.Length==3 && args[2]=="--native-original-openapi-energy-equity-w30w31")
{
    try
    {
        var bytes=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions{
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            bytes,parse)??throw new ArgumentException("CROSS_ASSET_SOURCE_NULL");
        if(source.SourceLabel!=
            "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W30_W31_ENERGY_EQUITY_PREDECLARED" ||
           !source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
               .SequenceEqual(new[]{"AMD.US","EURUSD","SpotBrent","SpotCrude"}) ||
           source.Marks.Any(x=>!new[]{"AMD.US","EURUSD","SpotBrent","SpotCrude"}
                .Contains(x.Symbol,StringComparer.Ordinal)))
            throw new ArgumentException("CROSS_ASSET_SOURCE_OR_UNIVERSE_MISMATCH");
        var native=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        var joint=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"CROSS_OIL_EQUITY_W30W31");
        var onlyOil=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"CROSS_ONLY_OIL_W30W31");
        var onlyEquity=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"CROSS_ONLY_EQUITY_W30W31");
        var weeks=joint.SampledEquity
            .GroupBy(x=>{
                var d=DateTimeOffset.FromUnixTimeMilliseconds(x.At).UtcDateTime;
                return System.Globalization.ISOWeek.GetYear(d)+"-W"+
                    System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
            })
            .OrderBy(g=>g.Key,StringComparer.Ordinal)
            .Select(g=>{
                var a=g.First();var b=g.Last();
                return new {
                    Week=g.Key,FirstAtUtcMs=a.At,LastAtUtcMs=b.At,
                    FirstSampledEquityEur=a.CentralEquityEur,
                    LastSampledEquityEur=b.CentralEquityEur,
                    ObservedSampledEquityChangeEur=b.CentralEquityEur-a.CentralEquityEur,
                    FirstSampledAdverseEquityEur=a.AdverseEquityEur,
                    LastSampledAdverseEquityEur=b.AdverseEquityEur,
                    ObservedSampledAdverseEquityChangeEur=
                        b.AdverseEquityEur-a.AdverseEquityEur,
                    ModelCompletedTripsCumulative=b.ClosedModelRoundTrips,
                    WeekCashNotReset=true,IndependentConfirmation=false
                };
            }).ToArray();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Protocol="research/cross_asset_energy_equity_w30_w31_protocol.json",
            SourceWindow="W30_DEVELOPMENT_W31_CHRONOLOGICAL_SELECTION_GLOBALLY_EXPOSED",
            ConversionReferenceEurusdNotTradingCandidate=true,
            BrokerTermsRetrospectiveScenariosNotHistoricalGuarantee=true,
            SourceAuthenticationOnlyInProtectedCollector=true,
            InputSha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
            Receipt=joint,ChronologicalWeeks=weeks,
            FundedAblations=new {
                OnlySpotCrudeBrentLeadLag=onlyOil,
                OnlyAmdOpeningSessionFlow=onlyEquity,
                MarginalEnergyLeadLagNetEur=joint.ModelClosedCentralNetEur-
                    onlyEquity.ModelClosedCentralNetEur,
                MarginalAmdSessionFlowNetEur=joint.ModelClosedCentralNetEur-
                    onlyOil.ModelClosedCentralNetEur,
                SeparateFullEUR300AbalationsNotSimultaneouslyFunded=true,
                ClaimedIndependentConfirmation=false
            },
            HistoricClockFirstUtcMs=source.Marks.Min(x=>x.At),
            ContractFirstObservedUtcMs=source.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            ContractTermsAppliedRetrospectively=
                source.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            ActualBrokerFills=false,PriceSlippageModeled=true,
            EUR300ModelOnly=true,OrdersSubmitted=0,CloudActivated=false
        }));
        return 0;
    }
    catch(Exception e)
    {
        Console.Error.WriteLine("CROSS_ASSET_NATIVE_REPLAY_REJECTED:"+
            e.GetType().Name);
        return 58;
    }
}

// Original-account historical W36/W37 source, protocol locked before
// acquisition. Replays existing single EUR300 native ledger per experiment
// with NO cash resets at the W36/W37 split, NO broker orders, NO Cloud.
// W45 exact frozen shock is replicated unchanged; tick-volume absorption is
// a novel preregistered mechanistic candidate, no data-derived thresholds.
if(args.Length==3 && args[2]=="--native-original-openapi-historic-w36w37")
{
    try
    {
        var input=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions{
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            input,parse)??throw new ArgumentException("HISTORICAL_W36W37_TAPE_NULL");
        if(source.SourceLabel!=
           "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W36_W37_FX_M5_SHOCK_TICKFLOW_PREDECLARED" ||
           source.Bars.Select(x=>x.Symbol).OrderBy(x=>x,StringComparer.Ordinal)
               .SequenceEqual(new[]{"AUDUSD","EURUSD","GBPUSD","NZDUSD"})==false)
            throw new ArgumentException("HISTORICAL_W36W37_PROTOCOL_UNIVERSE_MISMATCH");
        var native=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        var joint=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"FX_SHOCK_ABSORPTION_W36W37");
        var onlyShock=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"FX_ONLY_SHOCK_W36W37");
        var onlyAbsorption=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"FX_ONLY_ABSORPTION_W36W37");
        var weeks=joint.SampledEquity
            .GroupBy(x=>{
                var d=DateTimeOffset.FromUnixTimeMilliseconds(x.At).UtcDateTime;
                return System.Globalization.ISOWeek.GetYear(d)+"-W"+
                    System.Globalization.ISOWeek.GetWeekOfYear(d).ToString("00");
            })
            .OrderBy(g=>g.Key,StringComparer.Ordinal)
            .Select(g=>{
                var a=g.First();var b=g.Last();
                return new {
                    Week=g.Key,FirstObservedAtMs=a.At,LastObservedAtMs=b.At,
                    FirstEquityEur=a.CentralEquityEur,LastEquityEur=b.CentralEquityEur,
                    SampledEquityChangeEur=b.CentralEquityEur-a.CentralEquityEur,
                    FirstAdverseEquityEur=a.AdverseEquityEur,
                    LastAdverseEquityEur=b.AdverseEquityEur,
                    SampledAdverseEquityChangeEur=b.AdverseEquityEur-a.AdverseEquityEur,
                    LastCompletedRoundTripsCumulative=b.ClosedModelRoundTrips,
                    NoCashResetAtBoundary=true,
                    IsIndependentConfirmation=false
                };
            }).ToArray();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Protocol="research/fx_historical_w36_w37_protocol.json",
            Window="2026-W36_DEVELOPMENT_W37_SELECTION_GLOBALLY_EXPOSED",
            IndependentConfirmation=false,FutureW46NotScored=true,
            InputFileSha256=Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant(),
            Receipt=joint,ChronologicalWeeklySampledEconomics=weeks,
            CounterfactualAblation=new {
                OnlyFrozenW45Shock=onlyShock,
                OnlyNewTickVolumeAbsorption=onlyAbsorption,
                MarginalFrozenShockNetEur=joint.ModelClosedCentralNetEur-
                    onlyAbsorption.ModelClosedCentralNetEur,
                MarginalTickVolumeAbsorptionNetEur=joint.ModelClosedCentralNetEur-
                    onlyShock.ModelClosedCentralNetEur,
                AllAbalationsUseNewIsolatedEUR300CounterfactualBook=true,
                JointWalletNeverSummed=true,
                QualifiedIndependentEconomicSupport=false
            },
            BrokerContractFirstObservedUtcMs=source.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            HistoricDecisionFirstUtcMs=source.Marks.Min(x=>x.At),
            ContractTermsExplicitlyAppliedRetrospectively=
                source.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            ContractTermsAreCurrentNotHistorical=true,
            HistoricalSlippageModeledNotExecuted=true,
            OriginalAuthenticationVerifiedOnlyByCaller=true,
            BrokerFillProof=false,OrdersSubmitted=0,CloudActivated=false
        }));
        return 0;
    }
    catch(Exception e)
    {
        Console.Error.WriteLine("HISTORICAL_W36W37_NATIVE_REPLAY_REJECTED:"+
            e.GetType().Name);
        return 58;
    }
}

// New W45 post-PR162 economic research. The prespecified two-family protocol
// is committed BEFORE collecting the source: no PR160 breakout revival.
// Both ablations replay the identical quote tape and a complete fresh EUR300
// funded model, not a sum of standalone capital wallets. All outputs remain
// conditional on current tariffs, observed quotes and modeled (not broker) fills.
if(args.Length==3 && args[2]=="--native-original-openapi-w45")
{
    try
    {
        var input=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions{
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            input,parse)??throw new ArgumentException("OPENAPI_W45_TAPE_NULL");
        if(source.SourceLabel!=
           "ORIGINAL_PEPPERSTONE_OPENAPI_2026_W45_FX_M5_BREADTH_AND_SHOCK_PREDECLARED")
            throw new ArgumentException("W45_PROTOCOL_SOURCE_LABEL_MISMATCH");
        var native=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        var joint=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"FX_BREADTH_SHOCK_W45");
        var withoutBreadth=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"FX_ONLY_SHOCK_W45");
        var withoutShock=Mxm.Core.NativeHistoricalProductReplay.Evaluate(native,
            UnqualifiedShadowMode:true,ResearchMode:"FX_ONLY_BREADTH_W45");
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            Protocol="research/fx_w45_new_mechanisms_protocol.json",
            Window="2026-W45_EXPLORATORY_NOT_INDEPENDENT_CONFIRMATION",
            FutureW46NotScored=true,
            InputFileSha256=Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant(),
            Receipt=joint,
            CounterfactualAblation=new {
                WithoutUsdBreadthCatchup=withoutBreadth,
                WithoutM5ShockReversion=withoutShock,
                MarginalUsdBreadthCatchupNetEur=joint.ModelClosedCentralNetEur-
                    withoutBreadth.ModelClosedCentralNetEur,
                MarginalM5ShockReversionNetEur=joint.ModelClosedCentralNetEur-
                    withoutShock.ModelClosedCentralNetEur,
                JointWalletNotSumOfCounterfactualWallets=true,
                ClaimedIndependentEconomicSupport=false
            },
            BrokerContractFirstObservedUtcMs=source.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            HistoricDecisionFirstUtcMs=source.Marks.Min(x=>x.At),
            ContractTermsExplicitlyAppliedRetrospectively=
                source.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            ContractTermsAreCurrentNotHistorical=true,
            HistoricalSlippageIsModeledNotExecuted=true,
            SourceAuthenticationMustBeVerifiedByCaller=true,
            CertifiedBrokerTradeFills=false,
            IndependentlyConfirmed=false,OrdersSubmitted=0,CloudActivated=false
        }));
        return 0;
    }
    catch(Exception exc)
    {
        Console.Error.WriteLine("OPENAPI_W45_NATIVE_REPLAY_REJECTED:"+exc.GetType().Name);
        return 58;
    }
}

// This uses the EXISTING cost/ledger/replay machinery. Original Open API
// source authentication happens in the collector process; this offline reader
// does not independently establish account identity or tariff continuity.
if(args.Length==3 && args[2]=="--native-original-openapi-research")
{
    try
    {
        var input=File.ReadAllBytes(args[0]);
        var parse=new JsonSerializerOptions{
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var source=JsonSerializer.Deserialize<Mxm.Core.NativeOriginalOpenApiTape>(
            input,parse)??throw new ArgumentException("OPENAPI_PRODUCT_TAPE_NULL");
        var native=Mxm.Core.NativeOriginalOpenApiProductAdapter.Convert(source);
        // All three paths use one continuous EUR300 cash/equity ledger
        // each; the full portfolio is never the sum of standalone runs.
        // Marginal impact is a counterfactual removal, not an isolated
        // winner-sorting exercise. Families were fixed before the source.
        var receipt=Mxm.Core.NativeHistoricalProductReplay.Evaluate(
            native,UnqualifiedShadowMode:true,
            ResearchMode:"FX_CAUSAL_BREAKOUT_PLUS_RELATIVE_VALUE");
        var withoutRelative=Mxm.Core.NativeHistoricalProductReplay.Evaluate(
            native,UnqualifiedShadowMode:true,ResearchMode:"FX_ONLY_BREAKOUT");
        var withoutBreakout=Mxm.Core.NativeHistoricalProductReplay.Evaluate(
            native,UnqualifiedShadowMode:true,ResearchMode:"FX_ONLY_RELATIVE_VALUE");
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            InputFileSha256=Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant(),
            Receipt=receipt,
            CounterfactualAblation=new {
                WithoutRelativeValue=withoutRelative,
                WithoutBreakout=withoutBreakout,
                MarginalBreakoutNetEur=receipt.ModelClosedCentralNetEur-
                    withoutBreakout.ModelClosedCentralNetEur,
                MarginalRelativeValueNetEur=receipt.ModelClosedCentralNetEur-
                    withoutRelative.ModelClosedCentralNetEur,
                ClaimedIndependentEconomicSupport=false
            },
            BrokerContractFirstObservedUtcMs=source.Marks.Min(x=>x.Contract.ObservedAtUtcMs),
            HistoricDecisionFirstUtcMs=source.Marks.Min(x=>x.At),
            ContractTermsExplicitlyAppliedRetrospectively=
                source.Marks.Any(x=>x.Contract.ObservedAtUtcMs>x.At),
            ContractTermsAreCurrentNotHistorical=true,
            HistoricalSlippageIsModeledNotExecuted=true,
            SourceAuthenticationMustBeVerifiedByCaller=true,
            CertifiedBrokerTradeFills=false,
            IndependentlyConfirmed=false,
            OrdersSubmitted=0,
            CloudActivated=false
        }));
        return 0;
    }
    catch(Exception exc)
    {
        Console.Error.WriteLine("OPENAPI_PRODUCT_NATIVE_REPLAY_REJECTED:"+
            exc.GetType().Name);
        return 58;
    }
}

// Native product-level historical replay on FULL imported M5 OHLCV and exact
// quote/cost observations. Input provenance is not cryptographically attested
// by the command; custody validation must occur upstream in a permitted
// protected environment. Never synthesize BID/ASK or broker fills from OHLCV.
// Example: dotnet run --project src/Mxm.Replay -- input.json result.json
//          --native-product-ohlcv-exploratory
if(args.Length==3 && (args[2]=="--native-product-ohlcv-exploratory"||
                     args[2]=="--native-product-ohlcv-gated"))
{
    try
    {
        var bytes=File.ReadAllBytes(args[0]);
        var jsonOptions=new JsonSerializerOptions{
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var tape=JsonSerializer.Deserialize<Mxm.Core.NativeHistoricalMarketTape>(
            bytes,jsonOptions)??throw new ArgumentException("PRODUCT_TAPE_NULL");
        var receipt=Mxm.Core.NativeHistoricalProductReplay.Evaluate(tape,
            UnqualifiedShadowMode:args[2]=="--native-product-ohlcv-exploratory");
        string sha=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new{
            InputFileSha256=sha,
            Receipt=receipt,
            SourceOriginalBrokerCryptographicallyVerified=false,
            PortfolioRealBrokerNetEur=(decimal?)null,
            NoOrdersSent=true,CloudNotActivated=true,
            InputMustSupplyActualOriginalBidAskSnapshots=true,
            SourceProvenance="UNVERIFIED_INPUT_UNTIL_AUTHORIZED_CUSTODY_ATTESTS"
        }));
        return 0;
    }
    catch(Exception ex)
    {
        Console.Error.WriteLine("NATIVE_HISTORICAL_REPLAY_REJECTED:"+
            ex.GetType().Name+":"+ex.Message);
        return 57;
    }
}

// The SAME native Cloud-linked Mxm.Core executes all three MCS1 features.
// Research-only, no broker request or order. Original H1 bars provided as input.
if(args.Length==3 && args[2]=="--mcs1-native-h1-signs")
{
    try
    {
        var rows=JsonSerializer.Deserialize<Mxm.Core.McsH1Frame[]>(File.ReadAllBytes(args[0]))!;
        if(rows is null || rows.Length>11000)return 43;
        File.WriteAllText(args[1],JsonSerializer.Serialize(
            Mxm.Core.McsNativeH1Features.EvaluateBatch(rows)));
        return 0;
    }
    catch {return 43;}
}

// Research-only bridge to EXACT existing Mxm.Core finance implementation.
// The original broker contract fields come from CMA1/CMA2; example market
// prices and FX rates MUST be labeled illustrative, never actual broker fills.
if (args.Length==3 && args[2]=="--prospective-native-contract-ledger-parity")
{
    try
    {
        using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var rows=doc.RootElement.EnumerateArray();
        var numbers=new JsonSerializerOptions {
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        };
        var receipts=new List<object>();
        const string evidence="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        foreach(var row in rows)
        {
            var contract=JsonSerializer.Deserialize<Mxm.Core.NativeObservedContractTerms>(
                row.GetProperty("Contract").GetRawText(),numbers)!;
            var open=JsonSerializer.Deserialize<Mxm.Core.NativeMarketCostContext>(
                row.GetProperty("Entry").GetRawText(),numbers)!;
            var close=JsonSerializer.Deserialize<Mxm.Core.NativeMarketCostContext>(
                row.GetProperty("Exit").GetRawText(),numbers)!;
            int side=row.GetProperty("Side").GetInt32();
            if(side is not (-1 or 1) || open.Units!=close.Units || 
                close.AtUtcMs<=open.AtUtcMs+2000L || open.AtUtcMs<2000)
                throw new ArgumentException("COST_PARITY_CASE_CLOCK_OR_SIDE");
            var entry=Mxm.Core.NativeBrokerContractCosts.Quote(
                contract,open,executionIsBuy:side>0);
            var exit=Mxm.Core.NativeBrokerContractCosts.Quote(
                contract,close,executionIsBuy:side<0);
            decimal? carry=Mxm.Core.NativeBrokerContractCosts.SignedFinancing(
                contract,open.AtUtcMs,close.AtUtcMs,side,open.Units,
                close.QuoteCreditToEur,close.QuoteDebitToEur);
            if(carry is not decimal funding)
                throw new ArgumentException("COST_PARITY_FUNDING_UNKNOWN_NO_ZERO_DEFAULT");
            var book=new Mxm.Core.NativeFundedLedger(1000);
            decimal q=side>0?open.Ask+open.SlippagePerSideQuote:
                               open.Bid-open.SlippagePerSideQuote;
            decimal y=side>0?close.Bid-close.SlippagePerSideQuote:
                               close.Ask+close.SlippagePerSideQuote;
            var id="model-"+receipts.Count;
            Mxm.Core.LedgerEvent Fact(string name,long at,string kind,
                decimal price,decimal fee,decimal slip,decimal margin,
                Mxm.Core.LedgerQuote[] quotes,decimal signedFinance=0)
                =>new(name,at,kind,id,contract.Symbol,side,open.Units,price,fee,
                    margin,slip,0,0,1000,"AUTHENTIC_TERMS_ILLUSTRATIVE_MARKS_ONLY",
                    evidence,quotes,signedFinance);
            book.Apply(Fact("req-entry-"+id,open.AtUtcMs-1000,
                "REQUEST_OPEN",0,0,open.SlippagePerSideQuote,
                entry.Quote.MarginPerUnit,Array.Empty<Mxm.Core.LedgerQuote>()));
            book.Apply(Fact("fill-entry-"+id,open.AtUtcMs,
                "OPEN_FILL",q,entry.OneSideCommissionEur,
                open.SlippagePerSideQuote,entry.Quote.MarginPerUnit,
                new[]{entry.Quote}));
            book.Apply(Fact("req-exit-"+id,close.AtUtcMs-1000,
                "REQUEST_CLOSE",0,0,open.SlippagePerSideQuote,
                exit.Quote.MarginPerUnit,Array.Empty<Mxm.Core.LedgerQuote>()));
            if(funding!=0m)
                book.Apply(Fact("finance-"+id,close.AtUtcMs,
                    "FINANCING",0,0,open.SlippagePerSideQuote,0,
                    new[]{exit.Quote},funding));
            book.Apply(Fact("fill-exit-"+id,close.AtUtcMs,
                "CLOSE_FILL",y,exit.OneSideCommissionEur,
                open.SlippagePerSideQuote,exit.Quote.MarginPerUnit,
                new[]{exit.Quote}));
            var fragment=book.ClosedFragments().Single();
            var snapshot=book.Summary();
            var resumed=Mxm.Core.NativeFundedLedger.Restore(book.Checkpoint());
            if(resumed.Summary()!=snapshot ||
               resumed.ClosedFragments().Single()!=fragment)
                throw new InvalidOperationException("NATIVE_CONTRACT_LEDGER_RESTART_PARITY");
            receipts.Add(new {
                ContractSymbol=contract.Symbol,
                ContractAsObservedUtcMs=contract.ObservedAtUtcMs,
                Entry=entry,Exit=exit,FinancingSignedEur=funding,
                ClosedFragment=fragment,Ledger=snapshot,
                SourcePricesAuthenticBrokerTicks=false,
                ContractTermsObservedOriginalBroker=contract.OriginalBrokerAuthenticated,
                HistoricalContractContinuityCertified=false,
                NativeLedgerRestartExact=true,
                ActualBrokerNetEur=(decimal?)null,OrdersSubmitted=0
            });
        }
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            NativeContractAndLedgerReceipts=receipts,
            SameCoreAsCloud=true,ClosedOldStudiesReplayed=false,
            IndependentConfirmation=false,OrdersSubmitted=0,CloudActivated=false
        }));return 0;
    }
    catch(Exception ex) {
        Console.Error.WriteLine(ex.GetType().Name + ":" + ex.Message);
        return 42;
    }
}

if (args.Length == 3 && args[2] == "--sfx1-native-signs")
{
    try
    {
        var frames=JsonSerializer.Deserialize<Mxm.Core.SfxFeatureFrame[]>(
            File.ReadAllBytes(args[0]))!;
        if(frames is null || frames.Length>6000)return 41;
        File.WriteAllText(args[1],JsonSerializer.Serialize(
            Mxm.Core.SfxNativeSessionFeatures.EvaluateBatch(frames)));
        return 0;
    }
    catch { return 41; }
}

if (args.Length == 3 && args[2] == "--xua1-native-signs")
{
    try
    {
        var inputs=JsonSerializer.Deserialize<Mxm.Core.XuaFeatureFrame[]>(
            File.ReadAllBytes(args[0]),new JsonSerializerOptions{PropertyNameCaseInsensitive=true})!;
        if(inputs is null || inputs.Length>5000)return 31;
        File.WriteAllText(args[1],JsonSerializer.Serialize(
            Mxm.Core.XuaNativeFeatureSigns.DecideBatch(inputs)));
        return 0;
    }
    catch { return 31; }
}

// Byte-for-byte causality/parity oracle used only by protected research and CI.
// The same compiled Mxm.Core is used by the Cloud cBot; no orders or broker IO.
if (args.Length == 3 && args[2] == "--native-mfa1-feature-parity")
{
    try {
        var cases=JsonSerializer.Deserialize<Mxm.Core.NativeFamilyCase[]>(File.ReadAllBytes(args[0]))!;
        if(cases==null||cases.Length>6000)return 36;
        var result=cases.Select(Mxm.Core.MultiFamilyNativeFeatures.Evaluate).ToArray();
        File.WriteAllText(args[1],JsonSerializer.Serialize(result));
        return 0;
    } catch { return 36; }
}
if (args.Length == 3 && args[2] == "--native-funded-decision-cycle")
{
    try {
        var frames=System.Text.Json.JsonSerializer.Deserialize<Mxm.Core.NativeResearchFrame[]>(File.ReadAllBytes(args[0]),
            new System.Text.Json.JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        var session=new Mxm.Core.NativeFundedSession("CONDITIONAL_DEVELOPMENT_ONLY");
        var receipts=new List<object>();
        foreach(var frame in frames) {
            session.ApplyResearchFacts(frame.Facts);
            var decision=frame.Decision is null?null:session.DecideResearch(frame.Decision);
            session=Mxm.Core.NativeFundedSession.Restore(session.Checkpoint(),session.AccountBinding);
            receipts.Add(new {Decision=decision,Ledger=session.Ledger.Summary()});
        }
        File.WriteAllText(args[1],System.Text.Json.JsonSerializer.Serialize(new {Receipts=receipts,
            Trades=session.Ledger.ClosedFragments(),OrdersSubmitted=0,CloudActivated=false,
            ActualBrokerNetEur=(decimal?)null,IndependentConfirmation=false}));return 0;
    } catch {return 31;}
}
if (args.Length == 3 && args[2] == "--multiscale-conditional-program")
{
    try {
        var input=System.Text.Json.JsonSerializer.Deserialize<Mxm.Core.MultiscaleInput>(File.ReadAllBytes(args[0]),
            new System.Text.Json.JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        File.WriteAllText(args[1],System.Text.Json.JsonSerializer.Serialize(Mxm.Core.MultiscaleConditionalResearch.Evaluate(input)));return 0;
    } catch (Exception ex) { Console.Error.WriteLine(ex.GetType().Name);return 30; }
}
if (args.Length == 3 && args[2] == "--carry-cycle-preflight")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.CarryPreflightInput>(File.ReadAllBytes(args[0]),new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.CarryCyclePreflight.Evaluate(input)));return 0;
    } catch { return 28; }
}
if (args.Length == 3 && args[2] == "--native-risk-observations")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.PortfolioRiskMark[][]>(File.ReadAllBytes(args[0]),new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        var output=input.Select(marks=>{
            var session=new Mxm.Core.NativeFundedSession(marks[0].AccountBinding);var results=new List<Mxm.Core.PortfolioRiskReport>();
            foreach(var m in marks){var r=session.ObservePortfolio(m,m.AvailableAt);session=Mxm.Core.NativeFundedSession.Restore(session.Checkpoint(),m.AccountBinding);
                var same=session.ObservePortfolio(m,m.AvailableAt);if(JsonSerializer.Serialize(r)!=JsonSerializer.Serialize(same))throw new ArgumentException("RISK_RESTART_PARITY");results.Add(r);}
            return new {Reports=results,State=session.PortfolioObservation.State,RestartMatched=true};
        }).ToArray();File.WriteAllText(args[1],JsonSerializer.Serialize(output));return 0;
    } catch { return 29; }
}
if (args.Length == 3 && args[2] == "--native-frozen-money-recovery")
{
    try {
        var cases=JsonSerializer.Deserialize<Mxm.Core.FrozenMoneyRecoveryCase[]>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.FrozenMoneyRecoveryReceipt.Receive(cases)));return 0;
    } catch { return 27; }
}
if (args.Length == 3 && args[2] == "--auction-source-support")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.AuctionInput>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        var episodes=Mxm.Core.AuctionInventoryResearch.Episodes(input);
        File.WriteAllText(args[1],JsonSerializer.Serialize(input.Sessions.Select(s=>new {s.Symbol,FeatureEpisodes=episodes.Count(x=>x.Symbol==s.Symbol),KnownLabels=episodes.Count(x=>x.Symbol==s.Symbol&&x.Outcome.HasValue)})));return 0;
    } catch { return 26; }
}
if (args.Length == 3 && args[2] == "--auction-inventory-program")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.AuctionInput>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.AuctionInventoryResearch.Evaluate(input)));return 0;
    } catch { return 24; }
}
if (args.Length == 3 && args[2] == "--broker-identity-reception")
{
    try {
        using var root=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var snapshot=JsonSerializer.Deserialize<Mxm.Core.BrokerIdentitySnapshot>(root.RootElement.GetProperty("Snapshot").GetRawText(),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        var session=new Mxm.Core.NativeFundedSession(snapshot.AccountBinding);
        decimal? cash=root.RootElement.GetProperty("BrokerCashEur").ValueKind==JsonValueKind.Null?null:decimal.Parse(root.RootElement.GetProperty("BrokerCashEur").GetString()!,System.Globalization.CultureInfo.InvariantCulture);
        var first=session.Observe(snapshot,cash);var resumed=Mxm.Core.NativeFundedSession.Restore(session.Checkpoint(),snapshot.AccountBinding);
        var second=resumed.Observe(snapshot,cash);
        bool same=JsonSerializer.Serialize(first)==JsonSerializer.Serialize(second);
        if(!same)throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {Report=first,RestoredReportMatched=same,ActualBrokerCashImported=false,OrdersSubmitted=0}));return 0;
    } catch { return 25; }
}
if (args.Length == 3 && args[2] == "--native-funded-facts")
{
    try {
        var events=JsonSerializer.Deserialize<Mxm.Core.LedgerEvent[]>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString}) ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.NativeFundedLedger.ReceiveFacts(events)));return 0;
    } catch { return 22; }
}
if (args.Length == 3 && args[2] == "--portfolio-discovery-program")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.DiscoveryInput>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString}) ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.PortfolioDiscoveryProgram.Evaluate(input)));return 0;
    } catch { return 23; }
}
if (args.Length == 3 && args[2] == "--sequence-portfolio-forecasts")
{
    try {
        var blocks=JsonSerializer.Deserialize<Mxm.Core.SequenceFeatureBlock[]>(File.ReadAllBytes(args[0])) ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.SequenceOpportunityResearch.Describe(blocks)));return 0;
    } catch { return 21; }
}
if (args.Length == 3 && args[2] == "--assess-holding-risk-batch")
{
    try {
        var inputs=JsonSerializer.Deserialize<Mxm.Core.HoldingRiskInput[]>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(inputs.Select(Mxm.Core.HoldingPortfolioRisk.Assess).ToArray()));
        return 0;
    } catch { return 20; }
}
if (args.Length == 3 && args[2] == "--causal-observation-windows")
{
    try {
        var windows=JsonSerializer.Deserialize<Mxm.Core.ObservationWindow[]>(File.ReadAllBytes(args[0]))
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(windows.Select(Mxm.Core.CausalObservationClock.First).ToArray()));
        return 0;
    } catch { return 19; }
}
if (args.Length == 3 && args[2] == "--holding-market-context")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.HoldingPortfolioRisk.MarketContext(d.RootElement)));return 0;
    } catch { return 18; }
}
if (args.Length == 3 && args[2] == "--assess-holding-risk")
{
    try {
        var r=JsonSerializer.Deserialize<Mxm.Core.HoldingRiskInput>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.HoldingPortfolioRisk.Assess(r)));return 0;
    } catch { return 17; }
}
if (args.Length == 3 && args[2] == "--value-portfolio-source")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.MultiAssetValuation.Assess(d.RootElement)));
        return 0;
    } catch { return 16; }
}
if (args.Length == 3 && args[2] == "--estimate-portfolio-opportunities-batch")
{
    try {
        var requests=JsonSerializer.Deserialize<Mxm.Core.ResearchOrchestrationRequest[]>(
            File.ReadAllBytes(args[0]),new JsonSerializerOptions {
                NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        Mxm.Core.ResearchScopeContract.RequireBatch(requests);
        File.WriteAllText(args[1],JsonSerializer.Serialize(requests.Select(Mxm.Core.OpportunityOrchestrator.Estimate).ToArray()));
        return 0;
    } catch (Exception ex) { Console.Error.WriteLine($"BATCH_RESEARCH_ERROR:{ex.GetType().Name}"); return 32; }
}
if (args.Length == 3 && args[2] == "--estimate-portfolio-opportunities")
{
    try {
        var r=JsonSerializer.Deserialize<Mxm.Core.ResearchOrchestrationRequest>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.OpportunityOrchestrator.Estimate(r)));
        return 0;
    } catch { return 14; }
}
if (args.Length == 3 && args[2] == "--economic-portfolio-plan")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var bars=Mxm.Core.RegimeDiscovery.Read(d.RootElement);
        var plan=Mxm.Core.JointOpportunityResearch.Describe(bars)
            .Select(r=>new {r.Candidate,r.Symbol,r.Clock,r.Exit,r.Side});
        File.WriteAllText(args[1],JsonSerializer.Serialize(plan));return 0;
    } catch { return 15; }
}
if (args.Length == 3 && args[2] == "--orchestrate-opportunities")
{
    try {
        var r=JsonSerializer.Deserialize<Mxm.Core.OrchestrationRequest>(File.ReadAllBytes(args[0]), new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.OpportunityOrchestrator.Select(r.Clock,r.Account,r.Baseline,r.Opportunities)));
        return 0;
    } catch { return 13; }
}
if (args.Length == 3 && args[2] == "--joint-opportunity-research")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.JointOpportunityResearch.Assess(d.RootElement)));
        return 0;
    } catch { return 12; }
}
if (args.Length == 3 && args[2].StartsWith("--neighbour-"))
{
    try {using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        object result=args[2] switch {
            "--neighbour-plan"=>Mxm.Core.NeighbourFxResearch.MakePlan(d.RootElement).Plans,
            "--neighbour-confirm-plan"=>Mxm.Core.NeighbourFxResearch.MakePlan(d.RootElement,true).Plans,
            "--neighbour-selection"=>Mxm.Core.NeighbourFxResearch.Evaluate(d.RootElement),
            "--neighbour-confirmation"=>Mxm.Core.NeighbourFxResearch.Evaluate(d.RootElement,true),
            _=>throw new ArgumentException()};
        File.WriteAllText(args[1],JsonSerializer.Serialize(result));return 0;
    }catch{return 11;}
}
if (args.Length == 3 && args[2] == "--regime-discovery")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.RegimeDiscovery.Assess(d.RootElement)));
        return 0;
    } catch { return 11; }
}
if (args.Length == 3 && args[2].StartsWith("--flow-"))
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        object result=args[2] switch {
            "--flow-plan"=>Mxm.Core.CausalFlowResearch.Propose(d.RootElement),
            "--flow-confirm-plan"=>Mxm.Core.CausalFlowResearch.Propose(d.RootElement,true),
            "--flow-selection"=>Mxm.Core.CausalFlowResearch.Evaluate(d.RootElement),
            "--flow-confirmation"=>Mxm.Core.CausalFlowResearch.Evaluate(d.RootElement,true),
            _=>throw new ArgumentException()};
        File.WriteAllText(args[1],JsonSerializer.Serialize(result));return 0;
    } catch { return 10; }
}
if (args.Length == 3 && (args[2] == "--intraday-plan" || args[2] == "--intraday-net"))
{
    try {
        using var d=System.Text.Json.JsonDocument.Parse(System.IO.File.ReadAllBytes(args[0]));
        object r=args[2]=="--intraday-plan" ? Mxm.Core.IntradayReversalNet.Propose(Mxm.Core.IntradayReversalNet.Bars(d.RootElement)) : Mxm.Core.IntradayReversalNet.Assess(d.RootElement);
        System.IO.File.WriteAllText(args[1],System.Text.Json.JsonSerializer.Serialize(r));
        return 0;
    } catch { return 9; }
}
if (args.Length == 3 && args[2] == "--economic-net-coverage")
{
    try
    {
        using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var result=Mxm.Core.AuthenticatedNetCoverage.Examine(doc.RootElement);
        File.WriteAllText(args[1],JsonSerializer.Serialize(result));
        return 0;
    }
    catch { return 8; }
}
if (args.Length == 3 && args[2] == "--economic-screen")
{
    try
    {
        using var input=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var root=input.RootElement;
        _=Mxm.Core.EconomicSourceAdmission.ReadReceipt(root);
        var contracts=root.GetProperty("brokerContract");
        var groups=root.GetProperty("bars").EnumerateArray()
            .GroupBy(x=>(
                symbol:x.GetProperty("symbol").GetString()!,
                resolution:x.GetProperty("resolution").GetString()!,
                duration:x.GetProperty("periodMinutes").GetInt32()
            )).ToArray();
        var results=new List<object>();
        foreach(var g in groups.OrderBy(x=>x.Key.symbol,StringComparer.Ordinal)
                                .ThenBy(x=>x.Key.resolution,StringComparer.Ordinal))
        {
            var contract=contracts.GetProperty(g.Key.symbol);
            var pip=contract.GetProperty("pipPosition");
            if(pip.ValueKind!=JsonValueKind.Number)
                throw new ArgumentException("UNAVAILABLE_BROKER_PIP_SCALE");
            var bars=g.Select(b=>new Mxm.Core.PriceOnlyBar(
                g.Key.symbol,g.Key.resolution,
                DateTimeOffset.FromUnixTimeMilliseconds(b.GetProperty("openTime").GetInt64()).UtcDateTime,
                DateTimeOffset.FromUnixTimeMilliseconds(b.GetProperty("availableTime").GetInt64()).UtcDateTime,
                g.Key.duration,b.GetProperty("open").GetInt64(),
                b.GetProperty("high").GetInt64(),b.GetProperty("low").GetInt64(),
                b.GetProperty("close").GetInt64()));
            var gross=Mxm.Core.EconomicBreakoutProbe.Assess(bars,pip.GetInt32());
            // Never claim qualified trades or prefer one profitable instrument.
            bool admitted=gross.Episodes>=20;
            results.Add(new {
                symbol=g.Key.symbol,resolution=g.Key.resolution,
                priceOnlyCompleteProxies=gross.Episodes,
                observedWeeksWithProxies=gross.ObservedExitWeeks,
                weeksWith21PriceOnlyProxies=gross.WeeksWith21Proxies,
                meanGrossPips=admitted?gross.MeanGrossPips:null,
                medianGrossPips=admitted?gross.MedianGrossPips:null,
                positiveFraction=admitted?gross.PositiveFraction:null,
                earlySliceGrossPips=admitted?gross.EarlySliceGrossPips:null,
                middleSliceGrossPips=admitted?gross.MiddleSliceGrossPips:null,
                lateSliceGrossPips=admitted?gross.LateSliceGrossPips:null,
                status=admitted?gross.Verdict:"INSUFFICIENT_PRICE_ONLY_EPISODES"
            });
        }
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            schema="mxm-new-fixed-breakout-price-only-v1",
            sourceRunId=41476636915L,
            modelFrozen="PR11_FIXED_12_BAR_CLOSE_BREAKOUT_NEXT_BAR_OPEN_FOUR_BAR_CLOSE",
            developmentOnly=true,
            reportedPerSymbolNotCherryPicked=true,
            results,
            historicalBidAskNotAnExecutionPrice=true,
            netInEur=null as decimal?,
            funded200EurProven=false,
            hard21BrokerRoundTripsProven=false,
            independentConfirmation=false,
            ordersSubmitted=0
        }));
        return 0;
    }
    catch { return 7; }
}
if (args.Length == 3 && args[2] == "--economic-source")
{
    try
    {
        using var economic=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var sourceReceipt=Mxm.Core.EconomicSourceAdmission.ReadReceipt(economic.RootElement);
        File.WriteAllText(args[1],JsonSerializer.Serialize(sourceReceipt));
        return 0;
    }
    catch { return 6; }
}
if (args.Length != 2 && !(args.Length == 3 && args[2] == "--score-causal")) return 2;
var scoreOnly = args.Length == 3;
try
{
    var bytes = File.ReadAllBytes(args[0]);
    using var doc = JsonDocument.Parse(bytes);
    var root = doc.RootElement;
    if (root.GetProperty("source").GetString() != "Pepperstone-cTrader-OpenAPI" || !root.GetProperty("readOnly").GetBoolean()) return 3;
    var seen = new HashSet<(string,long)>();
    int count=0;
    foreach (var bar in root.GetProperty("bars").EnumerateArray())
    {
        var symbol=bar.GetProperty("symbol").GetString() ?? throw new Exception();
        var t=bar.GetProperty("openTime").GetInt64();
        var available=bar.GetProperty("availableTime").GetInt64();
        var o=bar.GetProperty("open").GetInt64(); var h=bar.GetProperty("high").GetInt64();
        var l=bar.GetProperty("low").GetInt64(); var c=bar.GetProperty("close").GetInt64();
        if (!seen.Add((symbol,t)) || available!=t+3600000 || available>root.GetProperty("end").GetInt64() ||
            t<root.GetProperty("start").GetInt64() || l<=0 || o<l || o>h || c<l || c>h || bar.GetProperty("tickVolume").GetInt64()<0) return 4;
        count++;
    }
    if (count==0) return 5;
    // A distinct native C# causal H1 research mechanism runs on source-admitted
    // bars in chronological per-symbol order, never emits orders and never
    // treats candidate counts as NET performance or independent confirmation.
    var bundleSha=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    var researchers=new Dictionary<string,Mxm.Core.CausalRangePressureResearch>();
    var actualSourceClocks=new List<Mxm.Core.SourceBarClock>();
    var pending=new Dictionary<string,Mxm.Core.ResearchForecast>();
    var lastCloses=new Dictionary<string,decimal>();
    var scorer=new Mxm.Core.CausalForecastScoreLedger();
    int causalForecastCount=0;
    foreach(var bar in root.GetProperty("bars").EnumerateArray()
        .OrderBy(x=>x.GetProperty("symbol").GetString(),StringComparer.Ordinal)
        .ThenBy(x=>x.GetProperty("openTime").GetInt64()))
    {
        var name=bar.GetProperty("symbol").GetString()!;
        if(!researchers.TryGetValue(name,out var researcher))
        {
            researcher=new Mxm.Core.CausalRangePressureResearch();
            researchers.Add(name,researcher);
        }
        var open=DateTimeOffset.FromUnixTimeMilliseconds(
            bar.GetProperty("openTime").GetInt64()).UtcDateTime;
        var available=DateTimeOffset.FromUnixTimeMilliseconds(
            bar.GetProperty("availableTime").GetInt64()).UtcDateTime;
        actualSourceClocks.Add(new Mxm.Core.SourceBarClock(
            name,open,available,TimeSpan.FromHours(1),bundleSha));
        var close=bar.GetProperty("close").GetDecimal();
        // Score only predictions made BEFORE this target completed.
        // A missing interval is never converted into an invented outcome.
        if (scoreOnly && pending.TryGetValue(name,out var prior) &&
            prior.TargetBarEndsUtc==available &&
            lastCloses.TryGetValue(name,out var priorClose))
        {
            var target=close>priorClose?1m:close<priorClose?0m:.5m;
            scorer.Score(prior.ProbabilityUp,target);
        }
        var candidate=researcher.Observe(new Mxm.Core.CompletedH1Candle(
            name,open,available,
            bar.GetProperty("open").GetDecimal(),
            bar.GetProperty("high").GetDecimal(),
            bar.GetProperty("low").GetDecimal(),
            bar.GetProperty("close").GetDecimal(),
            bar.GetProperty("tickVolume").GetInt64(),bundleSha));
        if(candidate!=null)causalForecastCount++;
        if (scoreOnly)
        {
            pending.Remove(name);
            if (candidate is not null) pending[name]=candidate;
            lastCloses[name]=close;
        }
    }
    var calendar=Mxm.Core.CausalSourceCalendar.Assess(actualSourceClocks);
    if(scoreOnly)
    {
        var score=scorer.Summarize();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            schema="mxm.causal-range-pressure-authentic-observation-only.v1",
            forecastScored=score.Count,
            publicScoreAdmitted=score.Count>=100,
            meanBrier=score.Count>=100 ? (decimal?)score.MeanBrier : null,
            neutralMeanBrier=score.Count>=100 ? (decimal?)score.BaselineMeanBrier : null,
            brierSkill=score.Count>=100 ? (decimal?)score.BrierSkillVersusNeutral : null,
            qualification=score.Qualification,
            sourceBars=count,
            sourceObservedWeeks=calendar.DistinctObservedIsoWeeks,
            netEurQualified=false,
            hard21BrokerOrders=0,
            twelveMonthsIndependentConfirmation=false,
            ordersSubmitted=0
        }));
        return 0;
    }
    File.WriteAllText(args[1],JsonSerializer.Serialize(new {
        sourceSha256=bundleSha,bars=count,
        observedCalendarWeeks=calendar.DistinctObservedIsoWeeks,
        observedCalendarDiscontinuities=calendar.DiscontinuitiesBetweenSuccessiveSameSymbolBars,
        twelveCalendarMonthsObserved=calendar.TwelveCalendarMonthsObservedForAnySymbol,
        calendarStatus=calendar.Status,
        causalResearchForecasts=causalForecastCount,causalResearchStatus=Mxm.Core.CausalRangePressureResearch.ResearchOnly,
        status="SOURCE_VALIDATED_NOT_EXECUTION_REPLAY",economicQualification=false,
        missing="Historical executable spreads, costs, FX, financing, margin and qualified strategy" }));
    return 0;
}
catch { return 1; }

