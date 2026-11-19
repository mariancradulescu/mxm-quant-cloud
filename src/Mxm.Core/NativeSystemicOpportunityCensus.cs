using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Core;

// Prospective SYSTEM scope only. This does not alter any closed study or historical
// scorecard. Every accepted event still requires a separate real Core ledger fill.
public sealed record NativeSystemicProposal(
    string ProposalId,string Family,string Symbol,int Side,long DecisionAt,long PlannedExitAt);
public sealed record NativeSystemicPositionLink(string ProposalId,string PositionId);
public sealed record NativeSystemicSourceProof(
    bool SingleOriginalEur300Account,
    bool LegalBrokerMinimumStepAndMargin,
    bool HistoricPairedBidAskCostsFxAndFinancing,
    bool EveryPositionAndFloatingMarkReconciled,
    bool ContinuousFloatingDrawdownCertified,
    bool ExAnteEligibleWeekCalendarVerified);
public sealed record NativeSystemicCensusInput(
    NativeSystemicProposal[] Proposals,
    NativeSystemicPositionLink[] PositionLinks,
    LedgerClosedFragment[] ClosedFragments,
    LedgerSummary? CommonLedger,
    string[] ExAnteEligibleIsoWeeks,
    NativeSystemicSourceProof? SourceProof=null,
    LedgerEvent[]? ModelEventTrace=null);
public sealed record NativeSystemicWeek(
    string IsoWeek,Dictionary<string,int> RawPerSymbolFamily,
    int RawCombinedProposals,int UniqueNonconflictingOpportunities,
    int? ModeledFundedCompleteTrips,string Hard21EvidenceState);
public sealed record NativeSystemicCensusResult(
    int RawCombinedProposals,int SameClockOppositeSideRejections,
    int SameSideDuplicatesRemoved,int SameInstrumentHoldingOverlapsRemoved,
    int UniqueNonconflictingOpportunities,int? ModeledFundedCompleteTrips,
    decimal? ModeledClosedNetEur,string SystemHard21EvidenceState,
    NativeSystemicWeek[] Weeks,string[] MissingEvidence,
    bool EconomicallyQualified=false,bool OrdersEnabled=false);

// Only chronological PREDECISION identity and planned holding are inspected for
// de-duplication: never any future price, model winner or economic outcome.
public static class NativeSystemicOpportunityCensus
{
    private static string Week(long milliseconds)
    {
        var t=DateTimeOffset.FromUnixTimeMilliseconds(milliseconds).UtcDateTime;
        return ISOWeek.GetYear(t)+"-W"+ISOWeek.GetWeekOfYear(t).ToString("00",CultureInfo.InvariantCulture);
    }

    private static bool ValidWeek(string week)
    {
        if(week is null || week.Length!=8 || week[4]!='-' || week[5]!='W' ||
           !int.TryParse(week.Substring(0,4),NumberStyles.None,CultureInfo.InvariantCulture,out int year) ||
           !int.TryParse(week.Substring(6,2),NumberStyles.None,CultureInfo.InvariantCulture,out int number) ||
           year<1 || year>9999)return false;
        return number>=1 && number<=ISOWeek.GetWeeksInYear(year);
    }

    public static NativeSystemicCensusResult Assess(NativeSystemicCensusInput x)
    {
        if(x is null || x.Proposals is null || x.PositionLinks is null ||
           x.ClosedFragments is null || x.ExAnteEligibleIsoWeeks is null ||
           x.ExAnteEligibleIsoWeeks.Any(w=>!ValidWeek(w)) ||
           x.ExAnteEligibleIsoWeeks.Distinct(StringComparer.Ordinal).Count()!=x.ExAnteEligibleIsoWeeks.Length ||
           x.Proposals.Any(p=>string.IsNullOrWhiteSpace(p.ProposalId) ||
               string.IsNullOrWhiteSpace(p.Family) || string.IsNullOrWhiteSpace(p.Symbol) ||
               (p.Side!=1 && p.Side!=-1) || p.DecisionAt<0 || p.PlannedExitAt<=p.DecisionAt) ||
           x.Proposals.Select(p=>p.ProposalId).Distinct(StringComparer.Ordinal).Count()!=x.Proposals.Length ||
           x.PositionLinks.Any(l=>string.IsNullOrWhiteSpace(l.ProposalId) ||
               string.IsNullOrWhiteSpace(l.PositionId)) ||
           x.PositionLinks.Select(l=>l.ProposalId).Distinct(StringComparer.Ordinal).Count()!=x.PositionLinks.Length ||
           x.PositionLinks.Select(l=>l.PositionId).Distinct(StringComparer.Ordinal).Count()!=x.PositionLinks.Length)
            throw new ArgumentException("SYC1_INVALID_CAUSAL_SCOPE");

        var accepted=new List<NativeSystemicProposal>();
        var heldUntil=new Dictionary<string,long>(StringComparer.Ordinal);
        int conflicts=0,duplicates=0,overlaps=0;
        foreach(var g in x.Proposals.GroupBy(p=>(p.Symbol,p.DecisionAt))
            .OrderBy(g=>g.Key.Symbol,StringComparer.Ordinal).ThenBy(g=>g.Key.DecisionAt))
        {
            var candidates=g.OrderBy(p=>p.ProposalId,StringComparer.Ordinal).ToArray();
            if(candidates.Select(p=>p.Side).Distinct().Count()!=1)
            {
                conflicts+=candidates.Length;
                continue; // Never resolve opposite sides with future returns.
            }
            duplicates+=candidates.Length-1; // Same symbol+clock+side, across families.
            var p=candidates[0]; // Stable ex-ante ID tie; not a model score.
            if(heldUntil.TryGetValue(p.Symbol,out long end) && p.DecisionAt<end)
            {
                overlaps++;
                continue; // Conservative candidate clock; no phantom second trip.
            }
            accepted.Add(p);
            heldUntil[p.Symbol]=p.PlannedExitAt;
        }

        var missing=new List<string>();
        bool matched=false;
        var completed=new List<(string PositionId,long ClosedAt)>();
        if(x.CommonLedger is null)missing.Add("ONE_EUR300_NATIVE_COMMON_LEDGER_MISSING");
        else
        {
            var acceptedIds=accepted.Select(p=>p.ProposalId).ToHashSet(StringComparer.Ordinal);
            var links=x.PositionLinks.ToDictionary(l=>l.PositionId,l=>l.ProposalId,StringComparer.Ordinal);
            var proposals=accepted.ToDictionary(p=>p.ProposalId,StringComparer.Ordinal);
            bool mapped=x.PositionLinks.All(l=>acceptedIds.Contains(l.ProposalId)) &&
                x.ClosedFragments.All(f=>links.ContainsKey(f.PositionId)) &&
                x.ClosedFragments.All(f=>f.OpenedAt>=0 && f.ClosedAt>=f.OpenedAt &&
                    proposals.TryGetValue(links[f.PositionId],out var p) &&
                    f.OpenedAt>=p.DecisionAt && f.ClosedAt<=p.PlannedExitAt) &&
                x.ClosedFragments.GroupBy(f=>f.PositionId).All(g=>g.Count(f=>f.CompletesRoundTrip)==1) &&
                x.CommonLedger.CompleteRoundTrips==
                    x.ClosedFragments.Count(f=>f.CompletesRoundTrip) &&
                Math.Abs(x.CommonLedger.ClosedNetEur-x.ClosedFragments.Sum(f=>f.NetEur))<=0.0000001m &&
                Math.Abs(x.CommonLedger.CashEur-
                    (OwnerRiskAuthority.InitialCapitalEur+x.CommonLedger.ClosedNetEur))<=0.0000001m &&
                x.CommonLedger.UsedMarginEur==0m &&
                x.CommonLedger.FreeMarginEur==x.CommonLedger.CashEur &&
                x.CommonLedger.LiquidationEquityEur==x.CommonLedger.CashEur &&
                !x.CommonLedger.HistoryEvidenceIncomplete &&
                x.CommonLedger.OpenPositions==0 && x.CommonLedger.PendingIntents==0;
            // The fragments do not include Side. It MUST be obtained from the
            // OPEN_FILL and REQUEST_OPEN facts of the SAME native model book.
            // Replaying caller-provided model events is necessary for technical
            // modeled counts, but is NOT original broker source authentication.
            bool traceValid=false;
            if(mapped && x.ModelEventTrace is {Length: > 0} events)
            {
                try
                {
                    var live=new NativeFundedLedger();
                    foreach(var e in events) live.Apply(e);
                    var rebuilt=live.Summary();
                    var fragments=live.ClosedFragments();
                    // The native ledger treats an exactly repeated EventId as
                    // idempotent. Match physical volumes on unique event IDs;
                    // replay itself rejects a conflicting duplicate payload.
                    var unique=events.DistinctBy(e=>e.EventId).ToArray();
                    var opens=unique.Where(e=>e.Kind=="OPEN_FILL").ToArray();
                    var requests=unique.Where(e=>e.Kind=="REQUEST_OPEN").ToArray();
                    var closures=unique.Where(e=>e.Kind=="CLOSE_FILL").ToArray();
                    bool identity=opens.Length==x.PositionLinks.Length &&
                        requests.Length==opens.Length &&
                        opens.Select(e=>e.PositionId).Distinct(StringComparer.Ordinal).Count()==opens.Length &&
                        opens.All(fill=>links.TryGetValue(fill.PositionId,out var proposalId) &&
                            proposals.TryGetValue(proposalId,out var p) &&
                            fill.Symbol==p.Symbol && fill.Side==p.Side &&
                            requests.Count(req=>req.PositionId==fill.PositionId &&
                                req.Symbol==p.Symbol && req.Side==p.Side && req.Units==fill.Units)==1 &&
                            closures.Where(e=>e.PositionId==fill.PositionId).All(close=>
                                close.Symbol==p.Symbol && close.Side==p.Side) &&
                            closures.Where(e=>e.PositionId==fill.PositionId).Sum(close=>close.Units)==fill.Units) &&
                        x.ClosedFragments.All(f=>links.TryGetValue(f.PositionId,out var id) &&
                            proposals.TryGetValue(id,out var p) && f.Symbol==p.Symbol) &&
                        fragments.SequenceEqual(x.ClosedFragments);
                    traceValid=identity &&
                        rebuilt.EventChainHash==x.CommonLedger.EventChainHash &&
                        rebuilt.CompleteRoundTrips==x.CommonLedger.CompleteRoundTrips &&
                        rebuilt.ClosedNetEur==x.CommonLedger.ClosedNetEur &&
                        rebuilt.CashEur==x.CommonLedger.CashEur &&
                        rebuilt.LiquidationEquityEur==x.CommonLedger.LiquidationEquityEur &&
                        rebuilt.UsedMarginEur==x.CommonLedger.UsedMarginEur &&
                        rebuilt.FreeMarginEur==x.CommonLedger.FreeMarginEur &&
                        rebuilt.MaximumSampledDrawdown==x.CommonLedger.MaximumSampledDrawdown &&
                        rebuilt.ObservedPeakEur==x.CommonLedger.ObservedPeakEur &&
                        rebuilt.OpenPositions==0 && rebuilt.PendingIntents==0 &&
                        !rebuilt.HistoryEvidenceIncomplete;
                }
                catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or OverflowException)
                {
                    traceValid=false;
                }
            }
            matched=mapped && traceValid;
            if(matched)
                foreach(var f in x.ClosedFragments.Where(f=>f.CompletesRoundTrip))
                    completed.Add((f.PositionId,f.ClosedAt));
            else missing.Add("NATIVE_EVENT_TRACE_SYMBOL_SIDE_VOLUME_SETTLEMENT_OR_CASH_IDENTITY_UNVERIFIED");
        }

        // Caller booleans and LedgerSummary.GlobalDrawdownCertified are never
        // independently authenticated broker proof. There is deliberately NO
        // CERTIFIED branch until a separate original-source verifier is wired.
        var eligible=x.ExAnteEligibleIsoWeeks.ToHashSet(StringComparer.Ordinal);
        bool completeCalendarScope=x.Proposals.All(p=>eligible.Contains(Week(p.DecisionAt))) &&
            x.ClosedFragments.All(f=>eligible.Contains(Week(f.ClosedAt)));
        if(!completeCalendarScope)missing.Add("ELIGIBLE_WEEK_CALENDAR_INCOMPLETE_OR_OUTSIDE_SCOPE");
        missing.Add("INDEPENDENT_ORIGINAL_BROKER_SOURCE_AND_CONTINUOUS_DD_VERIFIER_NOT_CONNECTED");
        bool sourceComplete=false;
        var weeks=x.ExAnteEligibleIsoWeeks.OrderBy(w=>w,StringComparer.Ordinal).Select(week=>
        {
            var raw=x.Proposals.Where(p=>Week(p.DecisionAt)==week).ToArray();
            var streams=raw.GroupBy(p=>p.Symbol+"/"+p.Family)
                .OrderBy(g=>g.Key,StringComparer.Ordinal)
                .ToDictionary(g=>g.Key,g=>g.Count(),StringComparer.Ordinal);
            int? complete=matched?completed.Count(f=>Week(f.ClosedAt)==week):null;
            string state=!sourceComplete?"UNKNOWN":
                complete>=OwnerRiskAuthority.MinimumSystemRoundTripsPerEligibleWeek?
                "CERTIFIED":"FAILED_THIS_ELIGIBLE_WEEK";
            return new NativeSystemicWeek(week,streams,raw.Length,
                accepted.Count(p=>Week(p.DecisionAt)==week),complete,state);
        }).ToArray();
        if(weeks.Length==0)missing.Add("EX_ANTE_ELIGIBLE_WEEKS_NOT_SPECIFIED");
        string systemic=weeks.Length==0?"UNKNOWN":
            weeks.All(w=>w.Hard21EvidenceState=="CERTIFIED")?"CERTIFIED":
            weeks.Any(w=>w.Hard21EvidenceState=="FAILED_THIS_ELIGIBLE_WEEK")?
            "FAILED_THIS_EVALUATED_CALENDAR":"UNKNOWN";
        return new NativeSystemicCensusResult(x.Proposals.Length,conflicts,duplicates,
            overlaps,accepted.Count,matched?completed.Count:null,
            matched?x.CommonLedger!.ClosedNetEur:null,systemic,weeks,
            missing.Distinct(StringComparer.Ordinal).ToArray());
    }
}
