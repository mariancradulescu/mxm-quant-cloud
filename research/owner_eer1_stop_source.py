"""Recover the official Trade stop witness for the worst NatGas episode."""
import json
import os
from decimal import Decimal
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from . import owner_eer1_source as eer
from . import owner_eur_conditional_source as conditional
from . import owner_eur_rollover_continuity as roll
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need


RUN = "45555613548"
SOURCE_ARTIFACT = 15000522105
DIAGNOSIS_ARTIFACT = 15004052694
DIAGNOSIS_SHA = "894e3915d3dd669d5b71f2b1bf24cfe4f51f9832f6896524a6985b3fb9b027a6"
SYMBOL = "NatGas"
ROOT_SPAN = 4 * 3600000


def focused_ticks(shard, fill, close):
    replies = {}
    account = None
    for packet in shard["packets"]:
        if packet["reqType"] != m.ProtoOAGetTickDataReq.__name__:
            continue
        query = eer.src.decode(packet["reqType"], packet["req"])
        if account is None:
            account = query.ctidTraderAccountId
        need(query.IsInitialized() and query.symbolId == shard["id"] and
             query.ctidTraderAccountId == account, "EER1_STOP_SYMBOL_BINDING")
        key = packet["req"]
        need(key not in replies, "EER1_STOP_DUPLICATE_TICK_REQUEST")
        replies[key] = packet
    need(account is not None and eer.src.original_account(account), "EER1_STOP_SHARD_TICKS")

    def request(query):
        packet = replies.get(eer.src.encode(query))
        if packet is None:
            return None, None, eer.src.UNCOLLECTED
        return eer.src.ReadbackJournal([packet]).query(query)

    start = fill - 30000
    first_root = start // ROOT_SPAN * ROOT_SPAN
    ticks = {}
    for side in (e.BID, e.ASK):
        ticks[side] = []
        leaves = []
        for left in range(first_root, close + 1, ROOT_SPAN):
            quote, pages = roll.tick_window(request, account, shard["id"], side, left,
                                           left + ROOT_SPAN - 1, [len(replies)])
            ticks[side].extend(row for row in quote if start <= row[0] <= close)
            leaves.extend(pages)
        need(eer.covered(leaves, start, close), "EER1_STOP_CUSTODY_WINDOW_INCOMPLETE")
    return ticks


def main():
    source = Path("stop-source")
    receipt = json.loads((source / "receipt.json").read_bytes())
    ref = next(s for s in receipt["sources"] if s["name"] == SYMBOL)
    diagnosis = Path("eer1-diagnosis.json").read_bytes()
    need(eer.src.digest(diagnosis) == DIAGNOSIS_SHA and receipt["runId"] == RUN,
         "EER1_STOP_RECEIPT_IDENTITY")
    episodes = next(s["Comparison"]["Episodes"] for s in json.loads(
        diagnosis, parse_float=Decimal)["Results"] if s["Stress"] == "S0")
    worst = min((x for x in episodes if x["Original"]["Symbol"] == SYMBOL),
                key=lambda x: x["Original"]["ReconciledNetEur"])
    original = worst["Original"]
    need(worst["Status"] == "RECONCILED_TO_ORIGINAL" and worst["SlippageEur"] == 0 and
         original["Side"] == -1 and len(worst["Parts"]) == 1, "EER1_STOP_S0_BRACKET_WITNESS")
    private_key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    shard = eer.unpack(source, ref, private_key, RUN)
    need(shard["name"] == ref["name"] and shard["id"] == ref["id"] and
         len(shard["packets"]) == ref["requests"], "EER1_STOP_SHARD_BINDING")
    fill, close = original["OpenAt"], original["CloseAt"]
    side = original["Side"]
    ticks = focused_ticks(shard, fill, close)

    def boundary(quote_side, at):
        mark = conditional.boundary(ticks[quote_side], at, True)
        need(mark and not mark["conflict"] and at - mark["at"] <= 30000, "EER1_STOP_BOUNDARY_QUOTE")
        return mark["at"], Decimal(mark["rawPrices"][0]).scaleb(-5)

    _, entry_price = boundary(e.BID, fill)
    at_fill, fill_side = boundary(e.ASK, fill)
    _, exit_side = boundary(e.ASK, close)
    stop = entry_price - side * worst["StopDistance"]
    original_overshoot = side * (stop - exit_side)
    need(original_overshoot > 0 and original_overshoot == worst["MaximumExitBeyondStop"],
         "EER1_STOP_ORIGINAL_PRICE_RECONCILIATION")
    tape = dict(PositionId=original["PositionId"], Side=side, FillAt=fill, OriginalCloseAt=close,
                AtFill=dict(At=at_fill, Price=str(fill_side)), Stop=str(stop),
                TradeSideTicks=[dict(At=t, Price=str(Decimal(raw).scaleb(-5)))
                                for t, raw in ticks[e.ASK] if fill < t <= close])
    with TemporaryDirectory() as directory:
        input_path = Path(directory) / "verified-quotes.json"
        output_path = Path(directory) / "trigger.json"
        input_path.write_bytes(eer.src.canonical(tape))
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        "--owner-eer1-stop-trigger-source", str(input_path), str(output_path)], check=True)
        result = json.loads(output_path.read_bytes())
    result.update(SourceArtifact=SOURCE_ARTIFACT, DiagnosisArtifact=DIAGNOSIS_ARTIFACT,
                  DiagnosisSha256=DIAGNOSIS_SHA, ShardSha256=ref["cipherSha256"],
                  OriginalExitOvershootInPrice=str(original_overshoot),
                  OriginalModeledNetEur=str(worst["NetEur"]), SourceBidTicks=len(ticks[e.BID]),
                  SourceAskTicks=len(ticks[e.ASK]), FullPageCoverage=True, BrokerRequests=0,
                  EconomicEvaluations=0)
    Path("eer1-stop-trigger-source.json").write_bytes(eer.src.canonical(result))


if __name__ == "__main__":
    main()
