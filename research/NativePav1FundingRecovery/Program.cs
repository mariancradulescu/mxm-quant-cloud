using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

bool marketTime=args.Length==3&&args[2]=="--market-time";
if((args.Length!=2&&!marketTime)||File.Exists(args[1]))throw new ArgumentException("PAV1_FUNDING_PATHS");
using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));var input=doc.RootElement;
if(input.GetProperty("Study").GetString()!="PAV1_CLOSED_FUNDING_RECOVERY_1"||
    input.GetProperty("EconomicPolicyReruns").GetInt32()!=0)throw new InvalidDataException("PAV1_FUNDING_SCOPE");
var options=new JsonSerializerOptions {NumberHandling=JsonNumberHandling.AllowReadingFromString};
var actual=input.GetProperty("Contract").Deserialize<NativeObservedContractTerms>(options)!;
if(actual.Symbol!="ETHUSD"||actual.QuoteAsset!="USD")throw new InvalidDataException("PAV1_FUNDING_CONTRACT");
// Exactly the original research tariff scenario; retain the true acquisition
// date separately. This does not attest historical tariff continuity.
var contract=actual with {ObservedAtUtcMs=input.GetProperty("ScenarioObservedAtUtcMs").GetInt64()};
var witnesses=input.GetProperty("Witnesses").EnumerateArray().ToArray();
var account=input.GetProperty("Account");
NativeMarketTimeCalendar? calendar=null;
var closing=new Dictionary<string,NativeMarketTimePrice>();
if(marketTime)
{
    var c=input.GetProperty("MarketTimeCalendar");
    calendar=new(c.GetProperty("From").GetInt64(),c.GetProperty("Through").GetInt64(),
        c.GetProperty("OpenClocks").Deserialize<long[]>(),c.GetProperty("AmbiguousClocks").Deserialize<long[]>(),
        c.GetProperty("EvidenceSha256").GetString()!);
    if(!calendar.Valid)throw new InvalidDataException("PAV1_FUNDING_MARKET_TIME_CALENDAR");
}
decimal? Price(string symbol,string side,long at,long age)
{
    var rows=witnesses.Where(w=>w.GetProperty("Target").GetProperty("Symbol").GetString()==symbol&&
        w.GetProperty("Target").GetProperty("Side").GetString()==side&&
        w.GetProperty("Target").GetProperty("At").GetInt64()==at).ToArray();
    if(rows.Length!=1)return null;
    var prefix=rows[0].GetProperty("Witness").Deserialize<NativeHistoricalFundingPrefix>(options);
    if(marketTime&&symbol=="EURUSD"&&prefix is not null)
    {
        var point=NativeMarketTimeFx.Resolve(prefix,at,calendar,age);
        if(point is not null)closing[$"{symbol}/{side}/{at}"]=point;
        return point?.Price;
    }
    return prefix?.PriceAtCharge(at,age);
}
var results=new List<object>();
foreach(var book in input.GetProperty("Books").EnumerateArray())
{
    var w=book.GetProperty("Window");
    if(w.GetProperty("Symbol").GetString()!=actual.Symbol||w.GetProperty("ClosedAt").ValueKind==JsonValueKind.Null)
        throw new InvalidDataException("PAV1_FUNDING_CLOSED_WINDOW");
    var chargeAudit=new List<object>();
    decimal? amount=NativeBrokerContractCosts.ObservedDailySwapEur(contract,w.GetProperty("FromExclusive").GetInt64(),
        w.GetProperty("ClosedAt").GetInt64(),w.GetProperty("Side").GetInt32(),w.GetProperty("Units").GetDecimal(),
        account.GetProperty("accountSwapFree").GetBoolean(),account.GetProperty("accountType").GetInt32(),
        account.GetProperty("moneyDigits").GetInt32(),input.GetProperty("PriceDigits").GetInt32(),at=>
        {
            decimal? bid=Price("ETHUSD","BID",at,345600000L),fxBid=Price("EURUSD","BID",at,7200000L),
                fxAsk=Price("EURUSD","ASK",at,7200000L);
            var fx=fxBid is >0m&&fxAsk>=fxBid?new NativeOriginalFxRate(1m/fxAsk.Value,1m/fxBid.Value,new[]{"EURUSD"}):null;
            chargeAudit.Add(new {At=at,Bid=bid,FxBid=fxBid,FxAsk=fxAsk,SupportedFx=fx is not null});
            return new NativeObservedRolloverQuote(bid,fx);
        });
    decimal stress=book.GetProperty("Stress").GetDecimal();
    decimal? stressed=amount is decimal known?(known<0m?known*(1m+stress):known):null;
    decimal? adjustment=stressed-w.GetProperty("BookedSignedEur").GetDecimal();
    decimal? cash=book.GetProperty("OriginalCashEur").GetDecimal()+adjustment;
    results.Add(new {Id=book.GetProperty("Id").GetString(),Stress=stress,Window=w,
        NativeFinancingEur=stressed,FinancingAdjustmentEur=adjustment,FinanciallyReconciledTerminalCashEur=cash,
        FinanciallyReconciledClosedNetEur=cash-300m,Resolved=amount.HasValue,ChargeAudit=chargeAudit,
        OriginalCashEur=book.GetProperty("OriginalCashEur").GetDecimal(),
        OriginalKnownNetSubtotalEur=book.GetProperty("KnownOtherNetEur").GetDecimal(),
        OriginalSampledDrawdown=book.GetProperty("OriginalSampledDrawdown").GetDecimal(),
        OriginalUnknownEquityClocks=book.GetProperty("OriginalUnknownEquityClocks").GetInt32()});
}
File.WriteAllText(args[1],JsonSerializer.Serialize(new {Study=marketTime?"PAV1_MARKET_TIME_FROZEN_BOOK_SETTLEMENT_1":"PAV1_CLOSED_FUNDING_RECOVERY_1",
    ConditionalClosingRateScenario=marketTime,ClosingRateWitnesses=marketTime?closing:null,
    OriginalRun=input.GetProperty("OriginalRun").GetInt64(),OriginalArtifact=input.GetProperty("OriginalArtifact").GetInt64(),
    OriginalArchiveSha256=input.GetProperty("OriginalArchiveSha256").GetString(),
    NativeInputSha256=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant(),
    OriginalContractObservedAtUtcMs=actual.ObservedAtUtcMs,ScenarioContractObservedAtUtcMs=contract.ObservedAtUtcMs,
    Results=results,OriginalResultModified=false,OriginalDecisionsReplayed=false,OriginalUnknownEquityRestored=false,
    Basis=marketTime?"AUTHENTIC_OFFICIAL_PREFIX_VERIFIED_CLOSED_SESSION_OPEN_AGE_AND_ORIGINAL_CONDITIONAL_TARIFF_NOT_CERTIFIED_BROKER_SETTLEMENT":"AUTHENTIC_OFFICIAL_PREFIX_WITH_UNCHANGED_NATIVE_FX_AGE_AND_ORIGINAL_CONDITIONAL_TARIFF",
    EconomicPromotionCertified=false,IndependentConfirmationCertified=false,Orders=0,CloudActivated=false})+"\n");
