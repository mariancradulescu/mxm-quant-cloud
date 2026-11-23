"""One V3.2 integrated source-only handoff. No predictions or financial simulation in Python.

Decrypts existing authenticated originals only in installed protected GitHub custody.
Temporary full-price tape MUST remain private; only native C# aggregates are public.
"""
import base64
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from .mde1_cumulative_original_native import _one_original, HXC_RUN, XMH_RUN
from .multiscale_conditional_research import recover as old_recover
from .p05_source_economic_gate import _load_sealed, _roster, _bars_from_original, RUN as P05_RUN
from .ctrader_proto import OpenApiMessages_pb2 as m
from .decode import decode_side

DURATION={"M1":60000,"M5":300000,"M15":900000,"M30":1800000,
          "H1":3600000,"H4":14400000,"D1":86400000}
END=1795392000000
SOURCE_RUNS=["41724643418","41735441128",XMH_RUN,HXC_RUN,P05_RUN]

def need(ok,code):
    if not ok:raise ValueError("V32_SOURCE_"+code)

def get(c,n):
    if isinstance(c,dict):return c.get(n)
    return getattr(c,n) if c.HasField(n) else None

def term(symbol,row,quote,margin,spread,stamp,assets=None):
    c=row.get("contract",row)
    def units(name):
        x=get(c,name)
        return str(x/100) if x is not None else None
    feeasset=get(c,"minCommissionAsset")
    if isinstance(feeasset,int):feeasset=(assets or {}).get(feeasset)
    return dict(Symbol=symbol,QuoteAsset=quote,MinimumUnits=units("minVolume"),
        StepUnits=units("stepVolume"),MaximumUnits=units("maxVolume"),
        LotUnits=units("lotSize"),CommissionType=get(c,"commissionType"),
        PreciseRateWire=get(c,"preciseTradingCommissionRate"),
        MinimumCommissionType=get(c,"minCommissionType"),
        PreciseMinimumWire=get(c,"preciseMinCommission"),
        MinimumCommissionAsset=feeasset,PnlConversionFeeBps=get(c,"pnlConversionFeeRate"),
        SwapCalculationType=get(c,"swapCalculationType"),LongSwap=get(c,"swapLong"),
        ShortSwap=get(c,"swapShort"),PipPosition=get(c,"pipPosition"),
        SwapPeriodHours=get(c,"swapPeriod"),SwapTimeUtcMinute=get(c,"swapTime"),
        TripleSwapWeekday=get(c,"swapRollover3Days"),
        MarginMinimumEur=str(margin) if margin is not None else None,
        SpreadBps=str(spread) if spread is not None else None,
        ObservedAtUtcMs=stamp,HistoricallyCertified=False)

def spread_samples(bundle):
    # Actual original fixed-clock tick sides; price-only data do not create spread samples.
    rows=defaultdict(list)
    for stamp,group in bundle.get("costIndices",{}).items():
        stamp=int(stamp)
        for symbol,idx in group.items():
            sides=[]
            for i in idx:
                r=m.ProtoOAGetTickDataRes()
                r.ParseFromString(base64.b64decode(bundle["raw"][i]["protobuf"],validate=True))
                sides.append(decode_side(r.tickData,stamp-2000,stamp+58000)
                             if r.HasField("hasMore") and not r.hasMore else [])
            if len(sides)!=2:continue
            bids,asks=sides
            latest=None;j=0
            for at,ask in asks:
                while j<len(bids) and bids[j][0]<=at:
                    latest=bids[j];j+=1
                if latest and at-latest[0]<=2000 and ask>=latest[1]>0:
                    rows[symbol].append(20000*(ask-latest[1])/(ask+latest[1]))
    return {s:sorted(v)[int(.9*(len(v)-1))] for s,v in rows.items() if len(v)>=3}

def execute(destination):
    key=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(key.strip()),"PRIVATE_CUSTODY_MISSING")
    protocol_sha=hashlib.sha256(
        Path("research/V32_UNIFIED_ECONOMIC_PROTOCOL_20261123.md").read_bytes()).hexdigest()
    bars=defaultdict(lambda:defaultdict(dict))
    contracts={}
    proof=[]
    duplicated=defaultdict(int)
    excluded=defaultdict(int)

    def add(symbol,tf,items):
        need(tf in DURATION,"FRAME_UNRECOGNIZED")
        for x in items:
            at=int(x[0])
            if at+DURATION[tf]>END:
                excluded[tf]+=1;continue
            data=(at,int(x[2]),int(x[3]),int(x[4]),int(x[5]),int(x[6]))
            need(data[3]>0 and data[3]<=min(data[1],data[4])<=max(data[1],data[4])<=data[2],
                 "RAW_OHLC_GEOMETRY")
            old=bars[symbol][tf].get(at)
            if old is not None:
                need(old==data,"OVERLAPPING_RAW_SOURCE_CONFLICT")
                duplicated[tf]+=1
            else:bars[symbol][tf][at]=data

    for source in json.loads(Path("research/hrc1_protocol.json").read_text())["source"]:
        b,raw,audit=old_recover(Path(source["folder"]),source["run"],source["hash"],
                                source["schema"],source["protocol"])
        need(audit["rawAccountAndBarsReconstructed"],"ANNUAL_ORIGINAL_PROOF")
        proof.append(dict(sourceRun=str(source["run"]),originalRows=sum(map(len,b["bars"].values()))))
        samples=spread_samples(b)
        for sym,items in b["bars"].items():
            add(sym,"M5",items)
            meta=b["symbols"][sym]
            contracts[sym]=term(sym,meta,meta["quoteAsset"],
                meta["currentMinMarginEur"],samples.get(sym),1793577600000)

    for run in (XMH_RUN,HXC_RUN):
        m15,bundle,readback,sha=_one_original(run,key)
        need(readback["rawRequestsRebuilt"]>0,"M15_ORIGINAL_PROOF")
        proof.append(dict(sourceRun=run,ciphertextSha256=sha))
        for sym,items in m15.items():add(sym,"M15",items)
        if run==HXC_RUN:
            for tag,items in bundle["bars"].items():
                sym,tf=tag.split("/")
                if tf in ("M1","H1"):add(sym,tf,items)

    p=json.loads(Path("p05-public/receipt.json").read_text())
    need(str(p["runId"])==P05_RUN and len(p["sources"])==76,"P05_RUN_BINDING")
    sealed=Path("p05-sealed")
    roster=_load_sealed(next(e for e in p["sources"] if e["kind"]=="ROSTER"),sealed,key)
    names=_roster(roster);assets={};lights={}
    for entry in roster:
        if entry.get("resType")=="ProtoOAAssetListRes":
            res=m.ProtoOAAssetListRes()
            res.ParseFromString(base64.b64decode(entry["res"],validate=True))
            assets={int(a.assetId):a.name for a in res.asset}
        if entry.get("resType")=="ProtoOASymbolsListRes":
            res=m.ProtoOASymbolsListRes()
            res.ParseFromString(base64.b64decode(entry["res"],validate=True))
            lights={int(s.symbolId):s for s in res.symbol}
    need(bool(assets) and bool(lights),"P05_ASSET_ROSTER_INCOMPLETE")
    # The P05 market shard contains a deliberately REDUCED public-safe
    # contract snapshot; the original separately encrypted CONTRACTS shards
    # retain minCommissionAsset and the complete tariff. Reconcile exactly
    # those original protobuf fields before creating native EUR cost inputs.
    full_contracts={}
    for shard in p["sources"]:
        if shard["kind"]!="CONTRACTS":continue
        original=_load_sealed(shard,sealed,key)
        for item in original:
            if item.get("resType")!="ProtoOASymbolByIdRes":continue
            detail=m.ProtoOASymbolByIdRes()
            detail.ParseFromString(base64.b64decode(item["res"],validate=True))
            need(detail.IsInitialized(),"P05_CONTRACT_PROTO")
            for c in detail.symbol:
                sid=int(c.symbolId)
                need(sid in lights,"P05_CONTRACT_NOT_IN_ROSTER")
                if sid in full_contracts:
                    need(c==full_contracts[sid],"P05_CONTRACT_CONFLICT")
                full_contracts[sid]=c
    need(len(full_contracts)>=48,"P05_FULL_CONTRACT_RECOVERY_INCOMPLETE")
    for shard in p["sources"]:
        packet=_load_sealed(shard,sealed,key)
        if shard["kind"]!="MARKET":continue
        need(packet and packet[0].get("contract") is not None,"P05_CONTRACT")
        sid,series=_bars_from_original(packet[1:])
        need(sid in names and sid in lights,"P05_MARKET_ID_NOT_ROSTER")
        sym=names[sid];pub=p["marketCoverage"][sym]
        quote=assets.get(lights[sid].quoteAssetId)
        need(bool(quote),"P05_QUOTE_ASSET_MISSING")
        samples=[x["medianSpreadBps"] for x in pub["bidAsk"].values()
                 if x["medianSpreadBps"] is not None and x["medianSpreadBps"]>0]
        need(sid in full_contracts,"P05_SELECTED_ORIGINAL_CONTRACT_MISSING")
        contracts[sym]=term(sym,full_contracts[sid],quote,
            pub["currentMinMarginEur"],max(samples) if samples else None,END,assets)
        for tf,values in series.items():
            need(len(values)==pub["timeframes"][tf]["bars"],"P05_ORIGINAL_BAR_COUNT")
            add(sym,tf,values.values())
    proof.append(dict(sourceRun=P05_RUN,originalShards=76))
    need(len(bars)>=48,"BROAD_SOURCE_UNIVERSE_MISSING")

    markets=[]
    for symbol in sorted(bars):
        marketbars={}
        for tf,vals in sorted(bars[symbol].items()):
            marketbars[tf]=[dict(OpenAt=t,Open=str(o/100000),High=str(h/100000),
                 Low=str(l/100000),Close=str(c/100000),TickVolume=v)
                 for _,(t,o,h,l,c,v) in sorted(vals.items())]
        markets.append(dict(Symbol=symbol,Terms=contracts.get(symbol),Bars=marketbars))
    destination.write_text(json.dumps(dict(SourceRuns=SOURCE_RUNS,
        ProtocolSha256=protocol_sha,PriceNormalization="ORIGINAL_PROTOWIRE_1E5_NO_SYNTHETIC_BAR",
        DevelopmentOnly=True,Markets=markets),separators=(",",":")))
    return dict(SourceRuns=SOURCE_RUNS,SourceProof=proof,ProtocolSha256=protocol_sha,
        Markets=len(markets),Coverage={s:{tf:len(z) for tf,z in f.items()}
            for s,f in sorted(bars.items())},IdenticalOverlaps=dict(duplicated),
        OmittedUnclosedBars=dict(excluded),BrokerRequests=0,Orders=0,CloudActivated=False)
