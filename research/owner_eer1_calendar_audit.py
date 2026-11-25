"""Read and classify the official contract calendars in the immutable EER1 metadata."""
import argparse
import json
import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import owner_eer1_recovery as recovery
from . import owner_eer1_source as eer
from . import owner_official_eur_source as wire
from . import owner_source_history_use as history
from . import source_history_universe as src
from .ctrader_proto import OpenApiMessages_pb2 as messages
from .decode import need


def classify(fields):
    """Explain all failing assumptions in the original schedule parser."""
    issues = []

    def check_zone(value, label):
        if not value:
            issues.append(f"{label}_TIME_ZONE_ABSENT")
            return
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            issues.append(f"{label}_TIME_ZONE_UNSUPPORTED")

    check_zone(fields.get("scheduleTimeZone"), "SESSION")
    intervals = fields.get("schedule", [])
    if not intervals:
        issues.append("SCHEDULE_ABSENT_IN_OFFICIAL_RESPONSE")
    for index, row in enumerate(intervals):
        start, end = row["startSecond"], row["endSecond"]
        if not 0 <= start < end <= 7 * 86400:
            issues.append(f"SESSION_INTERVAL_OUTSIDE_ORIGINAL_ASSUMPTION[{index}]")
    for index, row in enumerate(fields.get("holiday", [])):
        check_zone(row.get("scheduleTimeZone"), f"HOLIDAY[{index}]")
        start, end = row.get("startSecond", 0), row.get("endSecond", 86400)
        if not 0 <= start < end <= 86400:
            issues.append(f"HOLIDAY_INTERVAL_OUTSIDE_ORIGINAL_ASSUMPTION[{index}]")
        try:
            date(1970, 1, 1) + timedelta(days=row["holidayDate"])
        except (KeyError, OverflowError):
            issues.append(f"HOLIDAY_DATE_UNSUPPORTED[{index}]")
    return issues


def clock_counts(clocks):
    if clocks is None:
        return None
    return {
        "calibration": sum(eer.START <= clock < eer.FIT_END for clock in clocks),
        "comparison": sum(eer.FIT_END <= clock < eer.END for clock in clocks),
    }


def extract(packets, selected):
    items = list(wire.decoded_packets(dict(requests=packets)))
    roster = next({symbol.symbolName: symbol for symbol in r.symbol}
                  for _, _, r in items if type(r) is messages.ProtoOASymbolsListRes)
    assets = next({asset.assetId: asset.name for asset in r.asset}
                  for _, _, r in items if type(r) is messages.ProtoOAAssetListRes)
    requested, received = set(), {}
    for packet in packets:
        if packet["reqType"] == "ProtoOASymbolByIdReq":
            requested.update(src.decode(packet["reqType"], packet["req"]).symbolId)
    for row, request, response in items:
        if type(response) is not messages.ProtoOASymbolByIdRes:
            continue
        need(type(request) is messages.ProtoOASymbolByIdReq, "CALENDAR_REPLY_TYPE")
        for contract in response.symbol:
            need(contract.symbolId in request.symbolId, "CALENDAR_REPLY_SYMBOL")
            need(contract.symbolId not in received, "CALENDAR_DUPLICATE_SNAPSHOT")
            received[contract.symbolId] = (row["at"], contract)

    results = {}
    for name in selected:
        light = roster.get(name)
        if light is None or light.symbolId not in requested:
            reason = ("OFFICIALLY_DISABLED_AT_CAPTURE" if light is not None and not light.enabled
                      else "CONTRACT_NOT_COLLECTED")
            results[name] = {"reason": reason}
            continue
        if light.symbolId not in received:
            results[name] = {"reason": "CONTRACT_ABSENT_FROM_VERIFIED_RESPONSE"}
            continue
        observed_at, contract = received[light.symbolId]
        fields = history.fields_of(contract)
        issues = classify(fields)
        terms = wire.terms_input(contract, name, assets.get(light.quoteAssetId), observed_at)
        original_clocks = eer.schedule(fields) if terms is not None else None
        reason = "PARSED_BY_EER1"
        if original_clocks is None:
            reason = ("CONTRACT_TERMS_UNSUPPORTED" if terms is None else
                      issues[0] if issues else "UNCLASSIFIED_ORIGINAL_IMPLEMENTATION_EXCEPTION")
        contract_units = {
            name: str(Decimal(fields[key]).scaleb(-2))
            for key, name in (("lotSize", "lotUnits"), ("minVolume", "minimumUnits"),
                              ("stepVolume", "volumeStepUnits"), ("maxVolume", "maximumUnits"))
            if key in fields
        }
        results[name] = {
            "reason": reason, "issues": issues, "contractObservedAt": observed_at,
            "contractSha256": src.digest(contract.SerializeToString()),
            "quoteAsset": assets.get(light.quoteAssetId), "contractUnits": contract_units,
            "sessionTimeZone": fields.get("scheduleTimeZone"),
            "sessions": fields.get("schedule", []),
            "holidays": [{key: value for key, value in record.items()
                          if key in {"scheduleTimeZone", "holidayDate", "isRecurring", "startSecond", "endSecond"}}
                         for record in fields.get("holiday", [])],
            "originalScheduledClocks": clock_counts(original_clocks),
            "historicalCalendarContinuityCertified": False,
        }
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    receipt = json.loads((args.source / "receipt.json").read_bytes())
    need(receipt["runId"] == recovery.ORIGINAL_RUN and len(receipt["selected"]) == 16 and
         len(set(receipt["selected"])) == 16 and receipt["metadata"]["file"] == "metadata.sealed" and
         receipt["protocolSha256"] == src.digest(eer.PROTOCOL.read_bytes()) and
         receipt["matrixSha256"] == eer.MATRIX_SHA, "CALENDAR_ORIGINAL_RECEIPT")
    original = eer.unpack(args.source, receipt["metadata"],
                          os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(), recovery.ORIGINAL_RUN)
    need(original["runId"] == recovery.ORIGINAL_RUN and original["chosen"] == receipt["selected"],
         "CALENDAR_ORIGINAL_METADATA_BINDING")
    rows = extract(original["packets"], original["chosen"])
    report = dict(originalRun=recovery.ORIGINAL_RUN, originalArtifact=recovery.ARTIFACT_ID,
                  originalArchiveSha256=recovery.ARTIFACT_SHA, metadata=receipt["metadata"],
                  calendars=rows, interpretation="CONDITIONAL_CAPTURE_SNAPSHOT",
                  brokerRequests=0, economicRuns=0, orders=0, cloudActivated=False)
    args.report.write_bytes(src.canonical(report))
    for name, row in sorted(rows.items()):
        print(name, row["reason"], row.get("originalScheduledClocks"), flush=True)


if __name__ == "__main__":
    main()
