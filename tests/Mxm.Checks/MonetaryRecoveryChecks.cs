using Mxm.Core;
using System.Text.Json;

internal static class MonetaryRecoveryChecks
{
    public static void Run(Action<bool,string> check)
    {
        const string account="DETERMINISTIC_CONTRACT_ACCOUNT";string proof=new('b',64);
        MonetaryLeg Leg(decimal n,long at,string ccy="EUR",decimal rate=1,long? rateAt=null)=>new(n,ccy,rate,rateAt??at,proof);
        AttributedMoneyFact Fact(string id,string order,string pos,string ledger,string kind,int side,decimal units,long at,decimal gross,decimal fee,decimal conversion=0,decimal? price=10)=>
            new(account,"BROKER_EXECUTION_FACT",kind,"deal/"+id,id,order,pos,ledger,"SYNTH",side,units,at,at,at,price,Leg(gross,at),Leg(fee,at),Leg(conversion,at),null,proof);
        var f1=Fact("d1","open","p","local","OPEN",1,1,2000,0,.1m);
        var f2=Fact("d2","open","p","local","OPEN",1,1,3000,0,.1m,price:12);
        var funding=new AttributedMoneyFact(account,"BROKER_EXECUTION_FACT","FUNDING","funding/swap","swap","","p","local","SYNTH",1,0,3500,3500,3500,null,null,null,null,Leg(-.04m,3500),proof);
        var close1=Fact("d3","close1","p","local","CLOSE",-1,1,4000,-1,.1m,.02m,9);
        var close2=Fact("d4","close2","p","local","CLOSE",-1,1,5000,2,.1m,.03m,14);
        var intents=new[]{new LocalIntentIdentity("request-open","open","p","SYNTH",1,2,false,1000,"local"),
            new LocalIntentIdentity("request-close1","close1","p","SYNTH",-1,1,true,3800,"local"),
            new LocalIntentIdentity("request-close2","close2","p","SYNTH",-1,1,true,4800,"local")};
        var all=new[]{f1,f2,funding,close1,close2};
        MoneyRecoveryBatch Batch(AttributedMoneyFact[] facts,decimal cash,long at)
        {
            var fills=facts.Where(f=>f.Kind!="FUNDING").ToArray();
            var orders=fills.GroupBy(f=>f.OrderId).Select(g=>{
                var i=intents.Single(x=>x.OrderId==g.Key);decimal units=g.Sum(x=>x.Units);
                return new BrokerOrderIdentity(g.Key,i.IntentId,i.PositionId,i.Symbol,i.Side,i.RequestedUnits,units,i.Closing,
                    units==i.RequestedUnits?"FILLED":"ACTIVE",g.Max(x=>x.At));
            }).ToArray();
            var deals=fills.Select(f=>new BrokerDealIdentity(f.DealId,f.OrderId,f.PositionId,f.Symbol,f.Side,f.Units,f.Kind=="CLOSE",f.At)).ToArray();
            decimal remaining=fills.Sum(f=>f.Kind=="OPEN"?f.Units:-f.Units);
            var positions=remaining>0?new[]{new BrokerPositionIdentity("p","SYNTH",1,remaining)}:Array.Empty<BrokerPositionIdentity>();
            var s=new BrokerIdentitySnapshot(account,at,0,at,true,true,true,orders,deals,positions);
            var funds=facts.Where(f=>f.Kind=="FUNDING").Select(f=>new ConfirmedFundingEvent(f.DealId,f.PositionId,f.Symbol,f.At,f.Financing!.Amount,f.Financing.Currency,f.AvailableAt,proof)).ToArray();
            return new(account,"BROKER_EXECUTION_FACT",s,facts,cash,true,true,true,false,funds,at);
        }
        var session=new NativeFundedSession(account,intents:intents,journalContinuityProven:true);
        var first=Batch(new[]{f1},199.9m,2500);
        // Only intents already submitted may occur in a current snapshot.
        first=first with {BrokerCashObservedAt=6000,Snapshot=first.Snapshot with {At=6000,HistoryThrough=6000}};
        var accepted=session.ReconcileMoney(first);
        check(accepted.Adopted&&accepted.RetainedLedger.CashEur==199.9m&&accepted.RetainedLedger.OpenPositions==1,
            "positive partial execution imports its cash debit without waiting for full order completion");
        check(accepted.RetainedLedger.LiquidationEquityEur is null&&!accepted.OrdersEnabled,
            "missing broker floating liquidation evidence cannot become a zero loss or trading permission");
        var omittedNode=System.Text.Json.Nodes.JsonNode.Parse(JsonSerializer.Serialize(first with {BrokerCashEur=200}))!;
        omittedNode["Facts"]![0]!["Commission"]!.AsObject().Remove("Amount");
        var omittedAmount=JsonSerializer.Deserialize<MoneyRecoveryBatch>(omittedNode.ToJsonString())!;
        var noSilentZero=new NativeFundedSession(account,intents:intents,journalContinuityProven:true);
        check(!noSilentZero.ReconcileMoney(omittedAmount).Adopted&&noSilentZero.Ledger.Summary().CashEur==200,
            "an omitted JSON monetary Amount is unknown, never a default zero commission");
        var explicitZero=first with {Facts=new[]{f1 with {Commission=Leg(0,2000)}},BrokerCashEur=200};
        check(noSilentZero.ReconcileMoney(explicitZero).Adopted,
            "an explicitly evidenced zero commission remains distinct from an omitted amount");
        var before=session.Checkpoint();var repeated=session.ReconcileMoney(first);
        check(repeated.Adopted&&session.Checkpoint()==before,"same financial snapshot is idempotent");
        var missingCost=Batch(new[]{f1,f2 with {Commission=null}},199.8m,6000);
        var rejected=session.ReconcileMoney(missingCost);
        check(!rejected.Adopted&&session.Checkpoint()==before,"unknown commission rejects entire recovery atomically");
        rejected=session.ReconcileMoney(Batch(new[]{f1,f2},999,6000));
        check(!rejected.Adopted&&session.Checkpoint()==before,"cash mismatch is not patched by a deposit or balancing entry");
        rejected=session.ReconcileMoney(Batch(new[]{f1 with {Commission=Leg(.2m,2000)},f2},199.7m,6000));
        check(!rejected.Adopted&&session.Checkpoint()==before,"recovery cannot rewrite previously accepted monetary history");
        var afterTwo=Batch(new[]{f1,f2},199.8m,6000);accepted=session.ReconcileMoney(afterTwo);
        check(accepted.Adopted&&session.Ledger.Summary().CompleteRoundTrips==0,"split entries accumulate in one position, not two round trips");
        session=NativeFundedSession.Restore(session.Checkpoint(),account);
        var partial=Batch(new[]{f1,f2,funding,close1},198.64m,6000);accepted=session.ReconcileMoney(partial);
        check(accepted.Adopted&&accepted.RetainedLedger.CompleteRoundTrips==0&&accepted.RetainedLedger.OpenPositions==1,
            "cash funding and conversion costs survive restart and partial closing");
        var fragments=session.Ledger.ClosedFragments();
        check(fragments[0].SpreadEur is null&&fragments[0].SlippageEur is null,
            "broker realized price PNL cannot invent spread/slippage decomposition");
        var final=Batch(all,200.51m,6000);accepted=session.ReconcileMoney(final);
        check(accepted.Adopted&&accepted.RetainedLedger.CompleteRoundTrips==1&&accepted.RetainedLedger.ClosedNetEur==.51m,
            "full lifecycle cash equals200 plus net after commissions conversion and financing");
        check(session.Observe(final.Snapshot,200.51m).Identity.UnresolvedIntents==0,
            "monetarily imported terminal executions no longer remain import-required");
        var checkpoint=session.Checkpoint();
        rejected=session.ReconcileMoney(final with {Facts=all.Skip(1).ToArray()});
        check(!rejected.Adopted&&session.Checkpoint()==checkpoint,"history truncation cannot drop an earlier entry fee or loss");
        rejected=session.ReconcileMoney(final with {Facts=Array.Empty<AttributedMoneyFact>(),FundingRecords=Array.Empty<ConfirmedFundingEvent>(),
            BrokerCashEur=200,Snapshot=final.Snapshot with {Orders=Array.Empty<BrokerOrderIdentity>(),Deals=Array.Empty<BrokerDealIdentity>(),Positions=Array.Empty<BrokerPositionIdentity>()}});
        check(!rejected.Adopted&&session.Checkpoint()==checkpoint,
            "even a fully truncated supposedly-complete broker snapshot cannot reset a previously losing journal to200");
        rejected=session.ReconcileMoney(final with {Facts=all.Select(f=>f.EventId==f2.EventId?f with {Commission=Leg(.1m,3000,"USD",.9m,4000)}:f).ToArray()});
        check(!rejected.Adopted,"conversion observed after the monetary event cannot value an earlier debit");
        var unknown=new NativeFundedSession(account,intents:intents);
        check(!unknown.ReconcileMoney(final).Adopted,"an empty or restored journal does not certify actual initial funding");
        check(!session.ReconcileMoney(final with {BrokerCashObservedAt=1000}).Adopted,
            "matching but stale broker cash cannot certify current financial reconciliation");
        check(!session.ReconcileMoney(final with {AdditionalExternalCashflowDetected=true}).Adopted,
            "external funding cannot be silently absorbed into the continuous owner capital");
        // The initial200 and cash history here are TEST assumptions, not broker certificates.
        var restored=NativeFundedSession.Restore(checkpoint,account);
        check(restored.Ledger.Summary()==session.Ledger.Summary(),"v2 monetary state survives account-bound restore");
        bool modelFillBlocked=false;
        try{restored.Ledger.Apply(new LedgerEvent("forbidden",7000,"MARK","","",0,0,0,0,0,0,7000,7000,1,"TEST",proof,Array.Empty<LedgerQuote>()));}
        catch(InvalidOperationException){modelFillBlocked=true;}
        check(modelFillBlocked,"a recovered execution book cannot accept a modeled event as a real broker cash fact");
        // Two symbols share exactly one cash book; a partial account snapshot
        // must never create a separate EUR200 wallet for the second position.
        var aOpen=Fact("a-open","a-o","a-p","a-local","OPEN",1,1,2000,0,.1m);
        var bOpen=Fact("b-open","b-o","b-p","b-local","OPEN",-1,2,2500,0,.2m,price:20) with {Symbol="OTHER"};
        var aClose=Fact("a-close","a-c","a-p","a-local","CLOSE",-1,1,4000,-3,.1m,.01m,7);
        var bClose=Fact("b-close","b-c","b-p","b-local","CLOSE",1,2,5000,2,.2m,.02m,19) with {Symbol="OTHER"};
        var jointFacts=new[]{aOpen,bOpen,aClose,bClose};
        var jointIntents=jointFacts.Select(f=>new LocalIntentIdentity("i/"+f.OrderId,f.OrderId,f.PositionId,f.Symbol,f.Side,f.Units,f.Kind=="CLOSE",f.At-1000,f.LedgerPositionId)).ToArray();
        MoneyRecoveryBatch Joint(int count,decimal cash){
            var fs=jointFacts.Take(count).ToArray();
            var os=fs.Select(f=>new BrokerOrderIdentity(f.OrderId,"i/"+f.OrderId,f.PositionId,f.Symbol,f.Side,f.Units,f.Units,f.Kind=="CLOSE","FILLED",f.At)).ToArray();
            var ds=fs.Select(f=>new BrokerDealIdentity(f.DealId,f.OrderId,f.PositionId,f.Symbol,f.Side,f.Units,f.Kind=="CLOSE",f.At)).ToArray();
            var ps=fs.GroupBy(f=>f.PositionId).Where(g=>g.Sum(f=>f.Kind=="OPEN"?f.Units:-f.Units)>0)
                .Select(g=>new BrokerPositionIdentity(g.Key,g.First().Symbol,g.First().Side,g.Sum(f=>f.Kind=="OPEN"?f.Units:-f.Units))).ToArray();
            return new(account,"BROKER_EXECUTION_FACT",new(account,8000,0,8000,true,true,true,os,ds,ps),fs,cash,true,true,true,false,Array.Empty<ConfirmedFundingEvent>(),8000);
        }
        var joint=new NativeFundedSession(account,intents:jointIntents,journalContinuityProven:true);
        var jointReport=joint.ReconcileMoney(Joint(2,199.7m));
        check(jointReport.Adopted&&jointReport.RetainedLedger.OpenPositions==2&&jointReport.RetainedLedger.CashEur==199.7m,
            "simultaneous symbols reserve their actual fee debits in one continuous200 EUR cash book");
        joint=NativeFundedSession.Restore(joint.Checkpoint(),account);jointReport=joint.ReconcileMoney(Joint(3,196.59m));
        check(jointReport.Adopted&&jointReport.RetainedLedger.OpenPositions==1&&jointReport.RetainedLedger.CompleteRoundTrips==1,
            "closing one losing exposure leaves the other position and common cash intact after restart");
        jointReport=joint.ReconcileMoney(Joint(4,198.37m));
        check(jointReport.Adopted&&jointReport.RetainedLedger.CompleteRoundTrips==2&&jointReport.RetainedLedger.ClosedNetEur==-1.63m,
            "the combined book reconciles to200 minus total economic loss, never summed separate wallets");
        // Old v1 native modeled checkpoints remain loadable without changing event IDs.
        var model=new NativeFundedLedger();
        var request=new LedgerEvent("old-request",1000,"REQUEST_OPEN","old-position","OLD",1,1,0,0,0,0,0,0,1000,"TEST",proof,Array.Empty<LedgerQuote>());
        var fill=request with {EventId="old-fill",At=2000,Kind="OPEN_FILL",ExecutionPrice=10.01m,FeeEur=.1m,MarginPerUnit=1,
            Quotes=new[]{new LedgerQuote("OLD",2000,10,10.01m,1,1,0,.1m,1)}};
        model.Apply(request);model.Apply(fill);
        using var envelope=JsonDocument.Parse(model.Checkpoint());
        var node=System.Text.Json.Nodes.JsonNode.Parse(envelope.RootElement.GetProperty("Payload").GetString()!)!;
        node["Version"]="mxm-native-funded-ledger-v1";node.AsObject().Remove("MonetaryDomain");
        foreach(var item in node["Positions"]!.AsObject()){
            item.Value!.AsObject().Remove("EntryConversionRemaining");item.Value.AsObject().Remove("MonetaryDomain");
        }
        string payload=node.ToJsonString();
        string hash=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
        var legacy=JsonSerializer.Serialize(new {Payload=payload,Sha256=hash,MaximumStalenessMs=1000});
        var migrated=NativeFundedLedger.Restore(legacy);var preserved=migrated.Summary();migrated.Apply(fill);
        check(migrated.Summary()==preserved && preserved.CashEur==199.9m && preserved.OpenPositions==1,
            "nonempty v1 checkpoint migrates with cash positions pending IDs and duplicate-fill idempotence intact");
    }
}
