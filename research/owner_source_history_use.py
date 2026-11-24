"""Read and normalize existing source packets in protected custody."""
from collections import Counter
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from google.protobuf.unknown_fields import UnknownFieldSet

from . import source_history_universe as source
from .ctrader_proto import OpenApiMessages_pb2 as messages, OpenApiModelMessages_pb2 as models
from .custody import unseal_new
from .decode import decode_bars, need
from .guard import CaptureContractError
from .multiscale_conditional_research import recover


SOURCE_RUN = "45396314675"
CIPHER_SHA = "264701583af01404bab89284a6d7481c6aba6ebde4b2f7949664070c758e7f28"
PLAIN_SHA = "7eaca634d8f61c79a0e5b5d93769aa67079dfa161fba1b79d66e0e1839f617a3"
RECEIPT_SHA = "19f266e5d24af76df30ca32518039413a8851ce242221653dc1d7e0592ae38f3"


def verified_original(folder, key):
    encrypted = (folder / "original.sealed").read_bytes()
    receipt_bytes = (folder / "receipt.json").read_bytes()
    need(source.digest(encrypted) == CIPHER_SHA and source.digest(receipt_bytes) == RECEIPT_SHA,
         "SOURCE_USE_ARCHIVE_HASH")
    original = unseal_new(encrypted, key, SOURCE_RUN)
    need(source.digest(original) == PLAIN_SHA, "SOURCE_USE_PLAINTEXT_HASH")
    original = json.loads(original)
    receipt = json.loads(receipt_bytes)
    need(original["runId"] == SOURCE_RUN and original["report"]["sourceBindingVerified"]
         and receipt == dict(original["report"], originalSha256=PLAIN_SHA, ciphertextSha256=CIPHER_SHA)
         and source.packet_summary(original["packets"]) == receipt["requestJournal"]
         and receipt["unexpectedOrMissingResponses"] == 0, "SOURCE_USE_ORIGINAL_RECEIPT")
    return original["packets"], receipt


def inspect_bars(request, reply, available_at):
    """Keep exact, public-safe diagnostics and use only in-window closed rows."""
    duration = source.PERIODS[models.ProtoOATrendbarPeriod.Name(request.period)] * 60_000
    start, end = request.fromTimestamp, request.toTimestamp
    errors, omissions, offsets = Counter(), Counter(), Counter()
    seen, rows = set(), []
    if not source.matching(reply, messages.ProtoOAGetTrendbarsRes, request.ctidTraderAccountId):
        return dict(status="RESPONSE_UNBOUND", acceptedRows=0), []
    if reply.period != request.period or reply.HasField("symbolId") and reply.symbolId != request.symbolId:
        return dict(status="RESPONSE_PERIOD_OR_SYMBOL", acceptedRows=0), []
    for bar in reply.trendbar:
        stamp = bar.utcTimestampInMinutes * 60_000
        missing = [field for field in ("utcTimestampInMinutes", "low", "deltaOpen", "deltaHigh", "deltaClose", "volume")
                   if not bar.HasField(field)]
        if missing:
            errors["BAR_FIELDS_MISSING"] += 1
            omissions.update(missing)
            continue
        if stamp in seen:
            errors["BAR_DUPLICATE_OPEN"] += 1
            continue
        seen.add(stamp)
        if bar.HasField("period") and bar.period != request.period:
            errors["BAR_ROW_PERIOD_MISMATCH"] += 1
            continue
        offsets[str((stamp % duration) // 60_000)] += 1
        if not start <= stamp <= end:
            direction = "BEFORE" if stamp < start else "AFTER"
            if start - duration <= stamp <= end + duration:
                omissions["ADJACENT_" + direction] += 1
                continue
            errors["OUTSIDE_ONE_PERIOD_" + direction] += 1
            continue
        try:
            row = decode_bars((bar,), stamp, stamp, 0)[0]
        except CaptureContractError as problem:
            errors[str(problem)] += 1
            continue
        except (IndexError, TypeError, ValueError, OverflowError):
            errors["BAR_DECODE_EXCEPTION"] += 1
            continue
        if stamp + duration > min(end + 1, available_at):
            omissions["CLOSE_AFTER_CUTOFF"] += 1
            continue
        row[1] = stamp + duration
        rows.append(row)
    more = source.field(reply, "hasMore")
    if more is not False:
        errors["PAGINATION_HAS_MORE" if more else "PAGINATION_FLAG_ABSENT"] += 1
    if errors:
        status = "INCOMPLETE_OR_INVALID"
    elif rows:
        status = "CLOSED_ROWS_VERIFIED"
    elif reply.trendbar:
        status = "NO_CLOSED_ROWS_WITHIN_WINDOW"
    else:
        status = "EXPECTED_RESPONSE_WITH_EMPTY_SERIES"
    rows = sorted(rows) if not errors else []
    return dict(status=status, rawRows=len(reply.trendbar), acceptedRows=len(rows), hasMore=more,
                reasons=dict(errors), exclusions=dict(omissions), nominalOffsetMinutes=dict(offsets),
                historicalSessionsCertified=False), rows


def calculation_type(contract):
    field = contract.DESCRIPTOR.fields_by_name["swapCalculationType"]
    unknown = [f.data for f in UnknownFieldSet(contract) if f.field_number == field.number and f.wire_type == 0]
    if unknown:
        return "UNKNOWN_WIRE_ENUM", None, unknown
    if not contract.HasField(field.name):
        return "ABSENT_ON_WIRE", None, []
    value = contract.swapCalculationType
    return models.ProtoOASwapCalculationType.Name(value), value, []


def fields_of(message):
    result = {}
    for field, value in message.ListFields():
        if field.name == "description":
            continue
        if field.label == field.LABEL_REPEATED:
            result[field.name] = [fields_of(item) for item in value]
        elif isinstance(value, float) and not math.isfinite(value):
            result[field.name] = str(value)
        else:
            result[field.name] = value
    return result


def archive_input(label, series, categories):
    names = sorted(series)
    return dict(Source=label, Markets=[
        dict(Symbol=symbol, Category=categories.get(symbol) or "UNMAPPED",
             Bars={period: rows for period, rows in series[symbol].items()})
        for symbol in names if series[symbol].get("M5")])


def extract(packets, receipt):
    contracts, details, prices, categories, timeframe = {}, {}, {}, {}, []
    assets, roster = {}, {}
    expected = {row["symbolId"]: row for row in receipt["contractRoster"]}
    account = source.decode(packets[0]["reqType"], packets[0]["req"]).ctidTraderAccountId
    need(source.original_account(account), "SOURCE_USE_ACCOUNT_BINDING")
    for packet in packets:
        q = source.decode(packet["reqType"], packet["req"])
        r = source.decode(packet["resType"], packet["res"])
        at = packet["availableAt"]
        need(q.ctidTraderAccountId == r.ctidTraderAccountId == account, "SOURCE_USE_PACKET_ACCOUNT")
        if type(r) is messages.ProtoOAAssetListRes:
            assets = {a.assetId: a.name for a in r.asset}
        elif type(r) is messages.ProtoOASymbolsListRes:
            roster = {sym.symbolId: sym for sym in r.symbol}
        elif type(r) is messages.ProtoOASymbolByIdRes:
            for contract in r.symbol:
                sid = contract.symbolId
                need(sid in q.symbolId and sid in roster and sid not in contracts
                     and expected[sid]["contractAvailableAt"] == at, "SOURCE_USE_CONTRACT_BINDING")
                symbol = roster[sid]
                name = symbol.symbolName
                kind, mode, unknown = calculation_type(contract)
                row = fields_of(contract)
                quote_asset = assets.get(symbol.quoteAssetId) if symbol.HasField("quoteAssetId") else None
                contracts[sid] = dict(Symbol=name, Category=str(expected[sid]["category"]),
                    QuoteAsset=quote_asset, BaseAsset=assets.get(symbol.baseAssetId), AvailableAt=at, SwapKind=kind,
                    SwapCalculationType=mode, UnknownSwapValues=unknown, Fields=row)
                categories[name] = str(expected[sid]["category"])
        elif type(r) is messages.ProtoOAExpectedMarginRes:
            if r.HasField("moneyDigits") and len(r.margin) == 1 and list(q.volume) == [r.margin[0].volume]:
                margin = r.margin[0]
                row = expected[q.symbolId]
                need(row["marginStatus"] == source.VERIFIED and row["buyMarginRaw"] == margin.buyMargin
                     and row["sellMarginRaw"] == margin.sellMargin and row["marginMoneyDigits"] == r.moneyDigits,
                     "SOURCE_USE_MARGIN_RECEIPT")
                details[q.symbolId] = dict(BuyEur=str(Decimal(margin.buyMargin).scaleb(-r.moneyDigits)),
                    SellEur=str(Decimal(margin.sellMargin).scaleb(-r.moneyDigits)), AvailableAt=at,
                    VolumeUnits=str(Decimal(margin.volume).scaleb(-2)))
        elif type(r) is messages.ProtoOAGetTrendbarsRes:
            name = roster[q.symbolId].symbolName
            period = models.ProtoOATrendbarPeriod.Name(q.period)
            diagnostic, bars = inspect_bars(q, r, at)
            prior = expected[q.symbolId]
            timeframe.append(dict(symbol=name, symbolId=q.symbolId, timeframe=period,
                originalStatus=prior["timeframeStatus"][period],
                originalClosedRows=prior.get("timeframeEvidence", {}).get(period, {}).get("closedBars"),
                **diagnostic))
            if bars:
                need(period not in prices.setdefault(name, {}), "SOURCE_USE_DUPLICATE_TIMEFRAME")
                prices[name][period] = bars

    need(len(contracts) == len(expected) and len(timeframe) == len(receipt["timeframeProbeIds"]) * len(source.PERIODS)
         and len(details) == sum(row.get("marginStatus") == source.VERIFIED for row in expected.values()),
         "SOURCE_USE_COVERAGE")
    for sid, margin in details.items():
        contracts[sid]["Margin"] = margin
    return list(contracts.values()), timeframe, archive_input(SOURCE_RUN, prices, categories)


def older_bars(categories):
    sources = json.loads(Path("research/hrc1_protocol.json").read_text())["source"]
    bdp = next(row for row in sources if row["folder"] == "bdp-source")
    original, _, proof = recover(Path(bdp["folder"]), bdp["run"], bdp["hash"], bdp["schema"], bdp["protocol"])
    return archive_input(str(bdp["run"]), {s: {"M5": rows} for s, rows in original["bars"].items()}, categories), proof


def main():
    key = os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    packets, receipt = verified_original(Path("original-source-history"), key)
    contracts, timeframe, latest = extract(packets, receipt)
    categories = {c["Symbol"]: c["Category"] for c in contracts}
    annual, proof = older_bars(categories)
    with tempfile.TemporaryDirectory(prefix="mxm-history-use-") as temp:
        path = Path(temp)
        inputs = path / "protected-input.json"
        inputs.write_bytes(source.canonical(dict(Contracts=contracts, Archives=[annual, latest])))
        report = path / "result.json"
        environment = dict(os.environ)
        environment.pop("R3_CUSTODY_PRIVATE_KEY_PEM", None)
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(inputs), str(report), "--owner-source-history-use"], env=environment,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        public = json.loads(report.read_text())
    public.update(originalRunId=SOURCE_RUN, originalArtifactId=14920674158,
        originalPlaintextSha256=PLAIN_SHA, originalReceiptSha256=RECEIPT_SHA,
        originalCiphertextSha256=CIPHER_SHA, originalPacketCount=len(packets), annualReadback=proof,
        timeframeDiagnostics=timeframe, sourceOnlyRequests=0, ordersSubmitted=0, cloudActivated=False,
        historicalTariffContinuityCertified=False, allInNetEur=None, independentConfirmation=False)
    Path("source-history-use-public.json").write_bytes(source.canonical(public) + b"\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, CaptureContractError, subprocess.SubprocessError) as error:
        print("OWNER_SOURCE_HISTORY_USE_FAILED", type(error).__name__, flush=True)
        raise SystemExit(1) from None
