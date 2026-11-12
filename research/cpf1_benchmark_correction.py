"""Diagnose the Donchian filter using the exact archived CPF1 input."""
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean

from .cpf1_research import (PROTOCOL, FAMILIES, HOUR, M5, WEEK, recover, extract_costs,
                            h1_from_m5, cost_eligible, family_sides)

RECEIPT = Path("docs/CPF1_AUTHENTIC_RESULT_20261107.json")
FAMILY = FAMILIES[0]


def summarize(groups, costs):
    weeks = {key:[] for key in ("GrossBps","CentralProxyBps","AdverseProxyBps")}
    signals = 0
    for i in range(26):
        assets = {s:x for (w,s),x in groups.items() if w==i and x}
        signals += sum(map(len,assets.values()))
        for key, fee in (("GrossBps",None),("CentralProxyBps","centralBps"),("AdverseProxyBps","adverseBps")):
            weeks[key].append(mean(mean(x)-(costs[s][fee] if fee else 0) for s,x in assets.items()) if assets else 0)
    return dict(Observations=signals, EqualCalendarWeekMeanBps={k:mean(v) for k,v in weeks.items()}, Weekly=weeks)


def main():
    original = RECEIPT.read_bytes()
    receipt = json.loads(original)
    protocol = PROTOCOL.read_bytes()
    p = json.loads(protocol)
    if sha256(protocol).hexdigest()!=receipt["provenance"]["originalLockedProtocolSha256"]:
        raise ValueError("CPF1_CORRECTION_PROTOCOL")
    manifest = json.loads(Path(p["source"]["originalManifest"]).read_bytes())["source"]
    if [x["run"] for x in manifest]!=p["source"]["originalAuthenticatedSealedRuns"]:
        raise ValueError("CPF1_CORRECTION_SOURCE_RUNS")
    bars, contexts = {}, []
    for x in manifest:
        bundle, raw, verified = recover(Path(x["folder"]),x["run"],x["hash"],x["schema"],x["protocol"])
        if not verified or set(bars).intersection(bundle["bars"]):
            raise ValueError("CPF1_CORRECTION_SOURCE")
        bars.update(bundle["bars"])
        contexts.extend(extract_costs(bundle,raw)[0])
    if sum(map(len,bars.values()))!=p["source"]["originalAuthenticatedM5BarCount"] or len(contexts)!=166:
        raise ValueError("CPF1_CORRECTION_UNIVERSE")
    hourly = {s:h1_from_m5(v) for s,v in bars.items()}
    prices = {s:{int(r[1]):float(r[5]) for r in v} for s,v in bars.items()}
    costs,_ = cost_eligible(p,bars,contexts,hourly)
    sets = {k:defaultdict(list) for k in ("Filtered","Momentum","Unselected","Cash")}
    cal=p["clock"]
    for symbol in sorted(costs):
        hours, observed = hourly[symbol], prices[symbol]
        for t in range(cal["start"],cal["developmentEnd"],HOUR):
            date=datetime.fromtimestamp(t/1000,timezone.utc)
            if date.weekday() not in cal["utcWeekdays"] or date.hour not in cal["utcHours"]:
                continue
            if any(t-i*HOUR not in hours for i in range(21)):
                continue
            previous=[hours[t-i*HOUR] for i in range(1,21)]
            side=(hours[t][3]>previous[3][3])-(hours[t][3]<previous[3][3])
            fired=family_sides(hours[t],previous)[FAMILY]
            if fired and fired!=side:
                raise ValueError("CPF1_CORRECTION_DIRECTION")
            entry=t+M5
            exit_at=entry+cal["holdMinutes"]*60_000
            if not side or exit_at>=cal["developmentEnd"] or any(at not in observed for at in range(entry,exit_at+M5,M5)):
                continue
            key=((t-cal["start"])//WEEK,symbol)
            value=side*10000*math.log(observed[exit_at]/observed[entry])
            sets["Momentum"][key].append(value)
            sets["Filtered" if fired else "Unselected"][key].append(value)
    outputs={k:summarize(v,costs) for k,v in sets.items()}
    old=receipt["results"][FAMILY]
    if (outputs["Filtered"]["Observations"]!=old["developmentSignals"] or
        abs(outputs["Filtered"]["EqualCalendarWeekMeanBps"]["AdverseProxyBps"]-old["developmentEqualCalendarWeeklyAdverseNetBps"])>1e-8):
        raise ValueError("CPF1_CORRECTION_ORIGINAL_FILTER_PARITY")
    result=dict(Study="CPF1_DONCHIAN_BENCHMARK_CORRECTION", OriginalReceiptSha256=sha256(original).hexdigest(),
                OriginalProtocolSha256=sha256(protocol).hexdigest(), OriginalSources=manifest,
                ProtocolSha256=sha256(Path("research/CPF1_BENCHMARK_CORRECTION.md").read_bytes()).hexdigest(),
                **outputs, SelectionScored=False, PortfolioExecuted=False, IndependentConfirmation=False,
                BrokerRequests=0, OrdersSubmitted=0, CloudActivated=False)
    Path("cpf1-benchmark-correction-public.json").write_text(json.dumps(result,indent=2)+"\n")


if __name__ == "__main__":
    main()
