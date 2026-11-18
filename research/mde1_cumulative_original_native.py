"""MDE1: existing genuine Pepperstone XMH2+HXC1 source custody and
original existing CDH1 shared C# Core directional-vs-event diagnostic.
Python ONLY source integrity, transient transcode and existing JPN225 contract
metadata readback. No Python predictive/trading math, no new broker request.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from .custody import unseal_new
from .decode import need
from . import hxc1_historical_readback as verifier
from . import hxc1_historical_source as hxc1
from . import xmh2_m15_source as xmh2
from .ctrader_proto import OpenApiMessages_pb2 as m

OUT=Path("mde1-public")
XMH_RUN="44352570167"
HXC_RUN="43817213663"
KEY="MDE1_XMH2_44352570167_HXC1_43817213663"
SYMBOLS=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD",
         "XAUUSD","US500","NAS100","GER40","UK100","AUS200","JPN225")
CAPTURED={
    XMH_RUN:("mde1-xmh2-source",xmh2.PROTOCOL,xmh2.SOURCE_CLASS,
             "7a86c18bcc616f85039d31ed556985e6910350dca962912efda7bcf0220cd2a8",
             1644,208624),
    HXC_RUN:("mde1-hxc1-source",hxc1.PROTOCOL,hxc1.SCHEMA,
             "445195a645f5427a04bb62b8a2b755715226a3893dda27c26ec7c80786c1077d",
             1444,70867)
}


def _one_original(run:str,private:bytes):
    directory,proto,source_class,expected_cipher,requests,total=CAPTURED[run]
    origin=Path(directory)
    sealed=(origin/"source.envelope.json").read_bytes()
    receipt=json.loads((origin/"receipt.public.json").read_text())
    digest=hashlib.sha256(sealed).hexdigest()
    need(digest==expected_cipher==receipt["ciphertextSha256"],
         "MDE1_ORIGINAL_SOURCE_CIPHERTEXT_IDENTITY_FAIL")
    bundle=json.loads(unseal_new(sealed,private,run))
    # Existing independent raw-request and raw-response original-account
    # provenance verifier. No closed predictor or strategy is called.
    verifier.PROTOCOL=proto
    verifier.SCHEMA=source_class
    checked=verifier.validate(bundle,receipt,run)
    need(checked["status"]=="HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT"
         and checked["rawRequestsRebuilt"]==requests,
         "MDE1_ORIGINAL_PROTOBUF_SOURCE_NOT_RECONSTRUCTED")
    data={symbol:bundle["bars"][symbol+"/M15"] for symbol in SYMBOLS}
    need(sum(map(len,data.values()))==total,"MDE1_ORIGINAL_M15_COUNTS_CHANGED")
    need(len(bundle["identityRaw"])==14,"MDE1_SOURCE_IDENTITY_COUNT")
    return data,bundle,checked,digest


def _jpn_original_contract(bundle:dict,run:str):
    identities=bundle["identityRaw"]
    item=identities[1]
    need(item["responseType"]=="ProtoOASymbolsListRes",
         "MDE1_ORIGINAL_ROSTER_NOT_ATTACHED")
    roster=m.ProtoOASymbolsListRes()
    roster.ParseFromString(base64.b64decode(item["responseProtobuf"],validate=True))
    ids={s.symbolName:s.symbolId for s in roster.symbol if s.enabled}
    need("JPN225" in ids,"MDE1_EXACT_JPN225_NOT_AVAILABLE")
    exact_symbol_id=ids["JPN225"]
    found=[]
    for item in identities[2:]:
        need(item["responseType"]=="ProtoOASymbolByIdRes",
             "MDE1_ORIGINAL_CONTRACT_RESPONSE_MISSING")
        response=m.ProtoOASymbolByIdRes()
        response.ParseFromString(base64.b64decode(item["responseProtobuf"],validate=True))
        if any(x.symbolId==exact_symbol_id for x in response.symbol):
            found.extend(x for x in response.symbol if x.symbolId==exact_symbol_id)
    need(len(found)==1,"MDE1_EXACT_JPN225_CONTRACT_NOT_UNIQUE")
    c=found[0]
    def number_if_present(name):
        return getattr(c,name) if c.HasField(name) else None
    def format_units(name):
        v=number_if_present(name)
        return str(v/100) if v is not None else None
    # Data only: exact wire units/asset references are not a fabricated
    # EUR cost. Margin requires a SEPARATE genuine expected-margin response.
    contract={
        "originalSourceRunId":run,
        "symbolNameExact":"JPN225",
        "distinctFromJPN225_F":True,
        "originalBrokerSymbolIdentityAttested":True,
        "minimumVolumeUnits":format_units("minVolume"),
        "volumeStepUnits":format_units("stepVolume"),
        "maximumVolumeUnits":format_units("maxVolume"),
        "lotSizeUnits":format_units("lotSize"),
        "commissionTypeWire":number_if_present("commissionType"),
        "preciseCommissionRateWire":number_if_present("preciseTradingCommissionRate"),
        "minimumCommissionTypeWire":number_if_present("minCommissionType"),
        "preciseMinCommissionWire":number_if_present("preciseMinCommission"),
        "swapCalculationTypeWire":number_if_present("swapCalculationType"),
        "swapLongWire":number_if_present("swapLong"),
        "swapShortWire":number_if_present("swapShort"),
        "swapTimeUtcMinutesWire":number_if_present("swapTime"),
        "swapPeriodHoursWire":number_if_present("swapPeriod"),
        "tripleSwapWeekdayWire":number_if_present("swapRollover3Days"),
        "tradeScheduleTimezone":number_if_present("scheduleTimeZone"),
        "tradeScheduleIntervalCount":len(c.schedule),
        "exactOriginalCurrentMarginEur":None,
        "originalHistoricalExecutableQuotePair":None,
        "realizedCommissionEur":None,
        "confirmedOriginalBrokerRoundTrips":0,
        "exactOriginalMarginWasNotQueried":True
    }
    need(contract["minimumVolumeUnits"] is not None and
         float(contract["minimumVolumeUnits"])>0,
         "MDE1_JPN225_CONTRACT_MINVOLUME_NOT_PRESENT")
    return contract,exact_symbol_id


def execute():
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
         os.environ.get("GITHUB_REF")=="refs/heads/main" and
         os.environ.get("GITHUB_ACTOR")=="mariancradulescu" and
         os.environ.get("GITHUB_RUN_ATTEMPT")=="1",
         "MDE1_NOT_ORIGINAL_EXACT_OWNER")
    key=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(key.strip()),"MDE1_CUSTODY_KEY_REQUIRED")
    old,bundle1,v1,sha1=_one_original(XMH_RUN,key)
    newer,bundle2,v2,sha2=_one_original(HXC_RUN,key)
    jpn1,broker_symbol_id1=_jpn_original_contract(bundle1,XMH_RUN)
    jpn2,broker_symbol_id2=_jpn_original_contract(bundle2,HXC_RUN)
    need(broker_symbol_id1==broker_symbol_id2,
         "MDE1_EXACT_JPN225_ID_CHANGED_ACROSS_ORIGINAL_SOURCES")
    streams=[]
    count_by_market={}
    for symbol in SYMBOLS:
        before,after=old[symbol],newer[symbol]
        need(all(b[1]<=1755475200000 for b in before),
             "MDE1_EARLIER_M15_SOURCE_CROSSED_CHRONOLOGY")
        need(all(b[0]>=1755475200000 for b in after),
             "MDE1_LATER_M15_SOURCE_CROSSED_CHRONOLOGY")
        rows=before+after
        need(all(rows[i][0]>=rows[i-1][1] for i in range(1,len(rows))),
             "MDE1_SOURCE_OVERLAP_OR_REPEATED_M15")
        streams.append({"Symbol":symbol,"Period":"M15",
                        "Bars":[{"Start":z[0],"End":z[1],
                                 "Open":z[2],"High":z[3],
                                 "Low":z[4],"Close":z[5],
                                 "Volume":z[6]} for z in rows]})
        count_by_market[symbol]=len(rows)
    need(sum(count_by_market.values())==279491,
         "MDE1_FULL_ORIGINAL_279491_HISTORY_NOT_PRESERVED")
    digest=lambda items:hashlib.sha256("|".join(items).encode("ascii")).hexdigest()
    source={
        "SourceRunId":KEY,
        "ProtocolSha256":digest([v1["protocolSha256"],v2["protocolSha256"]]),
        "CiphertextSha256":digest([sha1,sha2]),
        "Streams":streams
    }
    OUT.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory(prefix="mde1-native-protected-") as temp:
        p=Path(temp)/"both-originals-native-private.json"
        p.write_text(json.dumps(source,separators=(",",":")))
        result=OUT/"mde1-all12-direction-vs-event.native.json"
        job=subprocess.run(["dotnet","run","--no-build","--project",
            "src/Mxm.Replay","-c","Release","--",
            str(p),str(result),"--mde1-cumulative-all12-direction-vs-event"],
            capture_output=True,text=True,timeout=2400)
        need(job.returncode==0,"MDE1_NATIVE_CSHARP_CORE_FAILED")
        report=json.loads(result.read_text())
        need(report["Protocol"]=="MDE1_CUMULATIVE_ALL12_EXPOSED_M15_SIGN_VS_TOUCH_V1"
             and report["SourceRunId"]==KEY
             and report["FullSourceBarCount"]==279491
             and report["CausalSourceSupportedSymbols"]==12
             and len(report["Reports"])==12
             and report["OrdersSubmitted"]==0
             and report["CloudActivated"] is False
             and report["EconomicQualification"] is False
             and report["FundedNetEur"] is None
             and report["AdversarialNetEur"] is None,
             "MDE1_NATIVE_PUBLIC_REPORT_NOT_BOUND")
        (OUT/"mde1-existing-original-jpn225-contracts.public.json").write_text(
            json.dumps({
                "class":"EXISTING_GENUINE_ORIGINAL_PEPPERSTONE_CONTRACT_READBACK",
                "sourceXmh2":jpn1,"sourceHxc1":jpn2,
                "exactSymbolIdentityUnchanged":True,
                "historicalOrCurrentMarginEur":None,
                "historicalBidAskOrTradeNetEur":None,
                "cashAndOrderEffect":0
            },sort_keys=True,indent=2)+"\n")
        (OUT/"mde1-original-dual-source-custody.public.json").write_text(
            json.dumps({
                "schema":"MDE1_EXISTING_TWO_ORIGINAL_SOURCES_RECONSTRUCTED_V1",
                "originalXmh2RunId":XMH_RUN,
                "originalHxc1RunId":HXC_RUN,
                "originalXmh2CipherSha256":sha1,
                "originalHxc1CipherSha256":sha2,
                "sourceProtocolHashes":[v1["protocolSha256"],v2["protocolSha256"]],
                "originalRebuiltRawBrokerRequests":3088,
                "existingAuthenticTotalM15":279491,
                "originalSymbolCounts":count_by_market,
                "originalNativeCSharpJsonSha256":hashlib.sha256(result.read_bytes()).hexdigest(),
                "jpn225ExactOriginalContractReadback":True,
                "newBrokerRequests":0,
                "closedOriginalScorersRelaunched":0,
                "cashNetEur":None,"economicQualification":False,
                "brokerOrders":0,"cloudActivated":False
            },sort_keys=True,indent=2)+"\n")
    print("MDE1_ORIGINAL_TWO_SOURCE_REUSE_CSHARP_ALL12_JPN225_CONTRACT_NO_NET",flush=True)


if __name__=="__main__":
    try:execute()
    except Exception:
        print("MDE1_GUARDED_SOURCE_OR_NATIVE_FAILED_PRIVATE_DETAILS_WITHHELD",flush=True)
        raise SystemExit(1)
