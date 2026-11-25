"""Build independent native EUR inputs from verified archived packets and executable quote windows."""
import argparse
from collections import defaultdict
import gzip
import json
import os
from pathlib import Path

from . import closed_market_bar_source as supplemental
from . import closed_market_context_readback as context
from . import integrated_market_readback as marks
from . import owner_eer1_readback as readback
from . import owner_eer1_source as eer
from . import owner_eer1_recovery as recovery
from . import owner_history_continuation as older
from . import owner_official_eur_source as official
from . import owner_source_history_use as history
from . import source_history_universe as src
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .custody import unseal_new
from .decode import decode_side, need
from .official_symbol_calendar import build_clock_grid


REGISTRY = Path("research/eur_authentic_expansion_1.json")
ADAPTIVE = Path("research/eur_adaptive_calibration_1.json")
FULL_SESSION = Path("integrated-source-public/source.json")


def dated_market(name, market, terms, info, account, margin, start, end, source_run):
    contract = dict(terms, ObservedAtUtcMs=start-1, OriginalBrokerAuthenticated=True)
    grid = build_clock_grid(info["fields"], start, end+eer.DAY*7)
    needed = dict(Market=dict(market, Contract=contract, Margin=margin, M5=market.get("M5", []),
                             M15=market.get("M15", []), H1=market.get("H1", [])),
                  TermsAcquiredAt=terms["ObservedAtUtcMs"], ScheduledClocks=grid["openClocks"],
                  AmbiguousCalendarClocks=grid["ambiguousClocks"], CalendarStatus=grid["status"])
    needed["Market"]["DatedDevelopment"] = dict(
        Contract=contract, Margin=margin, ShortAllowed=info["shortAllowed"],
        TradingMode=info["tradingMode"], AccountSwapFree=account["accountSwapFree"],
        AccountType=account["accountType"], MoneyDigits=account["moneyDigits"], PriceDigits=info["priceDigits"],
        Digest=info["digest"], SourceRun=str(source_run))
    need(bool(needed["Market"]["Name"]==name), "EUR_ARCHIVE_MARKET_NAME")
    return needed


def read_earlier_packets(registered, key):
    values = defaultdict(lambda: defaultdict(dict))
    ticks = defaultdict(lambda: defaultdict(list))
    coverage = defaultdict(lambda: defaultdict(list))
    conflicting = set()
    acquired = 0
    for archive in registered["Earlier"]["Archives"]:
        root = Path(archive["Folder"])
        receipt = json.loads((root/"receipt.json").read_bytes())
        run = str(archive["Run"])
        cipher = (root/"packets.sealed").read_bytes()
        need(str(receipt["runId"])==run and receipt["ciphertextSha256"]==src.digest(cipher),
             "EUR_EARLIER_CIPHER")
        raw = unseal_new(cipher,key,run)
        need(src.digest(raw)==receipt["plaintextSha256"],"EUR_EARLIER_PLAINTEXT")
        payload=json.loads(raw)
        need(payload["report"]["runId"]==run and len(payload["packets"])==receipt["requests"] and
             receipt["orders"]==0 and not receipt["cloudActivated"],"EUR_EARLIER_PACKET_COUNT")
        for p in payload["packets"]:
            q=src.decode(p["reqType"],p["req"])
            need(src.original_account(q.ctidTraderAccountId),"EUR_EARLIER_ORIGINAL_ACCOUNT")
            if not isinstance(q,(m.ProtoOAGetTrendbarsReq,m.ProtoOAGetTickDataReq)) or q.symbolId not in registered["Earlier"]["SymbolIds"]:
                continue
            if not p["res"]:
                continue
            r=src.decode(p["resType"],p["res"])
            at=p["availableAt"]
            acquired=max(acquired,at)
            if isinstance(q,m.ProtoOAGetTrendbarsReq) and src.matching(r,m.ProtoOAGetTrendbarsRes,q.ctidTraderAccountId) and not r.hasMore:
                period=e.ProtoOATrendbarPeriod.Name(q.period)
                _,accepted=history.inspect_bars(q,r,at,closed_through=q.toTimestamp+1)
                for bar in accepted:
                    stamp=bar[0]
                    identity=(q.symbolId,period,stamp)
                    cell=values[q.symbolId][period]
                    if identity in conflicting:
                        continue
                    if stamp in cell and bar!=cell[stamp]:
                        cell.pop(stamp)
                        conflicting.add(identity)
                    else:
                        cell[stamp]=bar
            if isinstance(q,m.ProtoOAGetTickDataReq) and src.matching(r,m.ProtoOAGetTickDataRes,q.ctidTraderAccountId) and r.HasField("hasMore") and not r.hasMore:
                ticks[q.symbolId][q.type].extend(decode_side(r.tickData,q.fromTimestamp,q.toTimestamp))
                coverage[q.symbolId][q.type].append((q.fromTimestamp,q.toTimestamp))
    return values,ticks,coverage,len(conflicting),acquired


def earlier(registered,key,work):
    receipt=json.loads((eer.OUT/"receipt.json").read_bytes())
    package=eer.unpack(eer.OUT,receipt["metadata"],key,recovery.ORIGINAL_RUN)
    need(package["runId"]==recovery.ORIGINAL_RUN,"EUR_EARLIER_TERMS_SOURCE")
    account=src.decode(package["packets"][0]["reqType"],package["packets"][0]["req"]).ctidTraderAccountId
    meta=eer.metadata_read(package["packets"],receipt["selected"],account)
    names=older.TEMPORAL_SYMBOLS
    scope=registered["Earlier"]
    need(sorted(meta["roster"][n]["id"] for n in names)==sorted(scope["SymbolIds"]),"EUR_EARLIER_TERMS_IDENTITY")
    values,ticks,coverage,conflicts,acquired=read_earlier_packets(registered,key)
    start,end=scope["InitialFitFrom"],scope["TestBoundaries"][-1]
    tape_dir=work/"verified-protection"
    tape_dir.mkdir(mode=0o700)
    sink=readback.protection_tick_sink(tape_dir,"eer1")
    markets=[]; tape=[]; public={}
    for name in names:
        symbol=meta["roster"][name]
        sid=symbol["id"]
        terms=meta["terms"][name]
        info=meta["info"][name]
        def bars(period):
            return marks.normalized_bars([v for _,v in sorted(values[sid][period].items())])
        market=dict(Name=name,Class=symbol["assetClass"],OfficialAssetClass=symbol["assetClass"],
            Contract=terms,Margin=meta["margin"][name],TickSize=str(10**(-info["priceDigits"])),Quotes=[],
            ShortAllowed=info["shortAllowed"],TradingMode=info["tradingMode"],CostTermsComplete=True,
            EnabledAtCapture=symbol["enabled"],M5=bars("M5"),M15=bars("M15"),H1=bars("H1"),
            AdditionalTimeframes={tf:dict(Source="VERIFIED_ARCHIVED_OFFICIAL_BARS",Bars=bars(tf))
                                  for tf in ("M1","M30","H4","D1")})
        markets.append(dated_market(name,market,terms,info,meta,meta["margin"][name],start,end,recovery.ORIGINAL_RUN))
        days=defaultdict(lambda: defaultdict(list))
        for side in (e.BID,e.ASK):
            pairs=sorted({tuple(row) for row in ticks[sid][side]})
            for pair in pairs:
                days[pair[0]//eer.DAY*eer.DAY][side].append(pair)
            sink(name,side,pairs,coverage[sid][side])
        quotes=[]
        for day,sides in sorted(days.items()):
            combined={side:[(a,b,"VERIFIED_COMPLETE_PAGE",0,0) for a,b in coverage[sid][side]] for side in (e.BID,e.ASK)}
            for mark in marks.minute_marks(day,sides[e.BID],sides[e.ASK],interval=eer.STEP):
                at=mark["At"]
                if start<=at<end and all(eer.covered(combined[side],at-30_000,at) for side in combined):
                    quotes.append(mark)
        tape.append(dict(Name=name,Quotes=quotes,FundingQuotes=[]))
        public[name]=dict(M5=len(market["M5"]),M15=len(market["M15"]),H1=len(market["H1"]),MonetaryMarks=len(quotes),
                          QuoteSampleDays=len(days),VerifiedQuotePages=sum(map(len,coverage[sid].values())))
    proof=dict(OlderArchives=scope["Archives"],CurrentTermsMetadata=receipt["metadata"],Mode="EARLIER_SAMPLED_TICKS",
        TermsBasis="AUTHENTIC_CURRENT_CONTRACT_SCENARIO_NO_HISTORICAL_TARIFF_CONTINUITY",
        coverage=public,ConflictingBarRows=conflicts)
    source=dict(Start=start,FitEnd=scope["TestBoundaries"][0],End=end,EngineRevision=recovery.ORIGINAL_HEAD,
        SourceAcquiredAt=max(acquired,*meta["actual"].values()),Markets=markets,Tapes=tape,Routes=meta["routes"])
    return source,proof


def breadth(registered,key,work):
    payload=json.loads((work/"source.json").read_bytes())
    scope=registered["Breadth"]
    receipt_data=FULL_SESSION.read_bytes()
    receipt=json.loads(receipt_data)
    need(src.digest(receipt_data)==context.INTEGRATED_RECEIPT,"EUR_BREADTH_ORIGINAL_RECEIPT")
    existing={v["Market"]["Name"] for v in payload["Markets"]}
    names=[x for x in scope["ArchivedAliases"] if x in receipt["Markets"] and x not in existing]
    need(len(names)==1 and len(existing)==scope["BaseInstruments"],"EUR_BREADTH_ARCHIVED_ALIAS")
    name=names[0]
    shard=next(v for v in receipt["Shards"] if v["File"]=="account-contracts.enc")
    cipher=(marks.CIPHER_DIR/shard["File"]).read_bytes()
    need(src.digest(cipher)==shard["CipherSha256"],"EUR_BREADTH_TERMS_CIPHER")
    plain=unseal_new(cipher,key,context.INTEGRATED_RUN)
    need(src.digest(plain)==shard["CompressedPlainSha256"],"EUR_BREADTH_TERMS_PLAIN")
    raw=[marks.unpack(v) for v in json.loads(gzip.decompress(plain))["Identity"]]
    trader=raw[0][1].trader
    account=raw[0][0].ctidTraderAccountId
    need(src.original_account(account),"EUR_BREADTH_TERMS_ACCOUNT")
    roster=raw[2][1]
    selected=next(s for s in roster.symbol if s.symbolName==name)
    detail=next(r.symbol[0] for q,r in raw if isinstance(r,m.ProtoOASymbolByIdRes) and
                q.ctidTraderAccountId==account and r.symbol[0].symbolId==selected.symbolId)
    observed=receipt.get("ContractObservedAt") or payload["SourceAcquiredAt"]
    contract,fields,_,_=official.terms_input(detail,name,"USD",observed)
    # The full-session readback verifies the quote asset, exact margin levels,
    # dates and every raw quote page against original custody.
    charges=eer.charge_clocks({name:contract})
    clocks=[day+minute*60_000 for day in range(eer.START,marks.END,eer.DAY) for minute in charges]
    rows=marks.readback(receipt,key,interval=30_000,include_markets=names,rollover_clocks=clocks)
    tape_prefix=src.digest(name.encode())+"-"
    need(all((work/"verified-protection"/(tape_prefix+side+"-full-session.ticks")).is_file()
             for side in ("bid","ask")),"EUR_BREADTH_PROTECTION_TAPE")
    market=rows[0]
    need(market["Contract"]["QuoteAsset"]=="USD","EUR_BREADTH_CONVERSION_ROUTE")
    additional,supp_receipt=supplemental.readback(key,"44733062339",native_boundaries=True)
    market["AdditionalTimeframes"]={tf:dict(Source="AUTHENTIC_ARCHIVED_SUPPLEMENT",Bars=marks.normalized_bars(
        additional.get((name,tf),[]))) for tf in ("M1","M30","H4","D1")}
    market["OfficialAssetClass"]=market["Class"]
    info=dict(fields=fields,priceDigits=detail.digits,shortAllowed=detail.enableShortSelling,
              tradingMode=detail.tradingMode,digest=src.digest(detail.SerializeToString()))
    money=dict(accountSwapFree=src.field(trader,"swapFree"),accountType=src.field(trader,"accountType"),
               moneyDigits=src.field(trader,"moneyDigits"))
    payload["Markets"].append(dated_market(name,market,market["Contract"],info,money,market["Margin"],
                                          payload["Start"],payload["End"],context.INTEGRATED_RUN))
    quotes=[q for q in market["Quotes"] if q["At"]%eer.STEP==15_000]
    need(bool(quotes),"EUR_BREADTH_NO_ARCHIVED_QUOTE_MARKS")
    payload["Tapes"].append(dict(Name=name,Quotes=quotes,FundingQuotes=market["RolloverQuotes"]))
    proof=dict(OriginalInputManifest=payload["EvidenceManifestSha256"],FullSessionReceipt=context.INTEGRATED_RECEIPT,
               SupplementCipher=supp_receipt["CipherSha256"],AddedMarket=name,AddedMonetaryMarks=len(quotes),
               FirstAddedMark=quotes[0]["At"],LastAddedMark=quotes[-1]["At"],PreviousMarketCount=len(existing),MarketCount=len(payload["Markets"]),Mode="FULL_SESSION_SCOPE_EXTENSION")
    return payload,proof


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("lane",choices=("Earlier","Breadth"))
    parser.add_argument("work",type=Path)
    parser.add_argument("receipt",type=Path)
    args=parser.parse_args()
    plan_data=REGISTRY.read_bytes()
    registration=json.loads(plan_data)
    key=os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    if args.lane=="Earlier":
        args.work.mkdir(mode=0o700)
        source,proof=earlier(registration,key,args.work)
    else:
        source,proof=breadth(registration,key,args.work)
    source["ProtocolSha256"]=src.digest(plan_data)
    source["EvidenceManifestSha256"]=src.digest(src.canonical(proof))
    template=json.loads(ADAPTIVE.read_bytes())
    lane=registration[args.lane]
    trials=[t for t in template["Trials"] if t["Id"] in lane["Trials"]]
    if args.lane=="Earlier":
        trials.append(dict(Id="FINANCEABLE_PROBE",Policy="EUR_GENERAL_PROBE",Calibration="CLOSED_BAR_FAMILY_DIRECTION"))
    ids={t["Calibration"] for t in trials}
    plan=dict(Study=registration["Study"]+"_"+args.lane.upper(),Exposure=template["Exposure"],
        SourceProtocolSha256=source["ProtocolSha256"],EvidenceManifestSha256=source["EvidenceManifestSha256"],
        InitialFitFrom=lane["InitialFitFrom"],TestBoundaries=lane["TestBoundaries"],Stresses=template["Stresses"],
        Calibrations=[c for c in template["Calibrations"] if c["Id"] in ids],Trials=trials,
        ArchivedSampledQuotes=args.lane=="Earlier")
    if args.lane=="Breadth":
        plan["StopWitness"]=template["StopWitness"]
    source_bytes=src.canonical(source)
    plan_bytes=src.canonical(plan)
    for path,data in ((args.work/"source.json",source_bytes),(args.work/"protocol.json",plan_bytes)):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(data)
    public=dict(Scope=args.lane,RegistrationSha256=source["ProtocolSha256"],
        EvidenceManifestSha256=source["EvidenceManifestSha256"],SourceSha256=src.digest(source_bytes),
        ProtocolSha256=src.digest(plan_bytes),Proof=proof,Orders=0,SourceBrokerRequests=0,CloudActivated=False)
    args.receipt.write_bytes(src.canonical(public))
    print("AUTHENTIC_EXPANSION_INPUT",args.lane,len(source["Markets"]),src.digest(source_bytes),flush=True)


if __name__=="__main__":
    main()
