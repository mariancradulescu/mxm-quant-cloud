using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    // Financial settlement only: two missing official marks shared by the
    // frozen PAV1 original and the 36 unresolved new paired research books.
    // No Advance, no old policy replay, no reconstructed equity history.
    public static int RunAaplFrozenFunding(string sourcePath,string protectionDirectory,
        string reportPath,string newReportsDirectory,string witnessPath,string outputPath)
    {
        const string sourceSha="ff5b79b00f9a42778671c0cba849c689ba52f8ccbd1a6f0e8a84a26c87ab5eaf";
        const string reportSha="134fd898b9cd3d8948049927ddd039adeb12cccba04007ba3bf06eeae7e217b0";
        string[] pairedHashes={"2f1c3f8579d0d3ef003055b9004fd0c92b1e7234d39a72ed43559cf06168b6b1",
            "7fe81aef054833885527f9bd18bb0508a26bb179e8764f8a0a8c1f3cb206a525",
            "3429228c02736918daef2bc42ecf0854abcbef38f67ac7df7909f2722380aa53"};
        long[] charges={1793656800000L,1794434400000L};
        byte[] sb=File.ReadAllBytes(sourcePath),rb=File.ReadAllBytes(reportPath);
        if(File.Exists(outputPath)||GeneralSha(sb)!=sourceSha||GeneralSha(rb)!=reportSha)
            throw new InvalidDataException("AAPL_FROZEN_SOURCE_IDENTITY");
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=new EerProtectionTape(protectionDirectory)};
        var terms=input.Markets.Single(x=>x.Market.Name=="AAPL.US").Market.DatedDevelopment!;
        if(terms.Contract.Symbol!="AAPL.US"||terms.Contract.QuoteAsset!="USD"||
            !terms.Contract.OriginalBrokerAuthenticated)
            throw new InvalidDataException("AAPL_FROZEN_CONTRACT");
        using var witness=JsonDocument.Parse(File.ReadAllBytes(witnessPath));
        var rows=witness.RootElement.EnumerateArray().ToArray();
        if(rows.Length!=2||!rows.Select(x=>x.GetProperty("Target").GetProperty("At").GetInt64()).Order().SequenceEqual(charges))
            throw new InvalidDataException("AAPL_FROZEN_WITNESS_COUNT");
        var prefixes=new Dictionary<long,NativeHistoricalFundingPrefix?>();
        foreach(var w in rows)
        {
            var target=w.GetProperty("Target");long at=target.GetProperty("At").GetInt64();
            if(target.GetProperty("Symbol").GetString()!="AAPL.US"||target.GetProperty("Side").GetString()!="BID")
                throw new InvalidDataException("AAPL_FROZEN_WITNESS_SCOPE");
            var node=w.GetProperty("Witness");
            prefixes.Add(at,node.GetProperty("Status").GetString()=="AUTHENTIC_LATEST_PREFIX"
                ?node.Deserialize<NativeHistoricalFundingPrefix>(Json):null);
        }
        var retained=charges.ToDictionary(at=>at,at=>source.Charge("AAPL.US","USD",at));
        if(retained.Values.Any(q=>q.Bid is not null||q.QuoteToEur is null))
            throw new InvalidDataException("AAPL_ORIGINAL_QUOTE_PARITY");
        var output=new List<object>();int reconciled=0,paired=0;
        void Settle(JsonElement book,decimal stress,string study)
        {
            var result=book.GetProperty("Result");var details=book.GetProperty("Details");
            var window=details.GetProperty("OutstandingFunding").EnumerateArray().Single();
            string position=window.GetProperty("PositionId").GetString()!;
            var episodes=details.GetProperty("Episodes").EnumerateArray().ToArray();
            var episode=episodes.Single(x=>x.GetProperty("PositionId").GetString()==position);
            long from=window.GetProperty("FromExclusive").GetInt64(),through=window.GetProperty("ClosedAt").GetInt64();
            int side=window.GetProperty("Side").GetInt32();decimal units=window.GetProperty("Units").GetDecimal();
            long opened=episode.GetProperty("OpenAt").GetInt64();
            if(window.GetProperty("Symbol").GetString()!="AAPL.US"||episode.GetProperty("Symbol").GetString()!="AAPL.US"||
                opened>from||through!=episode.GetProperty("CloseAt").GetInt64()||units<=0m||
                units>episode.GetProperty("Units").GetDecimal()||side!=episode.GetProperty("Side").GetInt32()||
                result.GetProperty("OpenPositions").GetInt32()!=0||result.GetProperty("PendingIntents").GetInt32()!=0||
                result.GetProperty("UnknownFundingWindows").GetInt32()!=1||episode.GetProperty("NetEur").ValueKind!=JsonValueKind.Null||
                episodes.Count(x=>x.GetProperty("NetEur").ValueKind==JsonValueKind.Null)!=1||
                window.GetProperty("BookedSignedEur").GetDecimal()!=0m)
                throw new InvalidDataException("AAPL_FROZEN_POSITION_BINDING");
            var originalCharge=window.GetProperty("ChargeEvidence").EnumerateArray().Single();
            long charge=originalCharge.GetProperty("At").GetInt64();
            if(!prefixes.ContainsKey(charge)||originalCharge.GetProperty("HasRolloverBid").GetBoolean()||
                !originalCharge.GetProperty("HasRolloverConversion").GetBoolean()||
                NativeBrokerContractCosts.NextScheduledSwapCharge(terms.Contract,opened)!=charge)
                throw new InvalidDataException("AAPL_FROZEN_MISSING_FIELD_OR_PRIOR_CHARGE");
            // Three books had partial closes before this first charge; the
            // remaining window volume (not initial episode volume) is charged.
            decimal? bid=prefixes[charge]?.PriceAtCharge(charge,345600000L);
            decimal? funding=null;
            if(bid is decimal price)
            {
                funding=Financing(terms,from,through,side,units,at=>
                    at==charge?new NativeObservedRolloverQuote(price,retained[charge].QuoteToEur):
                        throw new InvalidDataException("AAPL_UNREGISTERED_CHARGE"));
                if(funding<0m)funding*=1m+stress;
            }
            decimal? episodeNet=null,terminalNet=null,terminalCash=null;
            if(funding is decimal settled)
            {
                episodeNet=episode.GetProperty("GrossEur").GetDecimal()-
                    episode.GetProperty("ExplicitExecutionCostsEur").GetDecimal()+settled;
                terminalNet=episodes.Where(x=>x.GetProperty("PositionId").GetString()!=position)
                    .Sum(x=>x.GetProperty("NetEur").GetDecimal())+episodeNet;
                terminalCash=result.GetProperty("CashEur").GetDecimal()+settled;
                if(Math.Abs(terminalCash.Value-300m-terminalNet.Value)>.000000000000001m)
                    throw new InvalidDataException("AAPL_FROZEN_CASH_RECONCILIATION");
                reconciled++;
            }
            output.Add(new {Study=study,Id=book.GetProperty("Id").GetString(),Stress=stress,PositionId=position,
                ChargeAt=charge,FromExclusive=from,ClosedAt=through,Side=side,Units=units,
                PartialCloseBeforeCharge=opened<from,OriginalFxReused=true,
                NewPriceObservedAt=prefixes[charge]?.At,NewRolloverBid=bid,FinancingSignedEur=funding,
                EpisodeClosedNetEur=episodeNet,FrozenClosedNetEur=terminalNet,FrozenTerminalCashEur=terminalCash,
                Status=funding.HasValue?"CONDITIONALLY_RECONCILED":"UNRESOLVED_NO_INVENTED_FUNDING"});
        }
        using(var report=JsonDocument.Parse(rb))
        {
            var scenario=report.RootElement.GetProperty("Results").EnumerateArray()
                .Single(x=>x.GetProperty("Stress").GetDecimal()==0m);
            var book=scenario.GetProperty("CommonBooks").EnumerateArray().Single(x=>x.GetProperty("Id").GetString()=="MT25_H1_24");
            if(book.GetProperty("Details").GetProperty("OutstandingFunding").EnumerateArray().Single()
                .GetProperty("PositionId").GetString()!="UCP1/EUR_GENERAL_PROBE/AAPL.US/PAV1_LOCAL_TRANSITION/1793649915000")
                throw new InvalidDataException("AAPL_ORIGINAL_POSITION_ID");
            Settle(book,0m,"PAV1_MARKET_TIME_FX_1");
        }
        for(int i=0;i<3;i++)
        {
            byte[] bytes=File.ReadAllBytes(Path.Combine(newReportsDirectory,"S"+i+".json"));
            if(GeneralSha(bytes)!=pairedHashes[i])throw new InvalidDataException("AAPL_PAIRED_ORIGINAL_HASH");
            using var doc=JsonDocument.Parse(bytes);var root=doc.RootElement;
            decimal stress=root.GetProperty("Stress").GetDecimal();
            if(stress!=i*.5m||root.GetProperty("SourceSha256").GetString()!=sourceSha||
                root.GetProperty("Study").GetString()!="MONETARY_REDUCE_COMMON_BOOK_1")
                throw new InvalidDataException("AAPL_PAIRED_ORIGINAL_IDENTITY");
            var books=root.GetProperty("CommonBooks").EnumerateArray().Where(x=>
                x.GetProperty("Result").GetProperty("UnknownFundingWindows").GetInt32()>0).ToArray();
            if(books.Length!=12)throw new InvalidDataException("AAPL_PAIRED_BOOK_COUNT");
            foreach(var book in books){Settle(book,stress,"MONETARY_REDUCE_COMMON_BOOK_1");paired++;}
        }
        if(paired!=36||output.Count!=37)throw new InvalidDataException("AAPL_FROZEN_EXPECTED_SCOPE");
        File.WriteAllBytes(outputPath,JsonSerializer.SerializeToUtf8Bytes(new {
            Study="AAPL_FROZEN_FUNDING_RECOVERY_1",OriginalRun=45835675932L,OriginalArtifact=15126531887L,
            PairedRun=45861661121L,PairedArtifact=15138568335L,
            OriginalSourceSha256=sourceSha,OriginalEconomicJsonSha256=reportSha,PairedEconomicJsonSha256=pairedHashes,
            MissingOfficialMarks=2,FrozenBooks=37,ReconciledBooks=reconciled,Rows=output,
            Status=reconciled==37?"CONDITIONALLY_RECONCILED":"PARTIAL_OR_UNRESOLVED",
            Basis="AUTHENTIC_OFFICIAL_TICK_PREFIX_AND_ORIGINAL_ARCHIVED_CONDITIONAL_TARIFF_NOT_BROKER_SETTLEMENT",
            OriginalResultsModified=false,OriginalEquityHistoryRestored=false,EconomicPolicyReruns=0,
            EconomicPromotionCertified=false,IndependentConfirmationCertified=false,Orders=0,CloudActivated=false
        },Json));
        return 0;
    }
}
