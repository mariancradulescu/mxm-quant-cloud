"""IES1: shared *exposed* causal benchmark and EUR fee audit on ORIGINAL BDP1 raw.

No replay of BDP1's closed forecasts, models or portfolio. No new broker
requests. Authenticated raw archive and original account binding are audited by
the existing source-only audit() method; no BDP1 readback()/cost_contexts().
"""
import base64
import hashlib
import json
import math
import os
import statistics
from collections import Counter
from decimal import Decimal as D
from pathlib import Path
from .custody import unseal_new
from .decode import decode_side
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .portfolio_discovery_source import audit as source_only_audit
from .contract_eur_cost import attribute_costs,IncompleteCostEvidence

PROTOCOL=Path("research/integrated_economic_surface_protocol.json")
ORIGINAL=Path("research/portfolio_discovery_protocol.json")
SEALED=Path("ies1-original-bdp1-source/source.envelope.json")
HOUR=3600000
M5=300000
WEEK=7*24*HOUR

def need(check,code):
    if not check:
        raise ValueError(code)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def _quantile(values,fraction):
    if not values:return None
    rows=sorted(values)
    return rows[max(0,math.ceil(len(rows)*fraction)-1)]

def source():
    p=json.loads(PROTOCOL.read_text())
    original=json.loads(ORIGINAL.read_text())
    need(p["id"]=="IES1" and p["newBrokerRequests"]==0 and
         p["sourceUniverse"]==original["universe"] and
         p["sourceWeeks"]==52,"IES1_EX_ANTE_PROTOCOL")
    raw=SEALED.read_bytes()
    need(sha(raw)==p["sourceCiphertextSha256"],"IES1_ORIGINAL_CIPHER_SHA")
    b=json.loads(unseal_new(raw,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),
                            str(p["originalSourceRunId"])))
    need(b["schema"]=="mxm-bdp1-source-v1" and
         b["protocolSha256"]==sha(ORIGINAL.read_bytes()) and
         b["readOnly"] is True and b["depositCurrency"]=="EUR",
         "IES1_ORIGINAL_BINDING")
    need(source_only_audit(b,original)==b["auditReceipt"],
         "IES1_ORIGINAL_RAW_RECONSTRUCTION")
    return p,b

def _first_paired_raw_quote(b,symbol,nominal):
    indices=b["costIndices"].get(str(nominal),{}).get(symbol)
    if indices is None or len(indices)!=2:return None,"MISSING_SIDES"
    states={}
    for side,ix in zip((e.BID,e.ASK),indices):
        row=b["raw"][ix]
        req=m.ProtoOAGetTickDataReq()
        res=m.ProtoOAGetTickDataRes()
        req.ParseFromString(base64.b64decode(row["requestProtobuf"]))
        res.ParseFromString(base64.b64decode(row["protobuf"]))
        if (req.symbolId!=b["symbols"][symbol]["symbolId"] or req.type!=side or
            req.fromTimestamp!=nominal-2000 or req.toTimestamp!=nominal+58000 or
            not res.HasField("hasMore")):
            raise ValueError("IES1_QUOTE_RAW_BINDING")
        if res.hasMore:return None,"TRUNCATED_PAGE"
        states[side]=decode_side(res.tickData,nominal-2000,nominal+58000)
    events=sorted(set(t for rows in states.values() for t,v in rows
                        if nominal+1000<=t<=nominal+11000))
    prior={}
    for t in events:
        for side in (e.BID,e.ASK):
            earlier=[(ts,price) for ts,price in states[side] if ts<=t]
            if earlier:prior[side]=max(earlier,key=lambda row:row[0])
        if not all(side in prior for side in (e.BID,e.ASK)):continue
        bt,bp=prior[e.BID];at,ap=prior[e.ASK]
        if t-bt<=2000 and t-at<=2000 and abs(bt-at)<=2000 and bp>0 and ap>bp:
            return (t,D(bp)/100000,D(ap)/100000),"PAIRED"
    return None,"NO_FRESH_PAIRED_QUOTES"

def _fee_surface(b,p):
    cost_rows={s:[] for s in p["sourceUniverse"]}
    failures=Counter()
    sample_clocks=sorted(map(int,b["costIndices"]))
    need(len(sample_clocks)==18 and max(sample_clocks)<p["calendar"]["developmentEndUtcMs"],
         "IES1_COST_DEVELOPMENT_ONLY")
    for clock in sample_clocks:
        quotes={}
        for s in p["sourceUniverse"]:
            q,status=_first_paired_raw_quote(b,s,clock)
            if q is not None:quotes[s]=q
            else:failures[s+"/"+status]+=1
        eurusd=quotes.get("EURUSD")
        if eurusd is None:
            for s in quotes:failures[s+"/EUR_CONVERSION_MISSING"]+=1
            continue
        eur_t,eur_bid,eur_ask=eurusd
        usd_eur=1/eur_bid  # Conservative payable USD -> EUR.
        for s,(t,bid,ask) in quotes.items():
            if abs(t-eur_t)>2000:
                failures[s+"/EUR_RATE_NOT_SYNCHRONIZED"]+=1
                continue
            term=b["symbols"][s]
            quote=term["quoteAsset"]
            rates={"EUR":D(1),"USD":usd_eur}
            if quote=="JPY":
                rates["JPY"]=usd_eur/bid
            elif quote=="CAD":
                rates["CAD"]=usd_eur/bid
            elif quote!="USD" and quote!="EUR":
                failures[s+"/QUOTE_EUR_ROUTE_UNAVAILABLE"]+=1
                continue
            contract_msg=m.ProtoOASymbolByIdRes()
            contract_msg.ParseFromString(base64.b64decode(
                b["raw"][term["contractRawIndex"]]["protobuf"]))
            need(len(contract_msg.symbol)==1 and
                 contract_msg.symbol[0].symbolId==term["symbolId"],
                 "IES1_CONTRACT_PROVENANCE")
            c=contract_msg.symbol[0]
            try:
                units=D(c.minVolume)/100
                out=attribute_costs(c,quote,units,bid,ask,rates)
                notional=units*((bid+ask)/2)*rates[quote]
                if notional<=0:raise IncompleteCostEvidence("ZERO_NOTIONAL")
                row={"clockUtcMs":clock,"units":str(units),
                    "observedSpreadEur":out["spreadObservedEur"],
                    "oneSideCurrentContractCommissionEur":
                       out["feeProvenance"]["oneSideContractCommissionEur"],
                    "knownNonFinancingCurrentTermCostFloorEur":
                       out["knownComponentsSubtotalEur"],
                    "observedSpreadBps":round(10000*float(D(out["spreadObservedEur"])/notional),6),
                    "currentContractCommissionRoundTripBps":
                       round(10000*float(D(out["roundTripCurrentContractCommissionEur"])/notional),6),
                    "knownNonFinancingCurrentTermCostFloorBps":
                       round(10000*float(D(out["knownComponentsSubtotalEur"])/notional),6),
                    "minimumCurrentMarginEur":term["currentMinMarginEur"],
                    "contractRateWireExplicit":out["feeProvenance"]["rateWireExplicit"],
                    "contractMinimumFeeWireExplicit":out["feeProvenance"]["floorWireExplicit"],
                    "pnlConversionRateWireExplicit":c.HasField("pnlConversionFeeRate"),
                    "slippageKnown":False,"financingKnown":False,
                    "historicalContractTermsCertified":False,
                    "brokerFilled":False}
                cost_rows[s].append(row)
            except IncompleteCostEvidence as exc:
                failures[s+"/"+str(exc)]+=1
    return cost_rows,dict(sorted(failures.items()))

def _predictive_calibration(b,p):
    cal=p["calendar"]
    need(cal["endUtcMs"]-cal["startUtcMs"]==52*WEEK and
         cal["developmentEndUtcMs"]-cal["startUtcMs"]==26*WEEK and
         cal["selectionEndUtcMs"]-cal["developmentEndUtcMs"]==13*WEEK,
         "IES1_BOUNDARIES_CHANGED")
    out={}
    for name in p["sourceUniverse"]:
        source_rows=b["bars"].get(name,[])
        closes={int(x[0]):int(x[5]) for x in source_rows if int(x[5])>0}
        need(len(closes)==len(source_rows),"IES1_SOURCE_M5_DUPLICATE_OR_INVALID")
        data=[]
        omissions=Counter()
        for at in range(cal["startUtcMs"]+2*HOUR,cal["endUtcMs"]-HOUR,HOUR):
            if any(at+i*M5 not in closes for i in range(-13,12)):
                omissions["missingCompletePastAndNextM5"]+=1
                continue
            old=closes[at-13*M5];current=closes[at-M5];future=closes[at+11*M5]
            past=math.log(current/old);next_ret=math.log(future/current)
            if past==0 or next_ret==0:
                omissions["flatDirectionalLabel"]+=1
                continue
            pred=1 if past>0 else 0
            label=1 if next_ret>0 else 0
            week=(at-cal["startUtcMs"])//WEEK
            data.append((int(week),(pred-label)**2,10000*(2*pred-1)*next_ret,
                         abs(10000*next_ret)))
        result={}
        for label,lo,hi in (("development",0,26),("selection",26,39),
                            ("globallyExposedAudit",39,52)):
            rows=[r for r in data if lo<=r[0]<hi]
            allweeks=[sum(r[0]==w for r in rows) for w in range(lo,hi)]
            result[label]={
                "completeCausalLabelPairs":len(rows),
                "activeWeeks":sum(x>0 for x in allweeks),
                "emptyWeeks":sum(x==0 for x in allweeks),
                "allWeeklyCounts":allweeks,
                "meanDiagnosticBrier":round(statistics.mean(r[1] for r in rows),6) if rows else None,
                "neutralChanceBrierBenchmark":0.25,
                "brierSkillVsNeutral":round(1-statistics.mean(r[1] for r in rows)/.25,6) if rows else None,
                "meanOneHourSignedGrossBps":round(statistics.mean(r[2] for r in rows),6) if rows else None,
                "meanAbsoluteNextHourMoveBps":round(statistics.mean(r[3] for r in rows),6) if rows else None,
                "p90AbsoluteNextHourMoveBps":round(_quantile([r[3] for r in rows],.9),6) if rows else None,
                "qualification":False}
        out[name]={"completeM5Bars":len(closes),"missingOrFlatDiagnosticClocks":dict(omissions),
                   "phase":result}
    return out

def main():
    p,b=source()
    fees,gaps=_fee_surface(b,p)
    diagnostic=_predictive_calibration(b,p)
    out={"schema":"mxm-ies1-existing-authentic-source-integrated-diagnostic-v1",
        "sourceRunId":p["originalSourceRunId"],
        "sourceCiphertextSha256":p["sourceCiphertextSha256"],
        "originalBoundRawAuditVerified":True,
        "accountEurVerified":True,
        "sourceM5PriceRows":sum(len(b["bars"][s]) for s in p["sourceUniverse"]),
        "sourceInstrumentCount":len(p["sourceUniverse"]),
        "sourceNewRequests":0,"originalModelsReexecuted":False,
        "instrumentDiagnostics":diagnostic,
        "currentContractWithObservedHistoricalQuoteFeeSamples":{
          s:{"count":len(rows),
             "meanObservedSpreadBps":round(statistics.mean(x["observedSpreadBps"] for x in rows),6) if rows else None,
             "meanCurrentContractCommissionRoundTripBps":round(statistics.mean(x["currentContractCommissionRoundTripBps"] for x in rows),6) if rows else None,
             "meanIllustrativeCostFloorBps":round(statistics.mean(x["knownNonFinancingCurrentTermCostFloorBps"] for x in rows),6) if rows else None,
             "minimumMarginCurrentEur":b["symbols"][s]["currentMinMarginEur"],
             "currentMinMarginBelow200Eur":D(b["symbols"][s]["currentMinMarginEur"])<200,
             "sampleRows":rows}
          for s,rows in fees.items()},
        "quoteAndContractCostUnavailability":gaps,
        "sourceAndCostExposed":True,"independentConfirmation":False,
        "costScenarioCertifiedHistorical":False,"financingKnown":False,
        "slippageKnown":False,"executionPriceAndVolumeCertified":False,
        "fundedNetEur":None,"nativeAllocatorInvoked":False,
        "systemHard21Proven":False,"continuous30PercentDrawdownCertified":False,
        "promotedStrategy":None,"ordersSubmitted":0,"cloudActivated":False,
        "verdict":"EXPOSED_INTEGRATED_EVIDENCE_DIAGNOSTIC_NO_TRADING_OR_PORTFOLIO_PROMOTION"}
    dest=Path("integrated-economic-surface.public.json")
    dest.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("IES1_AUTHENTIC_ORIGINAL_ARCHIVE_DIAGNOSTIC_COMPLETE_NO_NET",flush=True)
    print("IES1_PUBLIC_SHA256="+sha(dest.read_bytes()),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as error:
        print("IES1_FAIL_CLOSED_"+type(error).__name__,flush=True)
        raise SystemExit(1)
