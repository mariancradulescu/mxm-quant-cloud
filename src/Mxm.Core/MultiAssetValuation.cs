using System.Text.Json;
namespace Mxm.Core;

// Shared source-to-EUR valuation, not a simulator or an execution adapter.
// Current tariffs/margins and sampled FX do not certify historical conditions.
public static class MultiAssetValuation
{
    private sealed record Rates(decimal Credit,decimal Debit,decimal UsdDebit);
    private static decimal N(JsonElement e,string key)=>e.GetProperty(key).GetDecimal();
    private static int I(JsonElement e,string key)=>e.GetProperty(key).GetInt32();
    public static object Assess(JsonElement root)
    {
        if(root.GetProperty("schema").GetString() is not ("mxm-epa1-source-v1" or "mxm-epa2-source-v1" or "mxm-sqp1-source-v1") ||
           !root.GetProperty("readOnly").GetBoolean() || root.GetProperty("depositCurrency").GetString()!="EUR")
            throw new ArgumentException("SOURCE_AND_DEPOSIT_CURRENCY_BINDING");
        var symbols=root.GetProperty("symbols");var output=new Dictionary<string,object>();
        foreach(var point in root.GetProperty("snapshots").EnumerateObject())
        {
            if(point.Value.ValueKind==JsonValueKind.Null)continue;
            var snapshot=point.Value;long nominal=long.Parse(point.Name),at=snapshot.GetProperty("at").GetInt64();
            var quotes=snapshot.GetProperty("quotes");
            if(at<nominal+1000 || at>nominal+(root.GetProperty("schema").GetString()=="mxm-sqp1-source-v1"?21000:11000))throw new ArgumentException("QUOTE_LATENCY");
            foreach(var q in quotes.EnumerateObject())
            {
                if(N(q.Value,"bid")<=0 || N(q.Value,"ask")<N(q.Value,"bid") ||
                    at-q.Value.GetProperty("bidAt").GetInt64() is <0 or >2000 ||
                    at-q.Value.GetProperty("askAt").GetInt64() is <0 or >2000)
                    throw new ArgumentException("UNSYNCHRONIZED_OR_INVALID_QUOTES");
            }
            decimal Bid(string s)=>N(quotes.GetProperty(s),"bid")/100000m;
            decimal Ask(string s)=>N(quotes.GetProperty(s),"ask")/100000m;
            Rates Convert(string currency)=>currency switch {
                "EUR"=>new(1,1,Ask("EURUSD")),
                "USD"=>new(1/Ask("EURUSD"),1/Bid("EURUSD"),1),
                "JPY"=>new(1/(Ask("USDJPY")*Ask("EURUSD")),1/(Bid("USDJPY")*Bid("EURUSD")),1/Bid("USDJPY")),
                "CAD"=>new(1/(Ask("USDCAD")*Ask("EURUSD")),1/(Bid("USDCAD")*Bid("EURUSD")),1/Bid("USDCAD")),
                _=>throw new ArgumentException("UNSUPPORTED_FX_ROUTE")};
            var valued=new Dictionary<string,object>();var missing=new Dictionary<string,string>();
            foreach(var prop in symbols.EnumerateObject())
            {
                try
                {
                    var c=prop.Value.GetProperty("contract");string symbol=prop.Name;
                    string ccy=prop.Value.GetProperty("quoteAsset").GetString()!;var rate=Convert(ccy);
                    decimal feeRate=N(c,"pnlConversionFeeRate")/10000m;
                    if(feeRate<0 || feeRate>=1)throw new ArgumentException("INVALID_FX_FEE");
                    decimal unitsPerLot=N(c,"lotSize")/100m,r=N(c,"preciseTradingCommissionRate"),linear;
                    if(unitsPerLot<=0 || r<0)throw new ArgumentException("INVALID_COMMISSION_TERMS");
                    // Commission notional uses adverse observed conversion and
                    // the larger BID/ASK value; this is an explicit cost bound.
                    linear=I(c,"commissionType") switch {
                        1=>r/100000000m*Ask(symbol)*rate.UsdDebit/1000000m*Convert("USD").Debit,
                        2=>r/100000000m/unitsPerLot*Convert("USD").Debit,
                        3=>r/100000m/100m*Ask(symbol)*rate.Debit,
                        4=>r/100000000m/unitsPerLot*rate.Debit,
                        _=>throw new ArgumentException("UNSUPPORTED_COMMISSION_TYPE")};
                    decimal floor=N(c,"preciseMinCommission")/100000000m;
                    if(floor<0)throw new ArgumentException("NEGATIVE_COMMISSION_FLOOR");
                    string floorCcy=I(c,"minCommissionType")==2 ? ccy : I(c,"minCommissionType")==1 ?
                        c.GetProperty("minCommissionAsset").GetString()! : throw new ArgumentException("COMMISSION_FLOOR_TYPE");
                    floor*=Convert(floorCcy).Debit;
                    valued[symbol]=new {Bid=Bid(symbol),Ask=Ask(symbol),
                        EurCreditPerQuote=rate.Credit*(1-feeRate),EurDebitPerQuote=rate.Debit*(1+feeRate),
                        FeeLinearEurPerUnit=linear,FeeFloorEur=floor,
                        CommissionStatus="CURRENT_TARIFF_ADVERSE_NOTIONAL_CONVERSION_SCENARIO_NOT_HISTORICAL_FEE_CERTIFICATE"};
                }
                catch(Exception e) when(e is ArgumentException or KeyNotFoundException or InvalidOperationException)
                {missing[prop.Name]="COST_OR_CURRENCY_EVIDENCE_INCOMPLETE";}
            }
            output[point.Name]=new {At=at,Quotes=valued,Missing=missing};
        }
        return new {Snapshots=output,HistoricalTariffsConfirmed=false,ActualFills=false,GlobalDrawdownCertified=false};
    }
}
