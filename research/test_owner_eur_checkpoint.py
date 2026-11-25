"""Synthetic full replay parity across encrypted process boundaries, without broker or Cloud access."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from . import owner_eur_checkpoint as checkpoint
from .custody import unseal


DAY = 86_400_000
STEP = 300_000
START = 1_792_972_800_000
FIT = START + 6 * DAY
END = FIT + 3 * DAY
CONTRACT_HASH = "a" * 64
SOURCE_HASH = "b" * 64
WIDTHS = {"M1": 60_000, "M5": STEP, "M15": 900_000, "M30": 1_800_000,
          "H1": 3_600_000, "H4": 14_400_000, "D1": DAY}


def cents(value):
    return f"{value // 100}.{value % 100:02}"


def bid_at(at):
    slot = (at - START) // STEP
    return 10000 + 10 * (slot % 24) + 120 * ((slot // 12) % 2)


def bars(width):
    return [
        dict(OpenAt=at, CloseAt=at + width, Open=cents(bid_at(at)),
             Close=cents(bid_at(at + width)), High=cents(max(bid_at(at), bid_at(at + width)) + 6),
             Low=cents(min(bid_at(at), bid_at(at + width)) - 6), TickVolume=100)
        for at in range(START - 6 * width, END + width, width)
    ]


def fixture(work):
    clock_index = [at for at in range(START + 15_000, END + 2 * STEP, STEP)
                   if (at - START) % DAY >= DAY - 6 * 3_600_000 or (at - START) % DAY < 12 * STEP]
    quotes = [dict(At=at, BidAt=at - 1, AskAt=at - 1, Bid=cents(bid_at(at)),
                   Ask=cents(bid_at(at) + 2), Path=None) for at in clock_index]
    markets = []
    available_bars = {name: bars(width) for name, width in WIDTHS.items()}
    for symbol in ("SYNTH_A", "SYNTH_B"):
        contract = dict(Symbol=symbol, QuoteAsset="EUR", ObservedAtUtcMs=START - 1000,
                        MinimumUnits=1, VolumeStepUnits=1, MaximumUnits=2, LotUnits=100,
                        CommissionType=2, PreciseRateWire=0, MinimumCommissionType=2,
                        SwapCalculationType=0, LongSwap=0, ShortSwap=0, PipPosition=2,
                        SwapPeriodHours=24, SwapTimeUtcMinute=1320, TripleSwapWeekday=3,
                        ChargeSwapAtWeekends=False, SkipSwapPeriods=0, OriginalBrokerAuthenticated=True)
        margin = [dict(Units=1, BuyMargin=20, SellMargin=20)]
        terms = dict(Contract=contract, Margin=margin, ShortAllowed=True, TradingMode=0,
                     AccountSwapFree=False, Digest=CONTRACT_HASH, SourceRun="SYNTHETIC",
                     AccountType=0, MoneyDigits=2, PriceDigits=2)
        market = dict(Name=symbol, Class="SYNTHETIC", Contract=contract, TickSize="0.01",
                      ShortAllowed=True, TradingMode=0, CostTermsComplete=True, Margin=margin,
                      Quotes=[], ActiveHours=24, RequestedTickHours=24, Schedule=[], ScheduleTimeZone="UTC",
                      EnabledAtCapture=True, DatedDevelopment=terms, OfficialAssetClass="SYNTHETIC")
        market.update({key: available_bars[key] for key in ("M5", "M15", "H1")})
        market["AdditionalTimeframes"] = {
            key: dict(Source="SYNTHETIC", Bars=available_bars[key]) for key in ("M1", "M30", "H4", "D1")
        }
        schedule = list(range(START + 15_000, END + 2 * STEP, STEP))
        markets.append(dict(Market=market, TermsAcquiredAt=START - 1000, ScheduledClocks=schedule,
                            AmbiguousCalendarClocks=[], CalendarStatus="SYNTHETIC_COMPLETE_CALENDAR"))
    protection = work / "verified-protection"
    protection.mkdir()
    for symbol in ("SYNTH_A", "SYNTH_B"):
        prefix = hashlib.sha256(symbol.encode()).hexdigest()
        for side, spread in (("bid", 0), ("ask", 2)):
            raw_ticks = [(at + delta, (bid_at(at) + spread) * 1000)
                         for at in clock_index for delta in (-1, 1000, 15000, STEP - 100)]
            base = f"{prefix}-{side}-eer1"
            (protection / f"{base}.ticks").write_bytes(b"".join(struct.pack("<qq", *tick) for tick in raw_ticks))
            (protection / f"{base}.coverage").write_bytes(struct.pack("<qq", START, END + STEP))
    first = clock_index[0] + 1000
    touch = clock_index[1] - 1
    protocol = json.loads(Path(checkpoint.PROTOCOL).read_bytes())
    protocol.update(InitialFitFrom=START, TestBoundaries=[FIT + i * DAY for i in range(4)],
                    SourceProtocolSha256=CONTRACT_HASH, EvidenceManifestSha256=SOURCE_HASH,
                    StopWitness=dict(Symbol="SYNTH_A", Side=-1, OriginalFillAt=first,
                                     OriginalCloseAt=touch + 10, StopDistance="0.03", FirstTradeTouchAt=touch))
    (work / "protocol.json").write_text(json.dumps(protocol))
    input_data = dict(Start=START, FitEnd=FIT, End=END, ProtocolSha256=CONTRACT_HASH,
                      EngineRevision="0" * 40, EvidenceManifestSha256=SOURCE_HASH, SourceAcquiredAt=END,
                      Markets=markets, Tapes=[dict(Name=x["Market"]["Name"], Quotes=quotes, FundingQuotes=[])
                                               for x in markets],
                      Routes={})
    (work / "source.json").write_text(json.dumps(input_data))


class CheckpointReplay(unittest.TestCase):
    def test_continuous_and_restored_replay(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            fixture(work)
            protocol = str(work / "protocol.json")
            settings = dict(MXM_ECONOMIC_SCENARIO_INDEX="1", MXM_ECONOMIC_PROFILE="0",
                            MXM_ECONOMIC_RECEIPT_DIRECTORY=str(work / "resumed-receipts"))
            times = {}
            for mode, enabled in (("legacy", "0"), ("optimized", "1")):
                report = work / f"{mode}.json"
                env = dict(os.environ, **settings)
                env.pop("MXM_ECONOMIC_RECEIPT_DIRECTORY")
                env.update(MXM_ECONOMIC_BOUNDED_NEIGHBORS=enabled, MXM_ECONOMIC_PAIRED_DISTRIBUTION=enabled,
                           MXM_ECONOMIC_REUSE_FRAMES=enabled)
                start = time.monotonic()
                subprocess.run(["dotnet", checkpoint.REPLAY, "--owner-eur-historical-study", protocol,
                                str(work / "source.json"), str(report), str(work / "verified-protection")],
                               env=env, check=True, stdout=subprocess.DEVNULL)
                times[mode] = time.monotonic() - start
            self.assertEqual(hashlib.sha256((work / "legacy.json").read_bytes()).digest(),
                             hashlib.sha256((work / "optimized.json").read_bytes()).digest())
            resumed = work / "resumed.json"
            settings.update(MXM_ECONOMIC_BOUNDED_NEIGHBORS="1", MXM_ECONOMIC_PAIRED_DISTRIBUTION="1",
                            MXM_ECONOMIC_REUSE_FRAMES="1", R3_CUSTODY_PRIVATE_KEY_PEM=key.decode())
            with patch.dict(os.environ, settings), patch.object(checkpoint, "PROTOCOL", protocol):
                previous = None
                start = time.monotonic()
                saved_active = 0
                for phase in (1, 2, 3):
                    archive = work / str(phase)
                    checkpoint.run(work, archive, previous, phase, resumed)
                    previous = archive / "checkpoint.sealed"
                    state = json.loads(gzip.decompress(unseal(previous.read_bytes(), key)))
                    self.assertEqual(state["CompletedPhases"], phase)
                    self.assertEqual(len(state["Streams"]), 2)
                    self.assertEqual(len(state["Observers"]), 2)
                    self.assertEqual(len(state["Trials"]), 4)
                    saved_active += sum(sum(x is not None for x in row["Episodes"]) for row in state["Observers"].values())
                    self.assertFalse(any(archive.glob("*checkpoint*.json")))
                checkpoint.run(work, None, previous, None, resumed)
                times["resumed"] = time.monotonic() - start
            digest = hashlib.sha256(resumed.read_bytes()).hexdigest()
            self.assertEqual(digest, hashlib.sha256((work / "legacy.json").read_bytes()).hexdigest())
            scenario = json.loads(resumed.read_bytes())["Summary"]["Results"][0]
            self.assertGreater(saved_active, 0)
            self.assertGreater(sum(x["Details"]["Counts"].get("MATURED_RECONCILED_LABEL", 0)
                                   for x in scenario["OpportunityObservations"]), 0)
            self.assertEqual(len(list((work / "resumed-receipts").glob("*.json"))), 3)
            print("EUR_FULL_REPLAY_PARITY", digest, "active_snapshots", saved_active, "seconds", times, flush=True)


if __name__ == "__main__":
    unittest.main()
