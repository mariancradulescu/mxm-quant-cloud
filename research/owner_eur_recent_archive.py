"""Evaluate V3 on the seven complete markets of the verified 13-week archive."""
import argparse
from collections import defaultdict
import gzip
from hashlib import file_digest
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

from . import funded_history_economic_development as prior
from . import integrated_market_readback as quotes
from . import owner_eer1_readback as readback
from . import owner_eer1_source as eer
from . import owner_eur_authentic_expansion as expansion
from . import owner_official_eur_source as official
from . import source_history_universe as source
from .ctrader_proto import OpenApiMessages_pb2 as messages
from .custody import unseal_new
from .decode import need
from .integrated_market_source import CIPHER_DIR, FUNDED_HISTORY, HOUR, PUBLIC_DIR

REGISTRY = Path("research/eur_recent_archive_13w_1.json")
TEMPLATE = Path("research/eur_recent_funded_1.json")
RECOVERY = Path("research/eur_recent_archive_13w_1_checkpoint_recovery.json")


def download_archive(artifact_id, run_id, expected_hash, destination):
    endpoint = f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts/{artifact_id}"
    metadata = json.loads(subprocess.check_output(["gh", "api", endpoint]))
    need(metadata["id"] == artifact_id and metadata["workflow_run"]["id"] == run_id and
         metadata["digest"] == "sha256:" + expected_hash and not metadata["expired"],
         "EUR_RECENT_ARCHIVE_ARTIFACT_IDENTITY")
    with tempfile.TemporaryFile() as stream:
        subprocess.run(["gh", "api", endpoint + "/zip"], stdout=stream, check=True)
        stream.seek(0)
        need(file_digest(stream, "sha256").hexdigest() == expected_hash, "EUR_RECENT_ARCHIVE_ZIP_HASH")
        stream.seek(0)
        destination.mkdir(mode=0o700)
        with ZipFile(stream) as archive:
            archive.extractall(destination)


def verified_scope(plan, key):
    recovery = prior.RECOVERY_DIR
    gap = (recovery / "gap-requests.json").read_bytes()
    original, manifest, names = prior.verify_recovery_binding(
        (PUBLIC_DIR / "source.json").read_bytes(), (recovery / "recovery-receipt.json").read_bytes(),
        (recovery / "coverage-manifest.json").read_bytes(), gap)
    need(names == plan["Instruments"] and original["Start"] == plan["InitialFitFrom"] and
         original["End"] == plan["TestBoundaries"][-1], "EUR_RECENT_ARCHIVE_REGISTERED_COVERAGE")
    prior.verify_original_against_manifest(original, manifest, prior.scan(original, key), gap)
    return original, manifest, names


def official_terms(original, names, key):
    shard = next(s for s in original["Shards"] if s["File"] == "account-contracts.enc")
    cipher = (CIPHER_DIR / shard["File"]).read_bytes()
    need(source.digest(cipher) == shard["CipherSha256"], "EUR_RECENT_ARCHIVE_TERM_CIPHER")
    compressed = unseal_new(cipher, key, original["RunId"])
    need(source.digest(compressed) == shard["CompressedPlainSha256"], "EUR_RECENT_ARCHIVE_TERM_PLAIN")
    metadata = json.loads(gzip.decompress(compressed))
    exchange = [quotes.unpack(row) for row in metadata["Identity"]]
    trader, assets, listing = (r for _, r in exchange[:3])
    account = exchange[0][0].ctidTraderAccountId
    need(source.original_account(account), "EUR_RECENT_ARCHIVE_ACCOUNT")
    asset = {a.assetId: a.name for a in assets.asset}
    roster = {s.symbolName: s for s in listing.symbol}
    details = {r.symbol[0].symbolId: r.symbol[0] for _, r in exchange
               if isinstance(r, messages.ProtoOASymbolByIdRes) and len(r.symbol) == 1}
    need(asset[trader.trader.depositAssetId] == "EUR" and
         asset[roster["EURUSD"].baseAssetId] == "EUR" and asset[roster["EURUSD"].quoteAssetId] == "USD",
         "EUR_RECENT_ARCHIVE_CONVERSION_IDENTITY")
    rows = {m["Name"]: m for m in metadata["Markets"]}
    resolved = {}
    for name in names:
        symbol = roster[name]
        detail = details[symbol.symbolId]
        at = rows[name]["Contract"]["ObservedAtUtcMs"]
        asset_name = asset[symbol.quoteAssetId]
        need(asset_name == "USD", "EUR_RECENT_ARCHIVE_QUOTE_ROUTE")
        terms, fields, _, _ = official.terms_input(detail, name, asset_name, at)
        info = dict(fields=fields, priceDigits=detail.digits, shortAllowed=detail.enableShortSelling,
                    tradingMode=detail.tradingMode, digest=source.digest(detail.SerializeToString()))
        resolved[name] = (terms, info, symbol.enabled)
    account_terms = dict(accountSwapFree=source.field(trader.trader, "swapFree"),
                         accountType=source.field(trader.trader, "accountType"),
                         moneyDigits=source.field(trader.trader, "moneyDigits"))
    return resolved, account_terms


def materialize(plan_raw, work, receipt):
    plan = json.loads(plan_raw)
    template_raw = TEMPLATE.read_bytes()
    need(source.digest(template_raw) == plan["TemplateSha256"], "EUR_RECENT_ARCHIVE_TEMPLATE")
    template = json.loads(template_raw)
    key = os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    original, manifest, names = verified_scope(plan, key)
    terms_by_market, account = official_terms(original, names, key)
    start, end = original["Start"], original["End"]
    clocks = [day + minute * 60_000 for day in range(start, end, eer.DAY)
              for minute in eer.charge_clocks({name: value[0] for name, value in terms_by_market.items()})]
    work.mkdir(mode=0o700)
    protection = work / "verified-protection"
    protection.mkdir(mode=0o700)
    raw_markets = quotes.readback(original, key, scope=FUNDED_HISTORY, include_markets=names,
                                 rollover_clocks=clocks, tick_sink=readback.protection_tick_sink(protection, "eer1"))
    active = defaultdict(set)
    for row in manifest["ActiveHourCoverage"]:
        if row["ResponseCoverage"] == "COMPLETE":
            active[row["Market"]].add(row["HourUtcMs"])
    markets, tapes, coverage = [], [], {}
    for market in raw_markets:
        name = market["Name"]
        terms, info, enabled = terms_by_market[name]
        decision_marks = [q for q in market.pop("Quotes")
                          if q["At"] % eer.STEP == 15_000 and q["At"] // HOUR * HOUR in active[name]]
        rollover_marks = market.pop("RolloverQuotes")
        need(bool(decision_marks) and len(active[name]) == manifest["Markets"][name]["ActiveHours"],
             "EUR_RECENT_ARCHIVE_MONETARY_COVERAGE")
        market["EnabledAtCapture"] = enabled
        market["OfficialAssetClass"] = None
        markets.append(expansion.dated_market(name, market, terms, info, account, market["Margin"],
                                              start, end, plan["OriginalRun"]))
        tapes.append(dict(Name=name, Quotes=decision_marks, FundingQuotes=rollover_marks))
        coverage[name] = dict(VerifiedActiveHours=len(active[name]), DecisionMarks=len(decision_marks),
                              FundingMarks=sum("Bid" in q and "Ask" in q for q in rollover_marks),
                              BarCounts={**{tf: len(market[tf]) for tf in ("M5", "M15", "H1")},
                                         **{tf: len(data["Bars"]) for tf, data in market["AdditionalTimeframes"].items()}})
    need(set(coverage) == set(names), "EUR_RECENT_ARCHIVE_COMPLETE_SCOPE")
    proof = dict(OriginalRun=plan["OriginalRun"], OriginalArtifact=plan["OriginalArtifact"],
                 OriginalArchiveSha256=plan["OriginalArchiveSha256"], RecoveryRun=plan["RecoveryRun"],
                 RecoveryArtifact=plan["RecoveryArtifact"], RecoveryArchiveSha256=plan["RecoveryArchiveSha256"],
                 OriginalRequests=original["Requests"], OriginalShards=len(original["Shards"]),
                 ManifestSha256=prior.MANIFEST_SHA256, Coverage=coverage, MissingNAS100Leaves=263,
                 TermsBasis="AUTHENTIC_ARCHIVED_CURRENT_CONTRACT_SCENARIO")
    source_protocol = source.digest(plan_raw)
    manifest_hash = source.digest(source.canonical(proof))
    private = dict(Start=start, FitEnd=plan["TestBoundaries"][0], End=end,
                   ProtocolSha256=source_protocol, EvidenceManifestSha256=manifest_hash,
                   EngineRevision=os.environ.get("MXM_ECONOMIC_ARCHIVE_CHECKPOINT_ORIGINAL_REVISION") or os.environ["GITHUB_SHA"],
                   SourceAcquiredAt=max(row[0]["ObservedAtUtcMs"] for row in terms_by_market.values()),
                   Markets=markets, Tapes=tapes, Routes={"USD": [dict(Symbol="EURUSD", BaseAsset="EUR", QuoteAsset="USD")]})
    controls = {t["Id"]: t for t in template["Trials"]}
    controls["V3_RANKED_RISK_RESIZE"] = dict(controls["V3_RANKED_GEOMETRY_RISK"],
        Id="V3_RANKED_RISK_RESIZE", ResizeWithinAdmissionRiskAtFill=True)
    protocol = dict(Study=plan["Study"], Exposure=template["Exposure"], SourceProtocolSha256=source_protocol,
                    EvidenceManifestSha256=manifest_hash, InitialFitFrom=plan["InitialFitFrom"],
                    TestBoundaries=plan["TestBoundaries"], Stresses=template["Stresses"],
                    Calibrations=template["Calibrations"], Trials=[controls[k] for k in plan["Trials"]],
                    ArchivedSampledQuotes=True, TrialGroups={"ARCHIVE": plan["Trials"]})
    private_bytes, protocol_bytes = source.canonical(private), source.canonical(protocol)
    for name, data in (("source.json", private_bytes), ("protocol.json", protocol_bytes)):
        (work / name).write_bytes(data)
    receipt.write_bytes(source.canonical(dict(Study=plan["Study"], EvidenceManifestSha256=manifest_hash,
        SourceSha256=source.digest(private_bytes), ProtocolSha256=source.digest(protocol_bytes), Proof=proof,
        SourceBrokerRequests=0, Orders=0, CloudActivated=False, IndependentConfirmationCertified=False)))
    print("EUR_RECENT_ARCHIVE_MATERIALIZED", coverage, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("download", "materialize", "restore"))
    parser.add_argument("--work", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    raw = REGISTRY.read_bytes()
    if args.stage == "download":
        plan = json.loads(raw)
        download_archive(plan["OriginalArtifact"], plan["OriginalRun"], plan["OriginalArchiveSha256"], CIPHER_DIR)
        download_archive(plan["RecoveryArtifact"], plan["RecoveryRun"], plan["RecoveryArchiveSha256"], prior.RECOVERY_DIR)
    elif args.stage == "restore":
        marker = json.loads(RECOVERY.read_bytes())
        need(source.digest(raw) == marker["ProtocolSha256"] and
             marker["ReplayRevision"] == os.environ["MXM_ECONOMIC_ARCHIVE_CHECKPOINT_ORIGINAL_REVISION"],
             "EUR_RECENT_ARCHIVE_RESUME_REGISTRATION")
        selected = marker["Checkpoints"][os.environ["MXM_ECONOMIC_SCENARIO_INDEX"]]
        destination = Path("checkpoints/3")
        destination.parent.mkdir(exist_ok=True)
        download_archive(selected["Artifact"], marker["ReplayRun"], selected["ArchiveSha256"], destination)
        need((destination / "checkpoint.sealed").is_file(), "EUR_RECENT_ARCHIVE_MISSING_PHASE3")
    else:
        materialize(raw, args.work, args.receipt)


if __name__ == "__main__":
    main()
