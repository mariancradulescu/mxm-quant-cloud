using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

if(args.Length!=2||File.Exists(args[1]))throw new ArgumentException("FUNDING_SETTLEMENT_PATHS");
using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));var input=doc.RootElement;
var options=new JsonSerializerOptions {NumberHandling=JsonNumberHandling.AllowReadingFromString};
var c=input.GetProperty("Contract").Deserialize<NativeObservedContractTerms>(options)!;
var w=input.GetProperty("Window");var episode=input.GetProperty("Episode");
long from=w.GetProperty("FromExclusive").GetInt64(),through=w.GetProperty("ClosedAt").GetInt64();
int side=w.GetProperty("Side").GetInt32();decimal units=w.GetProperty("Units").GetDecimal();
if(input.GetProperty("EconomicPolicyReruns").GetInt32()!=0||c.Symbol!="AAPL.US"||c.QuoteAsset!="USD"||
    w.GetProperty("PositionId").GetString()!=episode.GetProperty("PositionId").GetString()||
    from!=episode.GetProperty("OpenAt").GetInt64()||through!=episode.GetProperty("CloseAt").GetInt64()||
    episode.GetProperty("NetEur").ValueKind!=JsonValueKind.Null)throw new InvalidDataException("FUNDING_SETTLEMENT_BINDING");
var charges=input.GetProperty("Charges").EnumerateArray().ToDictionary(x=>x.GetProperty("At").GetInt64());
decimal Price(JsonElement witness,long charge,bool fx=false)
{
    var prefix=witness.Deserialize<NativeHistoricalFundingPrefix>(options);
    return prefix?.PriceAtCharge(charge,fx?7_200_000L:345_600_000L)
        ??throw new InvalidDataException("FUNDING_SETTLEMENT_LATEST_WITNESS");
}
var used=new List<object>();
var a=input.GetProperty("Account");
decimal? amount=NativeBrokerContractCosts.ObservedDailySwapEur(c,from,through,side,units,
    a.GetProperty("accountSwapFree").GetBoolean(),a.GetProperty("accountType").GetInt32(),
    a.GetProperty("moneyDigits").GetInt32(),input.GetProperty("PriceDigits").GetInt32(),at=>
    {
        if(!charges.TryGetValue(at,out var row))throw new InvalidDataException("FUNDING_SETTLEMENT_CHARGE_NOT_COLLECTED");
        decimal bid=Price(row.GetProperty("Bid"),at),fxBid=Price(row.GetProperty("FxBid"),at,true),
            fxAsk=Price(row.GetProperty("FxAsk"),at,true);
        if(fxAsk<fxBid)throw new InvalidDataException("FUNDING_SETTLEMENT_FX_CROSSED");
        used.Add(new {At=at,Bid=bid,BidAt=row.GetProperty("Bid").GetProperty("At").GetInt64(),
            CreditToEur=1m/fxAsk,DebitToEur=1m/fxBid});
        return new NativeObservedRolloverQuote(bid,new NativeOriginalFxRate(1m/fxAsk,1m/fxBid,new[]{"EURUSD"}));
    });
if(amount is not decimal funding)throw new InvalidDataException("FUNDING_SETTLEMENT_UNKNOWN_NOT_ZERO");
decimal closed=episode.GetProperty("GrossEur").GetDecimal()-episode.GetProperty("ExplicitExecutionCostsEur").GetDecimal()+funding;
decimal net=input.GetProperty("KnownOtherNetEur").GetDecimal()+closed;
decimal cash=input.GetProperty("OriginalCashEur").GetDecimal()+funding-w.GetProperty("BookedSignedEur").GetDecimal();
if(Math.Abs(cash-300m-net)>.000000000000001m)throw new InvalidDataException("FUNDING_SETTLEMENT_CASH_RECONCILIATION");
File.WriteAllText(args[1],JsonSerializer.Serialize(new {
    Study=input.GetProperty("Study").GetString(),OriginalRun=input.GetProperty("OriginalRun").GetInt64(),
    RegistrySha256=input.GetProperty("RegistrySha256").GetString(),
    NativeInputSha256=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant(),
    OriginalArchiveSha256=input.GetProperty("OriginalArchiveSha256").GetString(),
    OriginalProtocolSha256=input.GetProperty("OriginalProtocolSha256").GetString(),
    OriginalSourceSha256=input.GetProperty("OriginalSourceSha256").GetString(),
    PositionId=w.GetProperty("PositionId").GetString(),FinancingSignedEur=funding,EpisodeClosedNetEur=closed,
    FinanciallyReconciledFrozenClosedNetEur=net,FinanciallyReconciledTerminalCashEur=cash,
    QuoteBasis=used,OriginalResultModified=false,OriginalDecisionsReplayed=false,OriginalUnknownEquityRestored=false,
    Basis="AUTHENTIC_LATEST_OFFICIAL_TICK_PREFIX_AND_ARCHIVED_CONDITIONAL_TARIFF_NOT_BROKER_SETTLEMENT",
    EconomicPromotionCertified=false,IndependentConfirmationCertified=false,Orders=0,CloudActivated=false})+"\n");
