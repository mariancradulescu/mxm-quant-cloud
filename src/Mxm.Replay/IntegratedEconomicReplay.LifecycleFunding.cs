using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    public static int RunLifecycleFunding(string sourcePath,string tapePath,string reports,string witnessPath,string outputPath)
    {
        const string sourceHash="4336a525ad897bee1a280e2baff07dcd399606e25f9536d4a202bc2676d73b15";
        string[] hashes={"5e4ee19273798422843ca6409f81f07e14282079da2d1f92755513979fc1eee2",
            "5aed09659aa820a5f2c62eebc7ed670807cff5f86221eef9579eb43221bcf64b",
            "ad0e4f93c1e2673296afdbbf88e36602a13bb158bae04a0f877e58f3b12fa8d9"};
        byte[] sb=File.ReadAllBytes(sourcePath);
        if(File.Exists(outputPath)||GeneralSha(sb)!=sourceHash)throw new InvalidDataException("LIFECYCLE_FUNDING_SOURCE");
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        var tape=new EerProtectionTape(tapePath);
        var original=new EerEvidence(input){MarketTimeFx=true,ValuationTape=tape};
        using var wd=JsonDocument.Parse(File.ReadAllBytes(witnessPath));
        var targets=new HashSet<(string Symbol,string Side,long At)>{
            ("GOOG.US-24","BID",1795644000000L),("AAPL.US","BID",1793743200000L),
            ("EURUSD","BID",1794088800000L),("EURUSD","ASK",1794088800000L),
            ("EURUSD","BID",1794175200000L),("EURUSD","ASK",1794175200000L)};
        var seen=new HashSet<(string Symbol,string Side,long At)>();
        var overlays=new Dictionary<(string Symbol,long At),DatedRolloverQuote>();
        foreach(var w in wd.RootElement.EnumerateArray())
        {
            var t=w.GetProperty("Target");var k=(Symbol:t.GetProperty("Symbol").GetString()!,
                Side:t.GetProperty("Side").GetString()!,At:t.GetProperty("At").GetInt64());
            if(!targets.Contains(k)||!seen.Add(k))throw new InvalidDataException("LIFECYCLE_FUNDING_TARGET");
            var node=w.GetProperty("Witness");
            if(node.GetProperty("Status").GetString()!="AUTHENTIC_LATEST_PREFIX")continue;
            var prefix=node.Deserialize<NativeHistoricalFundingPrefix>(Json)!;
            if(prefix.PriceAtCharge(k.At,345600000L) is not decimal price)
                throw new InvalidDataException("LIFECYCLE_FUNDING_PREFIX");
            var key=(k.Symbol,k.At);
            var q=overlays.GetValueOrDefault(key)??original.FundingAt(k.Symbol,k.At)??new DatedRolloverQuote(k.At,false,null,null,null,null);
            bool ask=k.Side=="ASK";
            var prior=q.FundingPrice(ask,7200000L,345600000L);
            // Preserve already valid individual sides; disagreement is not silently overwritten.
            if(prior.HasValue)
            {
                if(prior.Value!=price)throw new InvalidDataException("LIFECYCLE_FUNDING_CONFLICT");
                continue;
            }
            if((ask?q.LatestAskPrefix:q.LatestBidPrefix) is not null)
                throw new InvalidDataException("LIFECYCLE_FUNDING_EXISTING_PREFIX");
            overlays[key]=ask?q with {LatestAskPrefix=prefix}:q with {LatestBidPrefix=prefix};
        }
        if(!seen.SetEquals(targets))throw new InvalidDataException("LIFECYCLE_FUNDING_SCOPE");
        var child=input with {Tapes=input.Tapes.Select(t=>
        {
            var f=t.FundingQuotes.ToDictionary(q=>q.At);
            foreach(var q in overlays.Where(x=>x.Key.Symbol==t.Name))f[q.Key.At]=q.Value;
            return t with {FundingQuotes=f.Values.OrderBy(q=>q.At).ToArray()};
        }).ToArray()};
        var recovered=new EerEvidence(child){MarketTimeFx=true,ValuationTape=tape};
        var rows=new List<object>();int settled=0,open=0;
        for(int i=0;i<3;i++)
        {
            byte[] rb=File.ReadAllBytes(Path.Combine(reports,"S"+i+".json"));
            if(GeneralSha(rb)!=hashes[i])throw new InvalidDataException("LIFECYCLE_FROZEN_REPORT");
            using var doc=JsonDocument.Parse(rb);var root=doc.RootElement;
            decimal stress=root.GetProperty("Stress").GetDecimal();
            if(stress!=i*.5m||root.GetProperty("Study").GetString()!="MONETARY_LIFECYCLE_ESTIMATION_1"||
                root.GetProperty("SourceSha256").GetString()!=sourceHash)throw new InvalidDataException("LIFECYCLE_FROZEN_IDENTITY");
            foreach(var b in root.GetProperty("CommonBooks").EnumerateArray())
            {
                var result=b.GetProperty("Result");var details=b.GetProperty("Details");
                var windows=details.GetProperty("OutstandingFunding").EnumerateArray().ToArray();
                if(windows.Length==0)continue;
                if(windows.Length!=1||result.GetProperty("UnknownFundingWindows").GetInt32()!=1)
                    throw new InvalidDataException("LIFECYCLE_WINDOW_COUNT");
                var w=windows[0];string symbol=w.GetProperty("Symbol").GetString()!;
                string position=w.GetProperty("PositionId").GetString()!;
                long from=w.GetProperty("FromExclusive").GetInt64(),through=w.GetProperty("Through").GetInt64();
                int side=w.GetProperty("Side").GetInt32();decimal units=w.GetProperty("Units").GetDecimal();
                bool stillOpen=w.GetProperty("ClosedAt").ValueKind==JsonValueKind.Null;
                var terms=input.Markets.Single(m=>m.Market.Name==symbol).Market.DatedDevelopment!;
                if(!terms.Contract.OriginalBrokerAuthenticated||terms.Contract.QuoteAsset!="USD"||
                    w.GetProperty("QuoteAsset").GetString()!="USD"||units<=0m)throw new InvalidDataException("LIFECYCLE_CONTRACT");
                if(symbol=="GOOG.US-24"&&(!stillOpen||position!="UCP1/EUR_GENERAL_SELECT/GOOG.US-24/M5_REVERSE/1795561815000"||
                    units!=.2m||side!=-1||from!=1795561883665L||through!=1795650915000L))
                    throw new InvalidDataException("LIFECYCLE_GOOG_IDENTITY");
                if(symbol is not ("GOOG.US-24" or "AAPL.US" or "ETHUSD"))throw new InvalidDataException("LIFECYCLE_UNREGISTERED_SYMBOL");
                var charges=w.GetProperty("ChargeEvidence").EnumerateArray().ToDictionary(x=>x.GetProperty("At").GetInt64());
                foreach(var c in charges)
                {
                    var q=original.Charge(symbol,"USD",c.Key);
                    if(q.Bid.HasValue!=c.Value.GetProperty("HasRolloverBid").GetBoolean()||
                        (q.QuoteToEur is not null)!=c.Value.GetProperty("HasRolloverConversion").GetBoolean())
                        throw new InvalidDataException("LIFECYCLE_ORIGINAL_EVIDENCE_PARITY");
                }
                decimal? funding=Financing(terms,from,through,side,units,at=>charges.ContainsKey(at)
                    ?recovered.Charge(symbol,"USD",at):throw new InvalidDataException("LIFECYCLE_UNREGISTERED_CHARGE"));
                if(funding<0m)funding*=1m+stress;
                decimal booked=w.GetProperty("BookedSignedEur").GetDecimal();
                decimal? delta=funding-booked,net=null,episodeNet=null;
                if(stillOpen){open++;if(result.GetProperty("OpenPositions").GetInt32()!=1)throw new InvalidDataException("LIFECYCLE_OPEN_PARITY");}
                else
                {
                    var episodes=details.GetProperty("Episodes").EnumerateArray().ToArray();
                    var e=episodes.Single(x=>x.GetProperty("PositionId").GetString()==position);
                    if(result.GetProperty("OpenPositions").GetInt32()!=0||result.GetProperty("PendingIntents").GetInt32()!=0||
                        w.GetProperty("ClosedAt").GetInt64()!=through||e.GetProperty("CloseAt").GetInt64()!=through||
                        e.GetProperty("OpenAt").GetInt64()!=from||e.GetProperty("Units").GetDecimal()!=units||
                        e.GetProperty("Side").GetInt32()!=side||e.GetProperty("Symbol").GetString()!=symbol||
                        e.GetProperty("NetEur").ValueKind!=JsonValueKind.Null||booked!=0m||
                        episodes.Count(x=>x.GetProperty("NetEur").ValueKind==JsonValueKind.Null)!=1)
                        throw new InvalidDataException("LIFECYCLE_CLOSED_EPISODE");
                    if(funding.HasValue)
                    {
                        episodeNet=e.GetProperty("GrossEur").GetDecimal()-e.GetProperty("ExplicitExecutionCostsEur").GetDecimal()+funding;
                        net=episodes.Where(x=>x.GetProperty("PositionId").GetString()!=position).Sum(x=>x.GetProperty("NetEur").GetDecimal())+episodeNet;
                        if(Math.Abs(result.GetProperty("CashEur").GetDecimal()+delta!.Value-300m-net!.Value)>.000000000000001m)
                            throw new InvalidDataException("LIFECYCLE_CASH_PARITY");
                    }
                }
                if(funding.HasValue)settled++;
                rows.Add(new {Id=b.GetProperty("Id").GetString(),Stress=stress,Symbol=symbol,PositionId=position,
                    FundingSignedEur=funding,AdditionalFundingSignedEur=delta,EpisodeNetEur=episodeNet,
                    ConditionalClosedNetEur=net,ConditionalCashEur=result.GetProperty("CashEur").GetDecimal()+delta,
                    PositionStillOpen=stillOpen,TerminalEquityCertified=false,OriginalEquityHistoryRestored=false,
                    Status=funding.HasValue?"CONDITIONALLY_RECONCILED":"UNRESOLVED"});
            }
        }
        if(rows.Count!=7||open!=2)throw new InvalidDataException("LIFECYCLE_EXPECTED_FROZEN_SCOPE");
        File.WriteAllBytes(outputPath,JsonSerializer.SerializeToUtf8Bytes(new {Study="LIFECYCLE_FUNDING_RECOVERY_1",
            OriginalRun=45885931266L,OriginalArtifact=15149404567L,OriginalSourceSha256=sourceHash,
            FrozenWindows=rows.Count,ReconciledWindows=settled,Rows=rows,OriginalResultsModified=false,
            HistoricalEquityCertified=false,Orders=0,CloudActivated=false,EconomicPolicyReruns=0},Json));
        return 0;
    }
}
