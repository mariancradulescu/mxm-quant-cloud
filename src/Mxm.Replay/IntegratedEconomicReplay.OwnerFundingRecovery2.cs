using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    // Frozen report reconciliation only: never advance a policy or alter its history.
    public static int RunOwnerFundingRecovery2(string sourcePath,string tapePath,string reports,string witnessPath,string outputPath)
    {
        if(File.Exists(outputPath))throw new InvalidDataException("RECOVERY2_OUTPUT_EXISTS");
        byte[] sb=File.ReadAllBytes(sourcePath);
        string hash=GeneralSha(sb);
        using var summary=JsonDocument.Parse(File.ReadAllBytes(Path.Combine(reports,"summary.json")));
        var sr=summary.RootElement;
        if(sr.GetProperty("SourceSha256").GetString()!=hash||sr.GetProperty("Orders").GetInt32()!=0||
            sr.GetProperty("CloudActivated").GetBoolean())throw new InvalidDataException("RECOVERY2_SOURCE_BINDING");
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        var tape=new EerProtectionTape(tapePath);
        var original=new EerEvidence(input){MarketTimeFx=true,ValuationTape=tape};
        var required=new HashSet<(string Symbol,long At,string Side)>();
        var overlays=new Dictionary<(string Symbol,long At),DatedRolloverQuote>();
        var witnessSeen=new HashSet<(string Symbol,long At,string Side)>();
        bool planning=witnessPath=="-";
        if(!planning)
        {
            using var wd=JsonDocument.Parse(File.ReadAllBytes(witnessPath));
            foreach(var w in wd.RootElement.EnumerateArray())
            {
                var t=w.GetProperty("Target");var k=(Symbol:t.GetProperty("Symbol").GetString()!,
                    At:t.GetProperty("At").GetInt64(),Side:t.GetProperty("Side").GetString()!);
                if(!witnessSeen.Add(k)||k.Side is not ("BID" or "ASK"))throw new InvalidDataException("RECOVERY2_WITNESS_SCOPE");
                if(!input.Tapes.Any(x=>x.Name==k.Symbol))continue;
                var node=w.GetProperty("Witness");
                if(node.GetProperty("Status").GetString()!="AUTHENTIC_LATEST_PREFIX")continue;
                var prefix=node.Deserialize<NativeHistoricalFundingPrefix>(Json)!;
                if(prefix.PriceAtCharge(k.At,345600000L) is not decimal price)
                    throw new InvalidDataException("RECOVERY2_PREFIX");
                var key=(k.Symbol,k.At);
                var q=overlays.GetValueOrDefault(key)??original.FundingAt(k.Symbol,k.At)??new DatedRolloverQuote(k.At,false,null,null,null,null);
                bool ask=k.Side=="ASK";
                var prior=q.FundingPrice(ask,7200000L,345600000L);
                if(prior.HasValue)
                {
                    // Existing valid marks cannot be silently replaced.
                    if(prior.Value!=price)continue;
                    continue;
                }
                if((ask?q.LatestAskPrefix:q.LatestBidPrefix) is not null)continue;
                overlays[key]=ask?q with {LatestAskPrefix=prefix}:q with {LatestBidPrefix=prefix};
            }
        }
        var child=input with {Tapes=input.Tapes.Select(t=>
        {
            var f=t.FundingQuotes.ToDictionary(q=>q.At);
            foreach(var q in overlays.Where(x=>x.Key.Symbol==t.Name))f[q.Key.At]=q.Value;
            return t with {FundingQuotes=f.Values.OrderBy(q=>q.At).ToArray()};
        }).ToArray()};
        var recovered=new EerEvidence(child){MarketTimeFx=true,ValuationTape=tape};
        using var registration=JsonDocument.Parse(File.ReadAllBytes(Path.Combine(reports,"registered-plan.json")));
        var profiles=registration.RootElement.GetProperty("Variants").EnumerateArray().ToDictionary(
            x=>x.GetProperty("Id").GetString()!,x=>x.GetProperty("Profile"));
        var books=new List<object>();var windows=new List<object>();int excluded=0,settled=0,originalWindows=0;
        for(int i=0;i<3;i++)
        {
            using var doc=JsonDocument.Parse(File.ReadAllBytes(Path.Combine(reports,"S"+i+".json")));
            var root=doc.RootElement;decimal stress=root.GetProperty("Stress").GetDecimal();
            if(stress!=i*.5m||root.GetProperty("SourceSha256").GetString()!=hash||
                root.GetProperty("ProtocolSha256").GetString()!=sr.GetProperty("ProtocolSha256").GetString())
                throw new InvalidDataException("RECOVERY2_REPORT_BINDING");
            foreach(var b in root.GetProperty("CommonBooks").EnumerateArray())
            {
                string id=b.GetProperty("Id").GetString()!;
                var result=b.GetProperty("Result");var details=b.GetProperty("Details");
                var outstanding=details.GetProperty("OutstandingFunding").EnumerateArray().ToArray();
                if(outstanding.Length!=result.GetProperty("UnknownFundingWindows").GetInt32())
                    throw new InvalidDataException("RECOVERY2_WINDOW_PARITY");
                if(outstanding.Length==0)continue;
                bool useClosed=profiles.TryGetValue(id,out var profile)&&profile.TryGetProperty("ModelFundingAtPriorClosedSessionQuote",out var flag)&&flag.ValueKind==JsonValueKind.True;
                decimal? sum=0m;
                foreach(var w in outstanding)
                {
                    originalWindows++;
                    string symbol=w.GetProperty("Symbol").GetString()!,position=w.GetProperty("PositionId").GetString()!;
                    long from=w.GetProperty("FromExclusive").GetInt64(),through=w.GetProperty("Through").GetInt64();
                    int side=w.GetProperty("Side").GetInt32();decimal units=w.GetProperty("Units").GetDecimal();
                    var terms=input.Markets.Single(x=>x.Market.Name==symbol).Market.DatedDevelopment!;
                    var c=terms.Contract;
                    if(!c.OriginalBrokerAuthenticated||c.QuoteAsset!=w.GetProperty("QuoteAsset").GetString())
                        throw new InvalidDataException("RECOVERY2_CONTRACT_IDENTITY");
                    var diagnostic=w.GetProperty("ChargeEvidence").EnumerateArray().ToDictionary(x=>x.GetProperty("At").GetInt64());
                    var eligible=NativeBrokerContractCosts.ObservedDailySwapChargeClocks(c,from,through,side,units,terms.AccountSwapFree);
                    var prior=useClosed?new Dictionary<(string Symbol,long ChargeAt),long>():null;
                    foreach(var (at,e) in diagnostic)
                    {
                        var q=original.Charge(symbol,c.QuoteAsset,at);
                        if(q.Bid.HasValue!=e.GetProperty("HasRolloverBid").GetBoolean()||
                            (q.QuoteToEur is not null)!=e.GetProperty("HasRolloverConversion").GetBoolean())
                            throw new InvalidDataException("RECOVERY2_ORIGINAL_MARK_PARITY");
                        if(eligible is not null&&!eligible.Contains(at))excluded++;
                    }
                    if(eligible is not null)
                    foreach(long at in eligible)
                    {
                        if(!diagnostic.ContainsKey(at))throw new InvalidDataException("RECOVERY2_CLOCK_PARITY");
                        var q=original.Charge(symbol,c.QuoteAsset,at,prior);
                        if(c.SwapCalculationType==1&&q.Bid is null)required.Add((symbol,at,"BID"));
                        if(q.QuoteToEur is null&&input.Routes.TryGetValue(c.QuoteAsset,out var route))
                            foreach(var hop in route)
                                foreach(string s in original.MissingFundingFxSides(hop.Symbol,at))required.Add((hop.Symbol,at,s));
                    }
                    decimal? funding=Financing(terms,from,through,side,units,at=>
                        recovered.Charge(symbol,c.QuoteAsset,at,useClosed?new Dictionary<(string Symbol,long ChargeAt),long>():null));
                    if(funding<0m)funding*=1m+stress;
                    decimal booked=w.GetProperty("BookedSignedEur").GetDecimal();
                    decimal? delta=funding-booked;sum+=delta;
                    if(funding.HasValue)settled++;
                    windows.Add(new {Id=id,Stress=stress,Symbol=symbol,PositionId=position,FromExclusive=from,Through=through,
                        EligibleClocks=eligible,DiagnosticClocks=diagnostic.Keys.OrderBy(x=>x).ToArray(),
                        BookedSignedEur=booked,FundingSignedEur=funding,AdditionalFundingSignedEur=delta,
                        Status=funding.HasValue?"CONDITIONALLY_RECONCILED":"UNRESOLVED"});
                }
                bool flat=result.GetProperty("OpenPositions").GetInt32()==0&&result.GetProperty("PendingIntents").GetInt32()==0;
                decimal? cash=result.GetProperty("CashEur").GetDecimal()+sum;
                books.Add(new {Id=id,Stress=stress,Windows=outstanding.Length,ConditionalCashEur=cash,
                    ConditionalTerminalNetEur=flat?cash-300m:null,Flat=flat,OriginalEquityHistoryRestored=false});
            }
        }
        if(!planning&&!required.IsSubsetOf(witnessSeen))throw new InvalidDataException("RECOVERY2_WITNESS_INCOMPLETE");
        File.WriteAllBytes(outputPath,JsonSerializer.SerializeToUtf8Bytes(new {Study="OWNER_NATIVE_FUNDING_RECOVERY_2",
            SourceSha256=hash,OriginalWindows=originalWindows,ReconciledWindows=settled,ExcludedDiagnosticClocks=excluded,
            Targets=required.OrderBy(x=>x.Symbol).ThenBy(x=>x.At).ThenBy(x=>x.Side).Select(x=>new {x.Symbol,x.At,x.Side}).ToArray(),
            Books=books,Windows=windows,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=false,
            HistoricalEquityCertified=false,HistoricalTariffCertified=false},Json));
        return 0;
    }
}
