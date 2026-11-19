using System;
using System.Linq;
using Mxm.Core;

// SYC1 tests are entirely synthetic: not a Pepperstone source, economic alpha,
// authenticated fills, or a genuine HARD21/continuous-risk certificate.
internal static class NativeSystemicOpportunityCensusChecks
{
    public static void Run(Action<bool,string> check)
    {
        long t=DateTimeOffset.Parse("2026-11-16T10:00:00+00:00").ToUnixTimeMilliseconds();
        NativeSystemicProposal P(string id,string family,string symbol,int side,long at,long exit)=>
            new(id,family,symbol,side,at,exit);
        var source=new[]{
            P("b","BAYES","FX",1,t,t+60000),
            P("a","SOFTMAX","FX",1,t,t+60000),
            P("c","BAYES","FX",-1,t+1000,t+15000),
            P("d","SOFTMAX","FX",1,t+1000,t+15000),
            P("e","STATE","FX",1,t+30000,t+90000),
            P("f","STATE","FX",1,t+60000,t+120000),
            P("g","BAYES","INDEX",-1,t+60000,t+120000),
            P("h","SOFTMAX","INDEX",-1,t+60000,t+120000)
        };
        var absent=NativeSystemicOpportunityCensus.Assess(new(
            source,Array.Empty<NativeSystemicPositionLink>(),
            Array.Empty<LedgerClosedFragment>(),null,
            new[]{"2026-W47","2026-W48"}));
        check(absent.RawCombinedProposals==8 &&
            absent.SameClockOppositeSideRejections==2 &&
            absent.SameSideDuplicatesRemoved==2 &&
            absent.SameInstrumentHoldingOverlapsRemoved==1 &&
            absent.UniqueNonconflictingOpportunities==3 &&
            absent.Weeks[0].RawCombinedProposals==8 &&
            absent.Weeks[0].UniqueNonconflictingOpportunities==3 &&
            absent.Weeks[1].RawCombinedProposals==0 &&
            absent.Weeks[0].RawPerSymbolFamily["FX/BAYES"]==2,
            "SYC1 individual stream, combined, deduplicated and simultaneous cross-symbol counts remain distinct");
        check(absent.ModeledFundedCompleteTrips is null &&
            absent.ModeledClosedNetEur is null &&
            absent.SystemHard21EvidenceState=="UNKNOWN" &&
            absent.Weeks.All(w=>w.ModeledFundedCompleteTrips is null) &&
            absent.MissingEvidence.Contains("ONE_EUR300_NATIVE_COMMON_LEDGER_MISSING") &&
            !absent.EconomicallyQualified && !absent.OrdersEnabled,
            "SYC1 raw signals cannot become modeled funded trips or a systemic certificate");
        var permuted=NativeSystemicOpportunityCensus.Assess(new(
            source.Reverse().ToArray(),Array.Empty<NativeSystemicPositionLink>(),
            Array.Empty<LedgerClosedFragment>(),null,new[]{"2026-W47","2026-W48"}));
        check(permuted.UniqueNonconflictingOpportunities==absent.UniqueNonconflictingOpportunities &&
            permuted.SameClockOppositeSideRejections==absent.SameClockOppositeSideRejections &&
            permuted.SameInstrumentHoldingOverlapsRemoved==absent.SameInstrumentHoldingOverlapsRemoved,
            "SYC1 overlap and same-clock conflict resolution are invariant to input order");
        var baseBook=new NativeFundedLedger().Summary();
        var fragment1=new LedgerClosedFragment("POS-A","FX",t+100,t+20000,1,
            .3m,0m,0m,0m,0m,0m,.3m,false,"SYNTH_PARTIAL");
        var fragment2=new LedgerClosedFragment("POS-A","FX",t+100,t+40000,1,
            .7m,0m,0m,0m,0m,0m,.7m,true,"SYNTH_FINAL");
        var modeled=NativeSystemicOpportunityCensus.Assess(new(source,
            new[]{new NativeSystemicPositionLink("a","POS-A")},
            new[]{fragment1,fragment2},
            baseBook with {CompleteRoundTrips=1,ClosedNetEur=1m,
                CashEur=301m,LiquidationEquityEur=301m,FreeMarginEur=301m},
            new[]{"2026-W47"}));
        check(modeled.ModeledFundedCompleteTrips is null &&
            modeled.ModeledClosedNetEur is null &&
            modeled.Weeks[0].ModeledFundedCompleteTrips is null &&
            modeled.SystemHard21EvidenceState=="UNKNOWN",
            "SYC2 externally supplied partial/final fragments cannot establish one modeled trip without native event trace");
        var broken=NativeSystemicOpportunityCensus.Assess(new(source,
            new[]{new NativeSystemicPositionLink("a","POS-A")},
            new[]{fragment1,fragment2},
            baseBook with {CompleteRoundTrips=2,ClosedNetEur=1m},
            new[]{"2026-W47"}));
        check(broken.ModeledFundedCompleteTrips is null &&
            broken.Weeks[0].ModeledFundedCompleteTrips is null &&
            broken.MissingEvidence.Contains("COMMON_LEDGER_TRIP_MAPPING_CASH_IDENTITY_OR_FINAL_SETTLEMENT_UNKNOWN"),
            "SYC1 ledger mismatch invalidates financial counts instead of treating missing proof as zero");
        const int n=21;
        var proposals=Enumerable.Range(0,n).Select(i=>P(
            "U"+i,"MULTI_CLASS","S"+i,1,t+i*60000,t+i*60000+45000)).ToArray();
        var links=Enumerable.Range(0,n).Select(i=>new NativeSystemicPositionLink("U"+i,"P"+i)).ToArray();
        var trades=Enumerable.Range(0,n).Select(i=>new LedgerClosedFragment(
            "P"+i,"S"+i,t+i*60000+100,t+i*60000+40000,1,
            1m,0m,0m,0m,0m,0m,1m,true,"SYNTH_COMPLETE")).ToArray();
        var proof=new NativeSystemicSourceProof(true,true,true,true,true,true);
        NativeSystemicCensusResult Run(int trips,bool globalCertificate,string[] weeks)=>
            NativeSystemicOpportunityCensus.Assess(new(
                proposals,links.Take(trips).ToArray(),trades.Take(trips).ToArray(),
                baseBook with {CompleteRoundTrips=trips,ClosedNetEur=trips,
                    CashEur=300m+trips,LiquidationEquityEur=300m+trips,
                    FreeMarginEur=300m+trips,
                    GlobalDrawdownCertified=globalCertificate,MaximumSampledDrawdown=.1m},
                weeks,proof));
        check(Run(21,false,new[]{"2026-W47"}).SystemHard21EvidenceState=="UNKNOWN",
            "SYC1 even 21 synthetic complete trips cannot certify continuous floating risk without a native certificate");
        check(Run(20,true,new[]{"2026-W47"}).SystemHard21EvidenceState=="UNKNOWN",
            "SYC1 20 complete trips fail HARD21 when all required modeled proof flags are asserted");
        check(Run(21,true,new[]{"2026-W47","2026-W48"}).SystemHard21EvidenceState=="UNKNOWN",
            "SYC1 empty predeclared eligible week is never discarded to manufacture frequency success");
        var syntheticCertificate=Run(21,true,new[]{"2026-W47"});
        check(syntheticCertificate.SystemHard21EvidenceState=="UNKNOWN" &&
            syntheticCertificate.Weeks[0].ModeledFundedCompleteTrips is null &&
            syntheticCertificate.MissingEvidence.Contains(
                "INDEPENDENT_ORIGINAL_BROKER_SOURCE_AND_CONTINUOUS_DD_VERIFIER_NOT_CONNECTED") &&
            !syntheticCertificate.EconomicallyQualified && !syntheticCertificate.OrdersEnabled,
            "SYC2 all-true source booleans cannot manufacture authentic HARD21");
        bool invalid=false;
        try{NativeSystemicOpportunityCensus.Assess(new(
            source,Array.Empty<NativeSystemicPositionLink>(),
            Array.Empty<LedgerClosedFragment>(),null,new[]{"2026-W54"}));}
        catch(ArgumentException e){invalid=e.Message=="SYC1_INVALID_CAUSAL_SCOPE";}
        check(invalid,"SYC1 invalid ISO eligibility calendar rejected before any scoring");
    }
}
