using System;
using System.Collections.Generic;

namespace Mxm.Core;

/// <summary>
/// CURRENT original-account ProtoOASymbol tariff fields with an as-observed
/// timestamp. Not a historical contract or actual-fill certificate. This
/// adapter supplies the EXISTING NativeFundedLedger LedgerQuote/FINANCING events;
/// it does not settle cash, select models or submit any order.
/// </summary>
public sealed record NativeObservedContractTerms(
    string Symbol, string QuoteAsset, long ObservedAtUtcMs,
    decimal MinimumUnits, decimal VolumeStepUnits, decimal MaximumUnits,
    decimal LotUnits, int CommissionType, long PreciseRateWire,
    int MinimumCommissionType, long PreciseMinimumWire,
    string? MinimumCommissionAsset, int PnlConversionFeeBps,
    int? SwapCalculationType, decimal? LongSwap, decimal? ShortSwap,
    int? PipPosition, int? SwapPeriodHours, int? SwapTimeUtcMinute,
    int? TripleSwapWeekday, bool? ChargeSwapAtWeekends,
    int? SkipSwapPeriods, bool OriginalBrokerAuthenticated = true,
    bool HistoricalTariffContinuityCertified = false);

public sealed record NativeMarketCostContext(
    long AtUtcMs, decimal Bid, decimal Ask, decimal QuoteCreditToEur,
    decimal QuoteDebitToEur, decimal UsdToEur,
    decimal? MinimumFeeAssetToEur, decimal MarginRequirementEur,
    decimal Units, decimal SlippagePerSideQuote);

public sealed record NativeCostAttribution(
    LedgerQuote Quote, decimal OneSideCommissionEur,
    decimal? FinancingSignedEur, decimal SlippageRoundTripEur,
    decimal? SpreadRoundTripEur, bool HistoricalExecutionCertified,
    string EvidenceLevel);

// A route is evidence about genuine as-of original-market BID/ASK, NOT a
// replacement market feed, broker fill or synthetic rate. Its caller must
// bind every hop to the authenticated original account source.
public sealed record NativeOriginalFxHop(
    string Symbol,string BaseAsset,string QuoteAsset,long AtUtcMs,
    decimal Bid,decimal Ask,bool OriginalBrokerAuthenticated);
public sealed record NativeOriginalFxRate(
    decimal CreditToEur,decimal DebitToEur,string[] RouteSymbols);

public static class NativeBrokerContractCosts
{
    /// <summary>
    /// Compose genuinely observed as-of bid/ask conversion rates into the
    /// EXISTING QuoteCreditToEur / QuoteDebitToEur ledger fields.
    /// On each leg a sale of the source asset uses BID; a purchase uses ASK.
    /// For reverse pairs the corresponding reciprocal ASK/BID is used.
    /// This accepts observed market facts only: no guessed FX, no mid-rate,
    /// no future/old quotes, no missing path and no zero-cost fallback.
    /// </summary>
    public static NativeOriginalFxRate ComposeCausalQuoteToEur(
        string quoteAsset,long decisionClockUtcMs,
        IReadOnlyList<NativeOriginalFxHop> route)
    {
        if(string.IsNullOrWhiteSpace(quoteAsset)||
           decisionClockUtcMs<=0||route is null)
            throw new ArgumentException("NATIVE_FX_ROUTE_INPUT_INVALID");
        if(quoteAsset=="EUR")
        {
            if(route.Count!=0)
                throw new ArgumentException("NATIVE_FX_EUR_ROUTE_MUST_BE_EMPTY");
            return new NativeOriginalFxRate(1m,1m,Array.Empty<string>());
        }
        if(route.Count is <1 or >4)
            throw new ArgumentException("NATIVE_FX_ROUTE_MISSING_OR_EXCESSIVE");
        decimal credit=1m,debit=1m;
        string current=quoteAsset;
        var visited=new HashSet<string>(StringComparer.Ordinal){current};
        var names=new List<string>();
        foreach(var hop in route)
        {
            if(!hop.OriginalBrokerAuthenticated ||
               string.IsNullOrWhiteSpace(hop.Symbol) ||
               string.IsNullOrWhiteSpace(hop.BaseAsset) ||
               string.IsNullOrWhiteSpace(hop.QuoteAsset) ||
               hop.BaseAsset==hop.QuoteAsset ||
               hop.AtUtcMs<=0 || hop.AtUtcMs>decisionClockUtcMs ||
               decisionClockUtcMs-hop.AtUtcMs>60000L ||
               hop.Bid<=0m || hop.Ask<hop.Bid)
                throw new ArgumentException("NATIVE_FX_ASOF_OR_ORIGINAL_BIDASK_INVALID");
            if(hop.BaseAsset==current)
            {
                credit*=hop.Bid;
                debit*=hop.Ask;
                current=hop.QuoteAsset;
            }
            else if(hop.QuoteAsset==current)
            {
                credit/=hop.Ask;
                debit/=hop.Bid;
                current=hop.BaseAsset;
            }
            else throw new ArgumentException("NATIVE_FX_CONVERSION_CHAIN_DISCONNECTED");
            if(!visited.Add(current))
                throw new ArgumentException("NATIVE_FX_CONVERSION_ROUTE_CYCLE");
            names.Add(hop.Symbol);
        }
        if(current!="EUR" || credit<=0m || debit<credit)
            throw new ArgumentException("NATIVE_FX_CONVERSION_EUR_END_MISSING");
        return new NativeOriginalFxRate(credit,debit,names.ToArray());
    }

    const decimal Million = 1000000m;
    const decimal Wire = 100000000m;
    static decimal Pip(int position)
    {
        if(position<0 || position>18)
            throw new ArgumentException("NATIVE_COST_PIP_POSITION_INVALID");
        decimal value=1m;
        for(int i=0;i<position;i++)value/=10m;
        return value;
    }

    public static void Validate(NativeObservedContractTerms c,decimal units,bool requireOriginalBroker=true)
    {
        ArgumentNullException.ThrowIfNull(c);
        if((requireOriginalBroker && !c.OriginalBrokerAuthenticated) || string.IsNullOrWhiteSpace(c.Symbol) ||
            string.IsNullOrWhiteSpace(c.QuoteAsset) || c.ObservedAtUtcMs<=0 ||
            c.MinimumUnits<=0 || c.VolumeStepUnits<=0 || c.LotUnits<=0 ||
            c.MaximumUnits<c.MinimumUnits || units<c.MinimumUnits ||
            units>c.MaximumUnits || (units-c.MinimumUnits)%c.VolumeStepUnits!=0 ||
            c.CommissionType is <1 or >4 || c.MinimumCommissionType is <1 or >2 ||
            c.PreciseRateWire<0 || c.PreciseMinimumWire<0 ||
            c.PnlConversionFeeBps<0 || c.PnlConversionFeeBps>=10000 ||
            (c.PreciseMinimumWire>0 && c.MinimumCommissionType==1 && string.IsNullOrWhiteSpace(c.MinimumCommissionAsset)))
            throw new ArgumentException("NATIVE_COST_CONTRACT_OR_VOLUME_UNVERIFIED");
    }
    static decimal CommissionPerUnit(NativeObservedContractTerms c, decimal price,
        decimal quoteToEur,decimal usdToEur)
    {
        decimal rate=c.PreciseRateWire/Wire;
        return c.CommissionType switch
        {
            1 => (rate/Million)*price*quoteToEur, // USD/million USD notional
            2 => (rate/c.LotUnits)*usdToEur,       // USD per lot
            3 => (c.PreciseRateWire/100000m/100m)*price*quoteToEur,
            4 => (rate/c.LotUnits)*quoteToEur,     // quote currency per lot
            _ => throw new ArgumentException("NATIVE_COST_UNKNOWN_COMMISSION_TYPE")
        };
    }
    // Exact original Open API contract path remains strictly authenticated.
    public static NativeCostAttribution Quote(
        NativeObservedContractTerms c,NativeMarketCostContext q,
        long? holdingOpenedAt=null,int? side=null,bool executionIsBuy=true)
        =>Price(c,q,holdingOpenedAt,side,executionIsBuy,true);

    // cTrader Algo Symbol fields have NOT been cryptographically authenticated
    // against the original Pepperstone Open API account contract. Never set the
    // original-account flag to true just to obtain a conditional research price.
    public static NativeCostAttribution QuoteCurrentAlgo(
        NativeObservedContractTerms c,NativeMarketCostContext q,
        long? holdingOpenedAt=null,int? side=null,bool executionIsBuy=true)
    {
        if(c.OriginalBrokerAuthenticated)
            throw new ArgumentException("ALGO_CURRENT_CONTRACT_PROVENANCE_MISMATCH");
        return Price(c,q,holdingOpenedAt,side,executionIsBuy,false);
    }

    private static NativeCostAttribution Price(NativeObservedContractTerms c,
        NativeMarketCostContext q,long? holdingOpenedAt,int? side,
        bool executionIsBuy,bool requireOriginalBroker)
    {
        Validate(c,q.Units,requireOriginalBroker);
        if(q.AtUtcMs<=0 || q.Bid<=0 || q.Ask<q.Bid ||
            q.QuoteCreditToEur<=0 || q.QuoteDebitToEur<q.QuoteCreditToEur ||
            q.UsdToEur<=0 || q.MarginRequirementEur<=0 ||
            q.SlippagePerSideQuote<0 ||
            (q.MinimumFeeAssetToEur is decimal x && x<=0))
            throw new ArgumentException("NATIVE_COST_QUOTE_OR_ROUTE_INVALID");
        // Preserve signed FX conversion and conversion fee explicitly within
        // existing LedgerQuote EurCredit/EurDebit; never add spread to bid/ask.
        decimal pnl=q.PnlConversionRate(c.PnlConversionFeeBps);
        decimal credit=q.QuoteCreditToEur*(1-pnl);
        decimal debit=q.QuoteDebitToEur*(1+pnl);
        decimal feeAssetToEur=c.PreciseMinimumWire==0 ? 0m :
            c.MinimumCommissionType==2 ? q.QuoteDebitToEur :
            c.MinimumCommissionAsset==c.QuoteAsset ? q.QuoteDebitToEur :
            c.MinimumCommissionAsset=="USD" ? q.UsdToEur :
            q.MinimumFeeAssetToEur ?? throw new ArgumentException("NATIVE_COST_MINIMUM_FX_ROUTE_UNKNOWN");
        decimal floor=(c.PreciseMinimumWire/Wire)*feeAssetToEur;
        // Commission follows actual proposed execution SIDE: buy at ASK,
        // sell at BID. Critical for percentage-of-notional broker tariffs.
        // Distinct from spread, already in the executable price.
        decimal executablePrice=executionIsBuy?q.Ask:q.Bid;
        decimal perUnit=CommissionPerUnit(c,executablePrice,q.QuoteDebitToEur,q.UsdToEur);
        var ledgerQuote=new LedgerQuote(c.Symbol,q.AtUtcMs,q.Bid,q.Ask,
            credit,debit,perUnit,floor,q.MarginRequirementEur/q.Units);
        decimal fee=Math.Max(perUnit*q.Units,floor);
        decimal spread=(q.Ask-q.Bid)*q.Units*((credit+debit)/2m);
        decimal? funding=null;
        if(holdingOpenedAt is long start && side is int orientation)
            funding=FinancingCore(c,start,q.AtUtcMs,orientation,q.Units,q.QuoteCreditToEur,q.QuoteDebitToEur,requireOriginalBroker);
        return new(ledgerQuote,fee,funding,
            2m*q.SlippagePerSideQuote*q.Units*((credit+debit)/2m),
            spread,false,requireOriginalBroker?
            "ORIGINAL_ACCOUNT_CURRENT_CONTRACT_CONDITIONAL_COST":
            "CTRADER_ALGO_CURRENT_CONDITIONAL_UNATTESTED_NOT_ORIGINAL_ACCOUNT");
    }

    public static decimal? SignedFinancing(NativeObservedContractTerms c,
        long openedAt,long closedAt,int side,decimal units,
        decimal quoteCreditToEur,decimal quoteDebitToEur)
        =>FinancingCore(c,openedAt,closedAt,side,units,quoteCreditToEur,quoteDebitToEur,true);

    public static decimal? SignedFinancingCurrentAlgo(NativeObservedContractTerms c,
        long openedAt,long closedAt,int side,decimal units,
        decimal quoteCreditToEur,decimal quoteDebitToEur)
    {
        if(c.OriginalBrokerAuthenticated)
            throw new ArgumentException("ALGO_CURRENT_CONTRACT_PROVENANCE_MISMATCH");
        return FinancingCore(c,openedAt,closedAt,side,units,quoteCreditToEur,quoteDebitToEur,false);
    }

    private static decimal? FinancingCore(NativeObservedContractTerms c,
        long openedAt,long closedAt,int side,decimal units,
        decimal quoteCreditToEur,decimal quoteDebitToEur,bool requireOriginalBroker)
    {
        Validate(c,units,requireOriginalBroker);
        if(side is not (-1 or 1) || openedAt<0 || closedAt<openedAt ||
            quoteCreditToEur<=0 || quoteDebitToEur<quoteCreditToEur)
            throw new ArgumentException("NATIVE_COST_FINANCING_INPUT");
        // Any non-zero crossing must use original contract charge time, never
        // a generic UTC midnight. Only genuine 24h PIPS schedules modeled.
        if(c.SwapPeriodHours!=24 || c.SwapTimeUtcMinute is not int minute ||
           minute<0 || minute>=1440 || c.ChargeSwapAtWeekends is not bool weekends)
            return null;
        long day=86400000L, chargeMinute=minute*60000L;
        long first=(openedAt/day)*day+chargeMinute;
        if(first<=openedAt)first+=day;
        if(first>closedAt)return 0m; // known intraday no rollover charge
        if(c.SwapCalculationType!=0 || c.PipPosition is not int pip ||
           c.TripleSwapWeekday is not int triple || triple<1 || triple>7 ||
           c.SkipSwapPeriods is not int skip || skip<0)
            return null;
        decimal? swap=side>0?c.LongSwap:c.ShortSwap;
        if(swap is null)return null;
        decimal signed=0m;
        int eligible=0;
        for(long t=first;t<=closedAt;t+=day)
        {
            if((t-openedAt)>40L*day)return null;
            var d=DateTimeOffset.FromUnixTimeMilliseconds(t).DayOfWeek;
            if(!weekends && (d==DayOfWeek.Saturday||d==DayOfWeek.Sunday))continue;
            eligible++;
            if(eligible<=skip)continue;
            int iso=d==DayOfWeek.Sunday?7:(int)d;
            decimal multiplier=iso==triple?3m:1m;
            decimal charge=(swap.Value*Pip(pip)*units)*multiplier;
            signed+=charge*(charge>=0?quoteCreditToEur:quoteDebitToEur);
        }
        return signed;
    }

    // Reuse the EXISTING native money ledger's FINANCING event; research facts
    // remain model-only and do not simulate broker cash transactions.
    public static LedgerEvent FinancingFact(string eventId,string positionId,
        NativeObservedContractTerms contract,long clock,int side,decimal units,
        long openedAt,decimal quoteCreditToEur,decimal quoteDebitToEur,
        string evidenceHash,LedgerQuote[] freshQuotes)
    {
        decimal? signed=SignedFinancing(contract,openedAt,clock,side,units,
            quoteCreditToEur,quoteDebitToEur);
        if(signed is not decimal cash)
            throw new InvalidOperationException("NATIVE_COST_FINANCING_NOT_CERTIFIED");
        return new(eventId,clock,"FINANCING",positionId,contract.Symbol,side,
            units,0,0,0,0,0,0,0,"CONTRACT_TERMS_CONDITIONAL_MODEL",
            evidenceHash,freshQuotes,cash);
    }
    static decimal PnlConversionRate(this NativeMarketCostContext q,int bps)=>
        bps/10000m;
}
