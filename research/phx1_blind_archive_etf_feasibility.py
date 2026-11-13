"""PHX1 read-only ORIGINAL broker RNE1 older-archive and new ETF source probe.

Contains ZERO return scoring, features, model fitting or candidate selection.
Capture exact raw protobuf in custody BEFORE public aggregate coverage.
"""
from __future__ import annotations
import base64
from datetime import date,datetime,time,timezone
from hashlib import sha256
import json,os
from pathlib import Path
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .custody_new import checked_public
from .custody import seal_new

NY=ZoneInfo("America/New_York")
ARCHIVE_DAYS=(date(2024,6,6),date(2024,11,7),
              date(2025,2,6),date(2025,4,3),
              date(2025,7,10),date(2025,10,23))
EXACT_NAMES=("US500","SPY.US","NAS100","QQQ.US")
MAX_CALLS=32
M5=300000


def stamp(day,hh,mm):
    return int(datetime.combine(day,time(hh,mm),NY).timestamp()*1000)


def source_availability(bars,begin,end):
    """No returns, no sides: only original completed M5 timestamp coverage."""
    times=set()
    for row in bars:
        if begin<=row[1]<=end:
            times.add(row[1])
    return {
        "originalClosedM5Bars":len(times),
        "consecutiveM5SlotsPresent":all(
            t in times for t in range(begin+M5,end+1,M5)),
        "clockSlotsExpected":(end-begin)//M5,
    }


def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    trans=StdlibCTraderTransport()
    count=0
    requests=[]
    statuses={}
    archives={}
    live={}
    day_count=0

    def request(q,klass,allow_no_bars=False):
        nonlocal count
        if count>=MAX_CALLS:raise RuntimeError("PHX1_READ_ONLY_CALL_CEILING")
        require_read_only_request(q)
        reply=trans.request(q)
        count+=1
        if (allow_no_bars and type(reply) is m.ProtoOAErrorRes and
            reply.errorCode=="NO_QUOTES" and
            reply.ctidTraderAccountId==account):
            result=None
        elif (type(reply) is klass and reply.IsInitialized() and
              reply.ctidTraderAccountId==account):
            result=reply
        else:
            raise RuntimeError("PHX1_BROKER_RESPONSE_IDENTITY_OR_TYPE_MISMATCH")
        requests.append({
            "requestType":type(q).__name__,
            "request":base64.b64encode(q.SerializeToString()).decode(),
            "responseType":type(reply).__name__,
            "response":base64.b64encode(reply.SerializeToString()).decode()})
        return result

    try:
        account=authenticate(trans)
        trader=request(m.ProtoOATraderReq(ctidTraderAccountId=account),
                       m.ProtoOATraderRes)
        asset=request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                      m.ProtoOAAssetListRes)
        currencies={x.assetId:x.name for x in asset.asset}
        if ("pepperstone" not in trader.trader.brokerName.casefold() or
            currencies.get(trader.trader.depositAssetId)!="EUR"):
            raise RuntimeError("PHX1_NOT_ORIGINAL_PEPPERSTONE_EUR")
        roster=request(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        visible={x.symbolName:x for x in roster.symbol if x.enabled}
        for symbol in ("NatGas",*EXACT_NAMES):
            item=visible.get(symbol)
            if item is None:
                statuses[symbol]={"presentCurrent":False,
                    "reason":"EXACT_NAME_NOT_ENABLED_OR_ABSENT"}
                continue
            detail=request(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[item.symbolId]),
                m.ProtoOASymbolByIdRes)
            if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=item.symbolId:
                raise RuntimeError("PHX1_DETAIL_ACCOUNT_SYMBOL_MISMATCH")
            contract=detail.symbol[0]
            status={"presentCurrent":True,
                "currentQuoteAsset":currencies.get(item.quoteAssetId),
                "currentTradingMode":int(contract.tradingMode),
                "currentMinimumVolumeWire":int(contract.minVolume),
                "currentStepVolumeWire":int(contract.stepVolume),
                "currentMinimumMarginBuyEur":None,
                "currentMinimumMarginSellEur":None,
                "currentMinCommissionCurrencyPresent":(
                    contract.HasField("minCommissionAsset") or
                    contract.HasField("minCommissionType")),
                "historicalContractAvailabilityCertified":False}
            if contract.minVolume>0:
                margin=request(m.ProtoOAExpectedMarginReq(
                    ctidTraderAccountId=account,symbolId=item.symbolId,
                    volume=[contract.minVolume]),m.ProtoOAExpectedMarginRes)
                if margin.HasField("moneyDigits") and len(margin.margin)==1 and (
                    margin.margin[0].volume==contract.minVolume):
                    status["currentMinimumMarginBuyEur"]=(
                        margin.margin[0].buyMargin/10**margin.moneyDigits)
                    status["currentMinimumMarginSellEur"]=(
                        margin.margin[0].sellMargin/10**margin.moneyDigits)
            statuses[symbol]=status
            live[symbol]=item.symbolId
        if "NatGas" in live:
            for day in ARCHIVE_DAYS:
                begin,end=stamp(day,9,25),stamp(day,10,55)
                resp=request(m.ProtoOAGetTrendbarsReq(
                    ctidTraderAccountId=account,symbolId=live["NatGas"],
                    period=e.M5,fromTimestamp=begin,toTimestamp=end),
                    m.ProtoOAGetTrendbarsRes,True)
                if resp is None:
                    archives[day.isoformat()]={"status":"NO_ORIGINAL_QUOTES"}
                elif resp.hasMore:
                    archives[day.isoformat()]={"status":"TRUNCATED_ORIGINAL_ARCHIVE"}
                elif resp.period!=e.M5 or (resp.HasField("symbolId") and
                    resp.symbolId!=live["NatGas"]):
                    raise RuntimeError("PHX1_ORIGINAL_M5_SOURCE_MISMATCH")
                else:
                    bars=decode_bars(resp.trendbar,begin-2*M5,end+2*M5,5)
                    count_=source_availability(bars,begin,end)
                    archives[day.isoformat()]={"status":"SOURCE_COVERAGE_ONLY",
                                               **count_}
                day_count+=1
    finally:
        trans.close()
    original=json.dumps({
        "schema":"MXM_PHX1_ORIGINAL_READ_ONLY_SOURCE_PRIVATE",
        "run":run,"originalBrokerAccountVerified":True,
        "originalRequestsAndResponses":requests,
        "diagnosticDates":[d.isoformat() for d in ARCHIVE_DAYS],
        "historicalBarsOutcomesNotScored":True,
        "privateRostersCurrentTerm":statuses,
        "requestCountAfterAuth":count
    },sort_keys=True,separators=(",",":")).encode()
    cipher=seal_new(original,recipient,run)
    Path("phx1-protected-original.v2.enc").write_bytes(cipher)
    report={
        "schema":"MXM_PHX1_ARCHIVE_AND_ETF_CURRENT_FEASIBILITY_ONLY",
        "protocolSha256":sha256(Path("research/PHX1_BLIND_ARCHIVE_AND_ETF_FEASIBILITY.md").read_bytes()).hexdigest(),
        "run":int(run),"authenticatedReadOnlyRequestsAfterAuth":count,
        "originalPepperstoneEurVerified":True,
        "sourceCipherSha256":sha256(cipher).hexdigest(),
        "sourcePlaintextSha256":sha256(original).hexdigest(),
        "oldNatGasM5Availability":archives,
        "originalAccountExactCurrentSymbols":statuses,
        "newQuoteOrReturnSignalsScored":0,
        "historicalIndependentConfirmation":False,
        "chronologicalPostDevelopmentConfirmation":False,
        "originalEconomicModelModified":False,
        "historicalEiaSurpriseProven":False,
        "newStudyFrozenButNotExecuted":True,
        "originalRawSourcePublished":False,
        "brokerOrdersSubmitted":0,
        "cloudTradingActivated":False,
        "oauthReauthorized":False,
        "disclosure":"Historical bar availability and current original account ETF contract snapshots ONLY. No prices, price directions, returns, forecasts, historical PnL or independent confirmation have been evaluated."
    }
    Path("phx1-original-public-availability.json").write_text(
        json.dumps(report,indent=2,allow_nan=False)+"\n")
    print("PHX1_SOURCE_ONLY_COVERAGE",
        json.dumps({"historicalWindows":day_count,
                    "requests":count,
                    "availableCurrent":{x:y["presentCurrent"] for x,y in statuses.items()},
                    "archiveBars":{x:y.get("originalClosedM5Bars")
                        for x,y in archives.items()}}),flush=True)


if __name__=="__main__":
    main()
