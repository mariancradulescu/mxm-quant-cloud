using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    // Settlement of a frozen, previously completed conditional model book.
    // No engine Advance, new signal, policy replay, or broker execution.
    public static int RunAaplFrozenFunding(string sourcePath,string protectionDirectory,
        string reportPath,string witnessPath,string outputPath)
    {
        const string sourceSha="ff5b79b00f9a42778671c0cba849c689ba52f8ccbd1a6f0e8a84a26c87ab5eaf";
        const string reportSha="134fd898b9cd3d8948049927ddd039adeb12cccba04007ba3bf06eeae7e217b0";
        const string position="UCP1/EUR_GENERAL_PROBE/AAPL.US/PAV1_LOCAL_TRANSITION/1793649915000";
        const long charge=1793656800000L,from=1793649915539L,through=1793723419747L;
        byte[] sb=File.ReadAllBytes(sourcePath),rb=File.ReadAllBytes(reportPath);
        if(File.Exists(outputPath)||GeneralSha(sb)!=sourceSha||GeneralSha(rb)!=reportSha)
            throw new InvalidDataException("AAPL_FROZEN_SOURCE_IDENTITY");
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        using var report=JsonDocument.Parse(rb);
        var scenario=report.RootElement.GetProperty("Results").EnumerateArray()
            .Single(x=>x.GetProperty("Stress").GetDecimal()==0m);
        var book=scenario.GetProperty("CommonBooks").EnumerateArray()
            .Single(x=>x.GetProperty("Id").GetString()=="MT25_H1_24");
        var result=book.GetProperty("Result");
        var details=book.GetProperty("Details");
        var window=details.GetProperty("OutstandingFunding").EnumerateArray().Single();
        var episodes=details.GetProperty("Episodes").EnumerateArray().ToArray();
        var episode=episodes.Single(x=>x.GetProperty("PositionId").GetString()==position);
        if(window.GetProperty("PositionId").GetString()!=position||window.GetProperty("Symbol").GetString()!="AAPL.US"||
            window.GetProperty("FromExclusive").GetInt64()!=from||window.GetProperty("ClosedAt").GetInt64()!=through||
            window.GetProperty("Side").GetInt32()!=-1||window.GetProperty("Units").GetDecimal()!=.1m||
            result.GetProperty("OpenPositions").GetInt32()!=0||result.GetProperty("PendingIntents").GetInt32()!=0||
            result.GetProperty("UnknownFundingWindows").GetInt32()!=1||
            episode.GetProperty("NetEur").ValueKind!=JsonValueKind.Null||episodes.Length!=23)
            throw new InvalidDataException("AAPL_FROZEN_POSITION_BINDING");
        var originalCharge=window.GetProperty("ChargeEvidence").EnumerateArray().Single();
        if(originalCharge.GetProperty("At").GetInt64()!=charge||
            originalCharge.GetProperty("HasRolloverBid").GetBoolean()||
            !originalCharge.GetProperty("HasRolloverConversion").GetBoolean())
            throw new InvalidDataException("AAPL_FROZEN_MISSING_FIELD");
        using var witness=JsonDocument.Parse(File.ReadAllBytes(witnessPath));
        var w=witness.RootElement;
        if(w.GetProperty("Target").GetProperty("Symbol").GetString()!="AAPL.US"||
            w.GetProperty("Target").GetProperty("Side").GetString()!="BID"||
            w.GetProperty("Target").GetProperty("At").GetInt64()!=charge)
            throw new InvalidDataException("AAPL_FROZEN_WITNESS_SCOPE");
        var node=w.GetProperty("Witness");
        var prefix=node.GetProperty("Status").GetString()=="AUTHENTIC_LATEST_PREFIX"
            ?node.Deserialize<NativeHistoricalFundingPrefix>(Json):null;
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=new EerProtectionTape(protectionDirectory)};
        var terms=input.Markets.Single(x=>x.Market.Name=="AAPL.US").Market.DatedDevelopment!;
        if(terms.Contract.Symbol!="AAPL.US"||terms.Contract.QuoteAsset!="USD"||
            !terms.Contract.OriginalBrokerAuthenticated)
            throw new InvalidDataException("AAPL_FROZEN_CONTRACT");
        var retained=source.Charge("AAPL.US","USD",charge);
        if(retained.Bid is not null||retained.QuoteToEur is null)
            throw new InvalidDataException("AAPL_ORIGINAL_QUOTE_PARITY");
        decimal? bid=prefix?.PriceAtCharge(charge,345600000L);
        decimal? funding=null;
        if(bid is decimal price)
            funding=Financing(terms,from,through,-1,.1m,at=>
                at==charge?new NativeObservedRolloverQuote(price,retained.QuoteToEur):
                    throw new InvalidDataException("AAPL_UNREGISTERED_CHARGE"));
        decimal? episodeNet=null,terminalNet=null,terminalCash=null;
        if(funding is decimal settled)
        {
            episodeNet=episode.GetProperty("GrossEur").GetDecimal()-
                episode.GetProperty("ExplicitExecutionCostsEur").GetDecimal()+settled;
            terminalNet=episodes.Where(x=>x.GetProperty("PositionId").GetString()!=position)
                .Sum(x=>x.GetProperty("NetEur").GetDecimal())+episodeNet;
            terminalCash=result.GetProperty("CashEur").GetDecimal()+settled-window.GetProperty("BookedSignedEur").GetDecimal();
            if(Math.Abs(terminalCash.Value-300m-terminalNet.Value)>.000000000000001m)
                throw new InvalidDataException("AAPL_FROZEN_CASH_RECONCILIATION");
        }
        File.WriteAllBytes(outputPath,JsonSerializer.SerializeToUtf8Bytes(new {
            Study="AAPL_FROZEN_FUNDING_RECOVERY_1",OriginalRun=45835675932L,OriginalArtifact=15126531887L,
            OriginalSourceSha256=sourceSha,OriginalEconomicJsonSha256=reportSha,
            PositionId=position,ChargeAt=charge,OriginalFxReused=true,
            NewPriceObservedAt=prefix?.At,NewRolloverBid=bid,FinancingSignedEur=funding,
            EpisodeClosedNetEur=episodeNet,FrozenClosedNetEur=terminalNet,FrozenTerminalCashEur=terminalCash,
            Status=funding.HasValue?"CONDITIONALLY_RECONCILED":"UNRESOLVED_NO_INVENTED_FUNDING",
            Basis="AUTHENTIC_OFFICIAL_TICK_PREFIX_AND_ORIGINAL_ARCHIVED_CONDITIONAL_TARIFF_NOT_BROKER_SETTLEMENT",
            OriginalResultsModified=false,OriginalEquityHistoryRestored=false,EconomicPolicyReruns=0,
            EconomicPromotionCertified=false,IndependentConfirmationCertified=false,Orders=0,CloudActivated=false
        },Json));
        return 0;
    }
}
