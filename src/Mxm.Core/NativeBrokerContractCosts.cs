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

public static class NativeBrokerContractCosts
{
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

    public static void Validate(NativeObservedContractTerms c,decimal units)
    {
        ArgumentNullException.ThrowIfNull(c);
        if(!c.OriginalBrokerAuthenticated || string.IsNullOrWhiteSpace(c.Symbol) ||
            string.IsNullOrWhiteSpace(c.QuoteAsset) || c.ObservedAtUtcMs<=0 ||
            c.MinimumUnits<=0 || c.VolumeStepUnits<=0 || c.LotUnits<=0 ||
            c.MaximumUnits<c.MinimumUnits || units<c.MinimumUnits ||
            units>c.MaximumUnits || (units-c.MinimumUnits)%c.VolumeStepUnits!=0 ||
            c.CommissionType is <1 or >4 || c.MinimumCommissionType is <1 or >2 ||
            c.PreciseRateWire<0 || c.PreciseMinimumWire<0 ||
            c.PnlConversionFeeBps<0 || c.PnlConversionFeeBps>=10000 ||
            (c.MinimumCommissionType==1 && string.IsNullOrWhiteSpace(c.MinimumCommissionAsset)))
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
    public static NativeCostAttribution Quote(
        NativeObservedContractTerms c,NativeMarketCostContext q,
        long? holdingOpenedAt=null,int? side=null)
    {
        Validate(c,q.Units);
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
        decimal feeAssetToEur=c.MinimumCommissionType==2 ? q.QuoteDebitToEur :
            c.MinimumCommissionAsset==c.QuoteAsset ? q.QuoteDebitToEur :
            c.MinimumCommissionAsset=="USD" ? q.UsdToEur :
            q.MinimumFeeAssetToEur ?? throw new ArgumentException("NATIVE_COST_MINIMUM_FX_ROUTE_UNKNOWN");
        decimal floor=(c.PreciseMinimumWire/Wire)*feeAssetToEur;
        // Conservative ask-side for commission sizing on a new entry.
        decimal perUnit=CommissionPerUnit(c,q.Ask,q.QuoteDebitToEur,q.UsdToEur);
        var ledgerQuote=new LedgerQuote(c.Symbol,q.AtUtcMs,q.Bid,q.Ask,
            credit,debit,perUnit,floor,q.MarginRequirementEur/q.Units);
        decimal fee=Math.Max(perUnit*q.Units,floor);
        decimal spread=(q.Ask-q.Bid)*q.Units*((credit+debit)/2m);
        decimal? funding=null;
        if(holdingOpenedAt is long start && side is int orientation)
            funding=SignedFinancing(c,start,q.AtUtcMs,orientation,q.Units,q.QuoteCreditToEur,q.QuoteDebitToEur);
        return new(ledgerQuote,fee,funding,
            2m*q.SlippagePerSideQuote*q.Units*((credit+debit)/2m),
            spread,false,"ORIGINAL_ACCOUNT_CURRENT_CONTRACT_CONDITIONAL_COST");
    }

    public static decimal? SignedFinancing(NativeObservedContractTerms c,
        long openedAt,long closedAt,int side,decimal units,
        decimal quoteCreditToEur,decimal quoteDebitToEur)
    {
        Validate(c,units);
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
