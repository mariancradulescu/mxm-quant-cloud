"""Pure frozen POLICY ATTRIBUTION on previously collected Pepperstone event quotes.

The actual closed signal, cost screen and broker scope are UNCHANGED.
Counterfactual prices are never trades, a backtest survivor or a new signal.
No additional broker requests, no order classes, no public raw prices.
"""
import hashlib,json,os,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from decimal import Decimal as D
from .custody import unseal_new
from .tick_volume_net import signals,read_quote,commission_eur,funded_and_diagnostics,financing_proven
from .decode import need

SOURCE_RUN="41614667957"
SLIPS=("0.5","1","2")

def count_week(ts):
    d=datetime.fromtimestamp(ts/1000,timezone.utc)
    m=d.toordinal()-d.weekday()
    return m

def calc(p,e,x,c,units,slip,fee):
    a=D(e["ask"])/100000; b=D(e["bid"])/100000
    z=D(x["ask"])/100000; y=D(x["bid"])/100000
    credit=(D("1")-fee)/z
    debit=(D("1")+fee)/y
    eur_ref=(credit+debit)/2
    side=D(p["side"])
    g=side*units*((y+z)-(a+b))/2*eur_ref
    sp=units*((a-b)+(z-y))/2*eur_ref
    sl=2*units*slip*eur_ref
    entry=a+slip if side>0 else b-slip
    exit=y-slip if side>0 else z+slip
    usd=side*units*(exit-entry)
    converted=usd*(credit if usd>=0 else debit)
    fx=g-sp-sl-converted
    need(fx>=D("-0.00000001"),"CONVERSION_RECONCILIATION")
    fx=max(D("0"),fx)
    comm=commission_eur(c,int(units),entry-slip if side>0 else entry+slip,b,a)+commission_eur(c,int(units),exit+slip if side>0 else exit-slip,y,z)
    net=converted-comm
    need(abs(g-sp-sl-fx-comm-net)<D("0.000000001"),"POLICY_ACCOUNTING_INVARIANT")
    return {"gross":g,"spread":sp,"slippage":sl,"fx":fx,"commission":comm,"net":net}

def study(b):
    frozen=signals(b)
    old=b["nativeReceipt"]
    need(old["model"]=="EURUSD_H1_TICK_VOLUME_PRICE_DISLOCATION_V1" and
         old["predeclaredSelectionNetSupport"] is False and old["diagnostic"]["proposals"]==len(frozen["plan"]),"ORIGINAL_FROZEN_MODEL_DIFFERENT")
    terms=b["contract"];units=int(terms["minVolume"])//100
    need(units>0 and int(terms["minVolume"])%100==0,"BROKER_UNIT_SCALING")
    spread=D(str(b["trainSpreadPrice"]))
    slip0=D(str(b["trainSlippagePrice"]))
    train_screen_cost=spread+2*slip0+2*D(str(b["screenMinCommissionEur"]))*D(str(b["screenEurAsk"]))/units
    fee=D(str(terms["pnlConversionFeeRate"]))/10000
    bygroup={}
    for multiplier in SLIPS:
        slip=slip0*D(multiplier)
        groups={"TRAIN_COST_ADMITTED":[],"TRAIN_COST_REJECTED":[]}
        incomplete=0
        for p in frozen["plan"]:
            entry=read_quote(b,p["signal"]);exit=read_quote(b,p["exit"])
            if entry is None or exit is None:
                incomplete+=1;continue
            admitted=abs(D(str(p["forecast"])))*D(str(p["price"]))>train_screen_cost
            g="TRAIN_COST_ADMITTED" if admitted else "TRAIN_COST_REJECTED"
            outcome=calc(p,entry,exit,terms,D(units),slip,fee)
            outcome["exitMs"]=p["exit"]
            groups[g].append(outcome)
        results={}
        for name,rows in groups.items():
            total=lambda field:sum((r[field] for r in rows),D("0"))
            byweek={w:[] for w in frozen["eligibleMondayUtcMs"]}
            for r in rows:
                for w in byweek:
                    if w<=r["exitMs"]<w+7*86400000:
                        byweek[w].append(r);break
            weekly=[sum((v["net"] for v in byweek[w]),D("0")) for w in sorted(byweek)]
            count=len(rows)
            results[name]={"completeQuoteBasedCounterfactualEpisodes":count,
                "positiveGrossEpisodes":sum(r["gross"]>0 for r in rows),
                "positiveNetEpisodes":sum(r["net"]>0 for r in rows),
                "sumGrossEur":str(total("gross")),
                "sumSpreadEur":str(total("spread")),
                "sumCommissionEur":str(total("commission")),
                "sumSlippageAssumptionEur":str(total("slippage")),
                "sumConversionEur":str(total("fx")),
                "sumNetEur":str(total("net")),
                "meanNetPerEpisodeEur":str(total("net")/count) if count else None,
                "eligibleWeeks":len(weekly),
                "positiveNetWeeks":sum(x>0 for x in weekly),
                "weeklyNetEur":[str(x) for x in weekly]}
        need(sum(x["completeQuoteBasedCounterfactualEpisodes"] for x in results.values())+incomplete==len(frozen["plan"]),"CLOSED_POLICY_ATTRIBUTION_COUNTS")
        bygroup[multiplier]={"hypotheticalSlippageScale":multiplier,"missingEventQuotePairs":incomplete,
                             "groups":results}
    original_admitted=old["diagnostic"]["proposals"]-old["diagnostic"]["forecastBelowTrainingCost"]
    need(bygroup["1"]["groups"]["TRAIN_COST_ADMITTED"]["completeQuoteBasedCounterfactualEpisodes"]==original_admitted and
        bygroup["1"]["groups"]["TRAIN_COST_REJECTED"]["completeQuoteBasedCounterfactualEpisodes"]==old["diagnostic"]["forecastBelowTrainingCost"],"ORIGINAL_SELECTION_IDENTITY")
    return {"schema":"mxm.frozen-h1-policy-cost-attribution.v1",
            "sourceRunId":int(SOURCE_RUN),"hypothesis":old["model"],
            "countOriginalProposals":len(frozen["plan"]),
            "originalAdmittedCount":original_admitted,
            "originalRejectedCount":old["diagnostic"]["forecastBelowTrainingCost"],
            "completeSourceHistoryH1":len(b["bars"]),
            "originalFrozenSelectionNETEur1x":old["fundedScenarios"][1]["portfolioEur200QuoteReplay"]["closed_net_eur"],
            "slippageIsHalfTrainObservedSpreadProxyNotMeasuredFill":True,
            "currentBrokerSwapScheduleOutsideHours":financing_proven(terms),
            "slippageScenarios":bygroup,
            "actualFundedPortfolioEurNetNotRecomputed":True,
            "counterfactualPortfolioFinanced":False,
            "historicBrokerTariffsCertified":False,
            "futureConfirmationUntouched":True,
            "modelRetunedOrPromoted":False,
            "originalClosedVerdictUnchanged":True,
            "ordersSubmitted":0,
            "interpretation":"Historical BID/ASK quote-crossing min-lot thought experiment for all FROZEN proposals; groups reflect original TRAIN-only cost admission. Summed independent no-overlap quote outcomes are NOT independently funded EUR200 portfolio, real fills, or permission to remove original risk/cost filters."}

def run():
    data=Path("sealed-output/source.envelope.json").read_bytes()
    pub=json.loads(Path("sealed-output/receipt.public.json").read_text())
    need(pub.get("runId")==SOURCE_RUN and hashlib.sha256(data).hexdigest()==pub.get("sha256"),"ORIGINAL_AUTHENTIC_CIPHERTEXT_SHA")
    key=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(key.strip()),"CUSTODY_PRIVATE_MISSING")
    b=json.loads(unseal_new(data,key,SOURCE_RUN))
    res=study(b)
    res["originalSourceCiphertextSha256"]=pub["sha256"]
    res["originalCustodyRunStatus"]="INDEPENDENT_READBACK_SUCCESS_FROM_ORIGINAL_RUN"
    Path("volume-policy-attribution.public.json").write_text(json.dumps(res,sort_keys=True,indent=2)+"\n")
    print("AUTHENTIC_FROZEN_VOLUME_POLICY_ATTRIBUTION "+json.dumps(res,sort_keys=True),flush=True)

if __name__=="__main__":
    try:run()
    except Exception:
        print("H1_VOLUME_POLICY_ATTRIBUTION_FAILED_CLOSED",flush=True)
        sys.exit(1)
