"""Prospective funding source observations only; never constructs a funding offer.

Reuse the frozen original account binding, socket allowlist and existing custody.
A point observation is NOT an effective interval or a debit ceiling.
"""
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport
from .guard import require_read_only_request
from .decode import need
from .custody import seal_new
from .custody_new import checked_public

SYMBOLS = {"NAS100": 126, "US500": 127}
SWAP_FIELDS = ("swapCalculationType", "swapLong", "swapShort", "swapPeriod",
               "swapTime", "swapRollover3Days", "chargeSwapAtWeekends",
               "skipSWAPPeriods", "scheduleTimeZone")
MARKER = "OWNER_FUNDING_PROVENANCE_POINT_OBSERVATION_20261124"


def observation(contract, expected_id, sent_at, received_at):
    need(contract.symbolId == expected_id and 0 < sent_at <= received_at,
         "FUNDING_OBSERVATION_ID_OR_CLOCK")
    fields = {k: getattr(contract, k) if contract.HasField(k) else None
              for k in SWAP_FIELDS}
    return dict(symbolId=expected_id, requestAt=sent_at, availableAt=received_at,
                observedFields=fields, effectiveFrom=None, effectiveThrough=None,
                exactSignedEur=None, maximumDebitEur=None,
                historicalContinuityCertified=False)


def collect(t, account, clock):
    packets = []
    def query(q, cls):
        require_read_only_request(q)
        sent = clock()
        r = t.request(q)
        received = clock()
        need(type(r) is cls and r.IsInitialized() and
             r.ctidTraderAccountId == account and 0 < sent <= received,
             "FUNDING_OBSERVATION_RESPONSE_BINDING")
        enc = lambda x: base64.b64encode(x.SerializeToString()).decode("ascii")
        packets.append(dict(reqType=type(q).__name__, req=enc(q),
                            resType=type(r).__name__, res=enc(r),
                            requestAt=sent, availableAt=received))
        return r, sent, received
    trader, _, _ = query(m.ProtoOATraderReq(ctidTraderAccountId=account),
                         m.ProtoOATraderRes)
    assets, _, _ = query(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                         m.ProtoOAAssetListRes)
    listing, _, _ = query(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                          includeArchivedSymbols=False), m.ProtoOASymbolsListRes)
    need(trader.trader.HasField("brokerName") and
         "pepperstone" in trader.trader.brokerName.casefold() and
         {a.assetId:a.name for a in assets.asset}.get(trader.trader.depositAssetId) == "EUR",
         "FUNDING_OBSERVATION_BROKER_OR_CURRENCY")
    result = {}
    for name, sid in sorted(SYMBOLS.items()):
        matches = [s for s in listing.symbol if s.symbolName == name]
        need(len(matches) == 1 and matches[0].symbolId == sid,
             "FUNDING_OBSERVATION_SYMBOL_ROSTER")
        r, sent, received = query(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                                  symbolId=[sid]), m.ProtoOASymbolByIdRes)
        need(len(r.symbol) == 1, "FUNDING_OBSERVATION_SYMBOL_COUNT")
        result[name] = observation(r.symbol[0], sid, sent, received)
    return packets, result


def main():
    # A distinct source-only execution must explicitly authorize this entrypoint.
    need(os.environ.get("GITHUB_EVENT_NAME") == "push" and
         os.environ.get("GITHUB_REF") == "refs/heads/main" and
         os.environ.get("GITHUB_RUN_ATTEMPT") == "1" and
         Path("ops/funding-provenance-point-observation-once.txt").is_file() and
         Path("ops/funding-provenance-point-observation-once.txt").read_text() == MARKER+"\n",
         "FUNDING_OBSERVATION_NOT_AUTHORIZED")
    rid = os.environ.get("GITHUB_RUN_ID", "")
    recipient = checked_public(Path("new-source-recipient"), rid)
    t = P05ReadOnlyTransport(response_timeout=30)
    try:
        account = authenticate(t)
        packets, observed = collect(t, account, lambda: time.time_ns() // 1000000)
        raw = json.dumps(dict(runId=rid, source="Pepperstone-cTrader-OpenAPI",
                              packets=packets, observations=observed),
                         sort_keys=True, separators=(",", ":")).encode()
        cipher = seal_new(raw, recipient, rid)
        dest = Path("funding-point-source"); dest.mkdir(exist_ok=False)
        (dest/"original.sealed").write_bytes(cipher)
        # No account ID, raw packet or credentials in public receipt.
        (dest/"receipt.json").write_text(json.dumps(dict(
            runId=rid, source="Pepperstone-cTrader-OpenAPI",
            originalSha256=hashlib.sha256(raw).hexdigest(),
            ciphertextSha256=hashlib.sha256(cipher).hexdigest(),
            observations=observed, ordersSubmitted=0, cloudActivated=False,
            economicEvaluations=0, evidenceClass="POINT_OBSERVATION_ONLY",
            usableFundingOffers=0), sort_keys=True, indent=2)+"\n")
    finally:
        t.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FUNDING_POINT_OBSERVATION_FAILED_DETAIL_WITHHELD", flush=True)
        sys.exit(1)
