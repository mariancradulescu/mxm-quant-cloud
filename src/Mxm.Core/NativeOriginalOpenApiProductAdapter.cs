using System;
using System.Linq;

namespace Mxm.Core;

// Transform original-account read-only Open API BID/ASK + tariff fields with
// the EXISTING NativeBrokerContractCosts. No new ledger or execution service.
public sealed record NativeOriginalOpenApiMarketMark(
    long At,string Symbol,decimal Bid,decimal Ask,
    decimal QuoteCreditToEur,decimal QuoteDebitToEur,decimal UsdToEur,
    decimal MarginRequirementEur,decimal SlippagePerSideQuote,
    NativeObservedContractTerms Contract,
    decimal? MinimumFeeAssetToEur=null);
public sealed record NativeOriginalOpenApiTape(
    string SourceLabel,NativeHistoricalBars[] Bars,
    NativeOriginalOpenApiMarketMark[] Marks);
public static class NativeOriginalOpenApiProductAdapter
{
    public static NativeHistoricalMarketTape Convert(NativeOriginalOpenApiTape input)
    {
        if(input is null||input.Marks is null||input.Bars is null||
           input.Marks.Length==0)throw new ArgumentException("OPENAPI_PRODUCT_TAPE_EMPTY");
        // Real contract observations often POSTDATE historical price clocks.
        // The price/fill remains historical; its tariff is explicitly an
        // ex-post conditional scenario, never an as-of tariff observation.
        var quotes=input.Marks.Select(m=>
        {
            if(!m.Contract.OriginalBrokerAuthenticated||
               m.Contract.HistoricalTariffContinuityCertified ||
               m.Contract.Symbol!=m.Symbol||
               m.Contract.ObservedAtUtcMs<=0)
                throw new ArgumentException("OPENAPI_PRODUCT_CURRENT_CONTRACT_PROVENANCE_INVALID");
            var ctx=new NativeMarketCostContext(m.At,m.Bid,m.Ask,
                m.QuoteCreditToEur,m.QuoteDebitToEur,m.UsdToEur,
                m.MinimumFeeAssetToEur,m.MarginRequirementEur,
                m.Contract.MinimumUnits,m.SlippagePerSideQuote);
            var priced=NativeBrokerContractCosts.Quote(m.Contract,ctx);
            return new NativeHistoricalQuoteObservation(m.At,priced.Quote,
                m.Contract,m.SlippagePerSideQuote,30);
        }).ToArray();
        return new(input.SourceLabel,input.Bars,quotes);
    }
}
