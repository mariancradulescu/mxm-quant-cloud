"""GCR1 A2 independent protected custody readback: reuse ORIGINAL BDP1 bar source.

No original broker requests, OAuth credentials, orders or Cloud in this job.
BDP1 raw encrypted source and new GCR1 Copper/quote encrypted source are
authenticated separately, merged only by original exact timestamps, then
the composite is encrypted BEFORE any EUR outcome scoring.
"""
from __future__ import annotations
import base64
from collections import Counter
from datetime import datetime, date, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path

from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .custody import seal_new, unseal_new
from .custody_new import derive_recipient
from .guard import require_read_only_request
from .gcr1_macro_signal import scheduled_clocks
from .gcr1_eur_model import intents, evaluate
from .portfolio_discovery_source import audit as bdp_audit

BDP_RUN = "41724643418"
BDP_SHA = "e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370"
BDP_SOURCE = Path("bdp1-original-sealed/source.envelope.json")
GCR_SOURCE = Path("gcr1-a2-source/gcr1-original-protected.v2.enc")
GCR_PUBLIC = Path("gcr1-a2-public/gcr1-original-source-public.json")
COMPOSITE = Path("gcr1-a2-composite-source.v2.enc")
OUTPUT = Path("gcr1-original-public-eur.json")


def digest_equal(path, expected, name):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(name+"_ORIGINAL_CIPHER_OR_RECEIPT_DIGEST_MISMATCH")
    return raw


def verify_new_raw(blob):
    """Verify same ORIGINAL_ACCOUNT commitment on every saved read-only call."""
    account = None
    for item in blob["originalRawProtobuf"]:
        req_type = item["requestType"]
        res_type = item["responseType"]
        q = getattr(m, req_type)()
        ans = getattr(m, res_type)()
        q.ParseFromString(base64.b64decode(item["request"], validate=True))
        ans.ParseFromString(base64.b64decode(item["response"], validate=True))
        require_read_only_request(q)
        if not ans.IsInitialized() or not hasattr(ans, "ctidTraderAccountId"):
            raise ValueError("GCR1_NEW_SOURCE_UNAUTHENTICATED_REPLY")
        if account is None:
            account = int(ans.ctidTraderAccountId)
        if (int(ans.ctidTraderAccountId) != account or
                int(q.ctidTraderAccountId) != account):
            raise ValueError("GCR1_NEW_SOURCE_ACCOUNT_SPLIT")
    if account is None:
        raise ValueError("GCR1_MISSING_ORIGINAL_SOURCE")
    fingerprint=sha256(f"ctrader-account:{account}".encode()).hexdigest()
    if sha256(fingerprint.encode()).hexdigest() != HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT:
        raise ValueError("GCR1_ORIGINAL_ACCOUNT_FINGERPRINT_MISMATCH")
    if len(blob["originalRawProtobuf"]) != blob["authenticatedRequestsAfterAccountAuth"]:
        raise ValueError("GCR1_SOURCE_REQUEST_COUNT_MISMATCH")


def original_bdp_close_maps(old, tape):
    """Use only original Gold/AUD M5 close, never BDP1 predictor or outcomes."""
    expected = set(tape)
    maps = {key: {"XAUUSD": {}, "AUDUSD": {}} for key in expected}
    original_counts = {}
    for name in ("XAUUSD", "AUDUSD"):
        unique = set()
        for row in old["bars"][name]:
            if len(row) != 7:
                raise ValueError("GCR1_BDP1_ROW_SHAPE_INVALID")
            start, end, _open, _high, _low, close, _volume = map(int, row)
            if end - start != 300000 or start in unique or close <= 0:
                raise ValueError("GCR1_BDP1_BAR_DUPLICATE_OR_INVALID")
            unique.add(start)
            key = datetime.fromtimestamp(end/1000,timezone.utc).date().isoformat()
            if key in maps:
                other = maps[key][name]
                if str(end) in other and other[str(end)] != close:
                    raise ValueError("GCR1_BDP1_CONFLICTING_5M_CLOSE")
                other[str(end)] = close
        original_counts[name] = len(unique)
    return maps, original_counts


def readback():
    run = os.environ["GITHUB_RUN_ID"]
    private = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    if not private:
        raise ValueError("GCR1_INSTALLED_ORIGINAL_CUSTODY_KEY_MISSING")

    original_old_cipher=digest_equal(BDP_SOURCE, BDP_SHA, "BDP1")
    old_plain=unseal_new(original_old_cipher,private,BDP_RUN)
    old=json.loads(old_plain)
    old_protocol=json.loads(Path("research/portfolio_discovery_protocol.json").read_text())
    old_attestation=bdp_audit(old,old_protocol)
    if (old["schema"] != "mxm-bdp1-source-v1"
            or old.get("auditReceipt") != old_attestation
            or not old_attestation.get("originalAccountBindingRechecked")
            or not old.get("pilotPassed")):
        raise ValueError("GCR1_CANNOT_REUSE_UNAUDITED_BDP1_M5")

    original_source_receipt=json.loads(GCR_PUBLIC.read_text())
    if (original_source_receipt.get("originalRunId")!=int(run)
            or original_source_receipt.get("schema") !=
               "MXM_GCR1_A2_SOURCE_ONLY_NO_FINANCIAL_SCORING"
            or original_source_receipt.get("conditionalNetEur") is not None
            or not original_source_receipt.get("sourceEncryptedBeforeAllGCR1OutcomeScoring")):
        raise ValueError("GCR1_NEW_SOURCE_RECEIPT_NOT_SOURCE_ONLY")
    new_cipher=digest_equal(GCR_SOURCE,
                            original_source_receipt["originalCiphertextSha256"],
                            "GCR1")
    new_plain=unseal_new(new_cipher,private,run)
    if sha256(new_plain).hexdigest()!=original_source_receipt["originalPlaintextSha256"]:
        raise ValueError("GCR1_NEW_SOURCE_PLAINTEXT_DIGEST_MISMATCH")
    new=json.loads(new_plain)
    if (new.get("schema")!="MXM_GCR1_A2_ORIGINAL_COPPER_AND_QUOTES_SOURCE_ONLY"
            or new.get("originalRunId")!=run
            or not new.get("originalPepperstoneEurAccountVerified")
            or new.get("authenticatedRequestsAfterAccountAuth")>4600):
        raise ValueError("GCR1_NEW_READONLY_SOURCE_INVALID")
    verify_new_raw(new)
    tape=new["originalDecodedDayPanels"]
    if len(tape) != 260:
        raise ValueError("GCR1_NEW_SOURCE_FIXED_CALENDAR_CHANGED")
    old_maps, old_counts=original_bdp_close_maps(old,tape)
    all_clock=scheduled_clocks()
    for clock in all_clock:
        day=datetime.fromtimestamp(clock/1000,timezone.utc).date().isoformat()
        if day not in tape:
            raise ValueError("GCR1_MISSING_SCHEDULED_DAY")
        panel=tape[day]
        if list(panel["bars"])!=["Copper"]:
            raise ValueError("GCR1_A2_DUPLICATE_GOLD_OR_AUD_NEW_SOURCE")
        for name in ("XAUUSD","AUDUSD"):
            panel["bars"][name]=old_maps[day][name]
        panel.setdefault("intents",{})[str(clock)]=intents(panel["bars"],clock)
    if sum(len(p["intents"]) for p in tape.values()) != 780:
        raise ValueError("GCR1_ORIGINAL_INTENT_CALENDAR_MISMATCH")

    # Bind GCR1 original account current symbol terms to the GCR1 raw response
    current_b64=new["originalAsObservedCurrentContract"].get("targetCurrentContractBase64")
    target=None
    if current_b64:
        target=e.ProtoOASymbol()
        target.ParseFromString(base64.b64decode(current_b64,validate=True))
        if not target.IsInitialized() or target.symbolId<=0:
            raise ValueError("GCR1_CURRENT_AUDUSD_SYMBOL_NOT_ORIGINAL")
        observed=False
        for rec in new["originalRawProtobuf"]:
            if rec["responseType"]!="ProtoOASymbolByIdRes":
                continue
            x=m.ProtoOASymbolByIdRes()
            x.ParseFromString(base64.b64decode(rec["response"],validate=True))
            observed |= any(xi.SerializeToString()==target.SerializeToString() for xi in x.symbol)
        if not observed:
            raise ValueError("GCR1_CURRENT_CONTRACT_NOT_IN_ORIGINAL_SOURCE")
    margin=new["originalAsObservedCurrentContract"].get("targetMinimumMarginEur")
    min_margin=max(D(x) for x in margin.values()) if margin else None
    if new["originalAsObservedCurrentContract"].get("sourceStates"):
        if "CURRENCY_ROUTE_OR_MARKET_INELIGIBLE" in new["originalAsObservedCurrentContract"]["sourceStates"]:
            min_margin=None

    joint={
        "schema":"MXM_GCR1_A2_BDP1_REUSED_PLUS_GCR1_NEW_SOURCE_PRE_EUR",
        "originalReadOnlyBdp1SourceRun":int(BDP_RUN),
        "originalReadOnlyGcr1SourceRun":int(run),
        "bdp1OriginalSourceSha256":BDP_SHA,
        "gcr1NewOriginalSourceSha256":sha256(new_cipher).hexdigest(),
        "gcr1NewOriginalReadOnlyRequests":new["authenticatedRequestsAfterAccountAuth"],
        "bdp1OriginalM5Counts":old_counts,
        "gcr1OriginalCopperAndFixedTwoSidedFxPanels":tape,
        "allClocksFixedPreOutcome":True,
        "allClocksGloballyExposedDevelopment":True,
    }
    composite_bytes=json.dumps(joint,sort_keys=True,separators=(",",":"),
                              allow_nan=False).encode()
    public,_=derive_recipient(private)
    composite_cipher=seal_new(composite_bytes,public,run)
    COMPOSITE.write_bytes(composite_cipher)
    # Seal the merged SOURCE and immutable intents FIRST, before EUR finance.
    scored=evaluate(tape,target,min_margin)
    before=scored["first26Weeks"]
    after=scored["last26Weeks"]
    def superior(x):
        d=x["adverseMatchedNetEur"]
        return x["commonPricedClocks"]>0 and d["combined"]>0 and all(
            d["combined"]>d[p] for p in ("copperOnly","inverseGoldOnly",
              "audOwnMomentum","long","short","cash")
        )
    enough=scored["overall"]["commonPricedClocks"]==780
    verdict = (
        "DEVELOPMENT_ONLY_POSSIBLE_ADVERSE_INCREMENTAL_CANDIDATE" if
        enough and superior(before) and superior(after)
        else ("REJECT_EXACT_GCR1_NO_ROBUST_ADVERSE_INCREMENTAL_NET" if
              enough else "INCONCLUSIVE_FULL_CALENDAR_COVERAGE_CONDITIONAL_NET_DISCLOSED")
    )
    out={
        "schema":"MXM_GCR1_A2_BDP1_REUSED_ORIGINAL_READONLY_EUR_FINANCIAL",
        "originalGcr1RunId":int(run),
        "originalBdp1SourceRunId":int(BDP_RUN),
        "bdp1SourceOriginalCiphertextSha256":BDP_SHA,
        "gcr1NewSourceOriginalCiphertextSha256":sha256(new_cipher).hexdigest(),
        "gcr1CompositeEncryptedSourceSha256":sha256(composite_cipher).hexdigest(),
        "gcr1CompositePlaintextSha256":sha256(composite_bytes).hexdigest(),
        "initialProtocolSha256":sha256(Path(
            "research/GCR1_COPPER_GOLD_AUD_MACRO_DIFFUSION.md").read_bytes()).hexdigest(),
        "a1ProtocolSha256":sha256(Path(
            "research/GCR1_OWNER_PRESOURCE_ADDENDUM_A1.md").read_bytes()).hexdigest(),
        "a2ProtocolSha256":sha256(Path(
            "research/GCR1_OWNER_PRESOURCE_SOURCE_REUSE_A2.md").read_bytes()).hexdigest(),
        "originalSourceEncryptedBeforeAnyFinancialScoring":True,
        "independentlyVerifiedBDP1OriginalSource":True,
        "newAuthenticatedReadOnlyRequests":new["authenticatedRequestsAfterAccountAuth"],
        "reusedBDP1M5OriginalCounts":old_counts,
        "fixedCausalCalendarClocks":780,
        "results":scored,
        "verdict":verdict,
        "brokerActualFills":None,
        "historicalTrueTariffsCertified":False,
        "nativeFundedCommonPortfolioNetEur":None,
        "continuousFloatDD30Certified":False,
        "hard21Certified":False,
        "independentConfirmation":False,
        "ordersSubmitted":0,
        "cloudTradingActivated":False,
    }
    OUTPUT.write_text(json.dumps(out,indent=2,allow_nan=False)+"\n")
    print("GCR1_A2_ORIGINAL_CONDITIONAL_EUR",json.dumps({
      "newRequests":out["newAuthenticatedReadOnlyRequests"],
      "reusedM5":old_counts,
      "fullCalendar":780,
      "matchedClocks":scored["overall"]["commonPricedClocks"],
      "firstAdverse":before["adverseMatchedNetEur"],
      "lastAdverse":after["adverseMatchedNetEur"],
      "verdict":verdict,
    },sort_keys=True),flush=True)


if __name__=="__main__":
    readback()
