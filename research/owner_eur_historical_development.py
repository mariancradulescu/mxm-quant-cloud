"""Reconstruct the new chronological EUR development from existing official sources."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import closed_market_context_readback as context
from . import integrated_market_readback as integrated
from . import owner_official_eur_source as official
from .decode import CaptureContractError, need
from .integrated_market_source import margin_snapshot
from .multiscale_conditional_research import recover

PROTOCOL = Path("research/OWNER_EUR_INTEGRATED_DEVELOPMENT_20261125.md")
OUT = Path("owner-eur-development-public")
MATRIX = Path("owner-eur-matrix/universe-evidence-matrix.json")
MATRIX_SHA256 = "63edb61f71f759e5c97d7dcb6595f285a42008d3b8e96d21471c3c183cd67462"
SUPPLEMENTARY = "44733062339"
# Upper bounds from the authenticated GitHub Actions completion times. The old
# bundles did not timestamp every margin response; do not move them earlier.
COMPLETE_BY = {
    41724643418: "2026-11-03T21:52:44+00:00",
    41735441128: "2026-11-03T23:05:43+00:00",
}
ARCHIVE_START = int(datetime.fromisoformat("2026-11-04T00:00:00+00:00").timestamp()*1000)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def preceding_terms():
    result = {}
    old_bars = {}
    for source in json.loads(Path("research/hrc1_protocol.json").read_text())["source"]:
        run = source["run"]
        bundle, wires, verified = recover(Path(source["folder"]), run, source["hash"],
                                          source["schema"], source["protocol"])
        need(verified["rawAccountAndBarsReconstructed"], "DATED_EUR_ORIGINAL_TERMS_READBACK")
        stamp = int(datetime.fromisoformat(COMPLETE_BY[run]).timestamp() * 1000)
        trader = wires[0][1].trader
        swap_free = trader.swapFree if trader.HasField("swapFree") else None
        for name, entry in bundle["symbols"].items():
            detail = wires[entry["contractRawIndex"]][1].symbol[0]
            if not detail.HasField("tradingMode"):
                continue
            fields = official.terms_input(detail, name, entry["quoteAsset"], stamp)
            if fields is None:
                continue
            cost_terms, _, _, _ = fields
            q, r = wires[entry["marginRawIndex"]]
            margin = margin_snapshot(r, list(q.volume))
            if not margin:
                continue
            result[name] = dict(Contract=cost_terms, Margin=margin,
                                ShortAllowed=detail.HasField("enableShortSelling") and detail.enableShortSelling,
                                TradingMode=detail.tradingMode, AccountSwapFree=swap_free,
                                AccountType=trader.accountType if trader.HasField("accountType") else None,
                                MoneyDigits=trader.moneyDigits if trader.HasField("moneyDigits") else None,
                                PriceDigits=detail.digits,
                                Digest=sha(trader.SerializeToString() + detail.SerializeToString() + q.SerializeToString() +
                                           r.SerializeToString() + str(run).encode()),
                                SourceRun=str(run))
        old_bars.update(bundle["bars"])
    return result, old_bars


def rollover_clocks(terms):
    minutes = set()
    for entry in terms.values():
        c = entry["Contract"]
        period, offset = c["SwapPeriodHours"], c["SwapTimeUtcMinute"]
        if period and 24 % period == 0 and offset is not None and 0 <= offset < 1440:
            minutes.update(range(offset, 1440, 60*period))
    return [day + minute*60_000 for day in range(ARCHIVE_START, integrated.END, integrated.DAY)
            for minute in sorted(minutes)]


def main():
    evidence_only = sys.argv[1:] == ["--evidence-only"]
    need(evidence_only or not sys.argv[1:], "DATED_EUR_ENTRY_MODE")
    key = os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "DATED_EUR_EXISTING_CUSTODY_KEY_MISSING")
    matrix_data = MATRIX.read_bytes()
    need(sha(matrix_data) == MATRIX_SHA256, "DATED_EUR_PUBLISHED_MATRIX_HASH")
    roster = {r["symbol"]: r for r in json.loads(matrix_data)["matrix"]}
    dated, old_bars = preceding_terms()
    print("DATED_EUR_PRECEDING_TERMS_VERIFIED", len(dated), flush=True)
    markets, extra = context.sources(key, SUPPLEMENTARY, native_boundaries=True,
                                     rollover_clocks=rollover_clocks(dated))
    source_notes = []
    for market in markets:
        symbol = market["Name"]
        row = roster.get(symbol, {})
        market["OfficialAssetClass"] = row.get("assetClass")
        earlier = dated.get(symbol)
        if earlier and earlier["Contract"]["QuoteAsset"] == market["Contract"]["QuoteAsset"]:
            market["DatedDevelopment"] = earlier
        # Long archival history can supply past context, never fill missing
        # marks or substitute a changing bar during the studied window.
        boundary = market["M5"][0]["OpenAt"] if market["M5"] else integrated.START
        prior = [r for r in old_bars.get(symbol, []) if r[1] <= boundary]
        market["M5"] = integrated.normalized_bars(prior) + market["M5"]
        source_notes.append(dict(Symbol=symbol, Class=market["OfficialAssetClass"],
                                 Category=row.get("category"), ArchivedWarmupM5=len(prior),
                                 RawQuoteMarks=len(market["Quotes"]), PrecedingTerms=symbol in dated,
                                 MissingTimeframes=[t for t in ("M1","M30","H4","D1")
                                                    if not market["AdditionalTimeframes"].get(t, {}).get("Bars")]))
    need(bool(markets) and any("DatedDevelopment" in m for m in markets), "DATED_EUR_NO_MATCHED_FINANCIAL_INPUT")
    OUT.mkdir(exist_ok=True)
    protocol_hash = sha(PROTOCOL.read_bytes())
    with tempfile.TemporaryDirectory(prefix="mxm-dated-eur-") as folder:
        materialized = Path(folder) / "verified-source.json"
        with materialized.open("x") as f:
            materialized.chmod(0o600)
            json.dump(dict(Start=integrated.START, End=integrated.END, SourceRun=context.INTEGRATED_RUN,
                           ProtocolSha256=protocol_hash, ManagementIntervalMs=30_000, Markets=markets),
                      f, separators=(",", ":"))
        input_hash = integrated.hashlib_file(materialized)
        env = {k:v for k,v in os.environ.items() if k != "R3_CUSTODY_PRIVATE_KEY_PEM"}
        result = OUT / ("finance-and-daily-context.json" if evidence_only else "economic.json")
        calibration = OUT / "calibration.json"
        mode = "--owner-eur-archive-evidence-only" if evidence_only else "--owner-eur-historical-development"
        print("DATED_EUR_ARCHIVES_BOUND", mode, len(markets), flush=True)
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        mode, str(materialized),str(result)] + ([] if evidence_only else [str(calibration)]),
                       check=True, env=env)
    receipt = dict(ArchiveRun=context.INTEGRATED_RUN, SupplementaryRun=SUPPLEMENTARY,
        HxcRun=context.HXC1_RUN, PrecedingContractRuns=list(COMPLETE_BY), ExposedDevelopment=True,
        InputSha256=input_hash, ProtocolSha256=protocol_hash, ResultSha256=sha(result.read_bytes()),
        CalibrationSha256=None if evidence_only else sha(calibration.read_bytes()),
        EvidenceOnly=evidence_only, OriginalSupplementaryHash=extra["CipherSha256"],
        MarketSources=source_notes, BrokerRequests=0, Orders=0, CloudActivated=False)
    (OUT / "receipt.json").write_text(json.dumps(receipt,indent=2) + "\n")
    print("DATED_EUR_NATIVE_DEVELOPMENT_PUBLISHED", flush=True)


if __name__ == "__main__":
    try:
        main()
    except CaptureContractError as error:
        print(str(error), flush=True)
        raise SystemExit(1) from None
