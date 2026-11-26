using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    public static int RunGoogOpenFunding(string sourcePath,string tapePath,string reportPath,string witnessPath,string outputPath)
    {
        const string sourceHash="4336a525ad897bee1a280e2baff07dcd399606e25f9536d4a202bc2676d73b15";
        const string reportHash="e80d2364d7018a7a692bf75647a1793c94e9a79be0ca470b483362b7a7218ac7";
        const string position="UCP1/EUR_GENERAL_SELECT/GOOG.US-24/M5_REVERSE/1795561815000";
        const long charge=1795644000000L,from=1795561883665L,through=1795650915000L;
        byte[] sb=File.ReadAllBytes(sourcePath),rb=File.ReadAllBytes(reportPath);
        if(File.Exists(outputPath)||GeneralSha(sb)!=sourceHash||GeneralSha(rb)!=reportHash)
            throw new InvalidDataException("GOOG_FROZEN_SOURCE_BINDING");
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=new EerProtectionTape(tapePath)};
        var terms=input.Markets.Single(m=>m.Market.Name=="GOOG.US-24").Market.DatedDevelopment!;
        if(!terms.Contract.OriginalBrokerAuthenticated||terms.Contract.Symbol!="GOOG.US-24"||terms.Contract.QuoteAsset!="USD")
            throw new InvalidDataException("GOOG_FROZEN_CONTRACT");
        using var doc=JsonDocument.Parse(rb);
        if(doc.RootElement.GetProperty("Study").GetString()!="MONETARY_CAUSAL_MANAGEMENT_1"||
            doc.RootElement.GetProperty("Stress").GetDecimal()!=0m)
            throw new InvalidDataException("GOOG_FROZEN_STUDY");
        using var wd=JsonDocument.Parse(File.ReadAllBytes(witnessPath));
        var w=wd.RootElement;var target=w.GetProperty("Target");
        if(target.GetProperty("Symbol").GetString()!="GOOG.US-24"||target.GetProperty("Side").GetString()!="BID"||
            target.GetProperty("At").GetInt64()!=charge)throw new InvalidDataException("GOOG_WITNESS_SCOPE");
        var node=w.GetProperty("Witness");
        var prefix=node.GetProperty("Status").GetString()=="AUTHENTIC_LATEST_PREFIX"
            ?node.Deserialize<NativeHistoricalFundingPrefix>(Json):null;
        var retained=source.Charge("GOOG.US-24","USD",charge);
        if(retained.Bid is not null||retained.QuoteToEur is null)
            throw new InvalidDataException("GOOG_ORIGINAL_QUOTE_PARITY");
        decimal? bid=prefix?.PriceAtCharge(charge,345600000L),funding=null;
        if(bid is decimal price)
            funding=Financing(terms,from,through,-1,.2m,at=>at==charge
                ?new NativeObservedRolloverQuote(price,retained.QuoteToEur):throw new InvalidDataException("GOOG_OTHER_CHARGE"));
        var rows=new List<object>();
        foreach(var b in doc.RootElement.GetProperty("CommonBooks").EnumerateArray()
            .Where(x=>x.GetProperty("Result").GetProperty("OpenPositions").GetInt32()>0))
        {
            var result=b.GetProperty("Result");
            var window=b.GetProperty("Details").GetProperty("OutstandingFunding").EnumerateArray().Single();
            if(result.GetProperty("OpenPositions").GetInt32()!=1||result.GetProperty("PendingIntents").GetInt32()!=0||
                result.GetProperty("UnknownFundingWindows").GetInt32()!=1||
                window.GetProperty("PositionId").GetString()!=position||window.GetProperty("Symbol").GetString()!="GOOG.US-24"||
                window.GetProperty("Side").GetInt32()!=-1||window.GetProperty("Units").GetDecimal()!=.2m||
                window.GetProperty("FromExclusive").GetInt64()!=from||window.GetProperty("Through").GetInt64()!=through||
                window.GetProperty("ClosedAt").ValueKind!=JsonValueKind.Null)
                throw new InvalidDataException("GOOG_WINDOW_BINDING");
            var clock=window.GetProperty("ChargeEvidence").EnumerateArray().Single();
            if(clock.GetProperty("At").GetInt64()!=charge||clock.GetProperty("HasRolloverBid").GetBoolean()||
                !clock.GetProperty("HasRolloverConversion").GetBoolean())
                throw new InvalidDataException("GOOG_MISSING_FIELD");
            decimal booked=window.GetProperty("BookedSignedEur").GetDecimal();
            rows.Add(new {Id=b.GetProperty("Id").GetString(),PositionId=position,FundingSignedEur=funding,
                AdditionalFundingSignedEur=funding-booked,OriginalCashEur=result.GetProperty("CashEur").GetDecimal(),
                ConditionalCorrectedCashEur=result.GetProperty("CashEur").GetDecimal()+funding-booked,
                OriginalClosedNetEur=result.GetProperty("ClosedNetEur").GetDecimal(),
                OriginalUnknownEquityClocks=result.GetProperty("UnknownEquityClocks").GetInt32(),
                TerminalEquityEur=(decimal?)null,PositionStillOpen=true});
        }
        if(rows.Count!=3)throw new InvalidDataException("GOOG_FROZEN_BOOK_COUNT");
        File.WriteAllBytes(outputPath,JsonSerializer.SerializeToUtf8Bytes(new {
            Study="GOOG_OPEN_FUNDING_RECOVERY_1",OriginalRun=45874059214L,OriginalArtifact=15143664128L,
            OriginalSourceSha256=sourceHash,OriginalReportSha256=reportHash,ChargeAt=charge,
            OriginalFxReused=true,RecoveredAt=prefix?.At,RecoveredBid=bid,FundingSignedEur=funding,
            ReconciledWindows=funding.HasValue?3:0,Rows=rows,
            Status=funding.HasValue?"CONDITIONALLY_RECONCILED_OPEN_FUNDING":"UNRESOLVED",
            TerminalLiquidationEquityCertified=false,OriginalEquityHistoryRestored=false,
            OriginalResultsModified=false,EconomicPolicyReruns=0,Orders=0,CloudActivated=false
        },Json));
        return 0;
    }
}
