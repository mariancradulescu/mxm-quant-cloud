"""Diagnose PVE1 continuation selection from exact original source custody."""
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean

from .pve1_causal import P, M5, WEEK, FAMILIES, HORIZONS, feature, phase, recover, extract_costs, market_view, cost_context

ORIGINAL = Path("docs/PVE1_AUTHENTIC_RESULT.json")
PROTOCOL_SHA = "921330cad16a93c7700dc26928c416e773b5192a2e2fb55d23d74f9443893496"


def summarize(weeks, cost):
    observations = sum(len(x) for x in weeks)
    return dict(Observations=observations, ActiveWeeks=sum(bool(x) for x in weeks),
                GrossBpsByWeek=[sum(x) for x in weeks],
                EqualCalendarWeekGrossBps=mean(sum(x) for x in weeks),
                EqualCalendarWeekCentralProxyBps=mean(sum(x)-len(x)*cost["centralBps"] for x in weeks),
                EqualCalendarWeekAdverseProxyBps=mean(sum(x)-len(x)*cost["adverseBps"] for x in weeks))


def main():
    protocol = P.read_bytes()
    if sha256(protocol).hexdigest() != PROTOCOL_SHA:
        raise ValueError("PVE1_CORRECTION_PROTOCOL")
    p = json.loads(protocol)
    original = ORIGINAL.read_bytes()
    receipt = json.loads(original)
    bars, costs = {}, []
    for source in p["sources"]:
        bundle, decoded, verified = recover(Path(source["folder"]), source["run"], source["hash"],
                                            source["schema"], source["protocol"])
        if not verified or set(bars).intersection(bundle["bars"]):
            raise ValueError("PVE1_CORRECTION_SOURCE")
        bars.update(bundle["bars"])
        costs.extend(extract_costs(bundle, decoded)[0])
    if set(bars) != set(p["symbols"]) or len(costs) != 166:
        raise ValueError("PVE1_CORRECTION_UNIVERSE")
    ctx = cost_context(costs)
    periods = dict(development=(0,26), selection=(26,39), exposed_audit=(39,52))
    cells = {}
    for symbol, values in bars.items():
        rows = {x[1]:x for x in values}
        view = market_view(values)
        data = defaultdict(list)
        for t in view["observed"]:
            if t % (p["features"]["decisionMinutes"]*60000) or not p["phase"]["start"] <= t < p["phase"]["end"]:
                continue
            directions = feature(rows,t,p,include_eligible_momentum=True)
            side = directions.get("UNFILTERED_MOMENTUM",{}).get("side",0)
            if not side:
                continue
            part, end = phase(t,p)
            entry = t+p["features"]["entryDelayMinutes"]*60000
            if entry not in rows:
                continue
            week = (t-p["phase"]["start"])//WEEK
            picked = FAMILIES[0] in directions
            if picked and directions[FAMILIES[0]]["side"] != side:
                raise ValueError("PVE1_CORRECTION_DIRECTION")
            for horizon in HORIZONS:
                due = entry+horizon*60000
                if due < end and due in rows:
                    value = side*10000*math.log(rows[due][5]/rows[entry][5])
                    data[part,horizon,week].append((picked,value))
        for horizon in HORIZONS:
            result = {}
            for part,(lo,hi) in periods.items():
                blocks = [data[part,horizon,w] for w in range(lo,hi)]
                policies = {"Filtered":[[v for yes,v in block if yes] for block in blocks],
                            "Momentum":[[v for _,v in block] for block in blocks],
                            "Unselected":[[v for yes,v in block if not yes] for block in blocks],
                            "Cash":[[] for _ in blocks]}
                result[part] = {k:summarize(v,ctx[symbol]) for k,v in policies.items()}
            cells[f"{symbol}/{horizon}m"] = result
    selection = sum(cell["selection"]["Filtered"]["Observations"] for cell in cells.values())
    if selection != receipt["phases"]["selection"]["efficientContinuationObservations"]:
        raise ValueError("PVE1_CORRECTION_ORIGINAL_FILTER_PARITY")
    result = dict(Study="PVE1_CONTINUATION_BENCHMARK_CORRECTION", OriginalRunId=receipt["executionWorkflowRunId"],
                  OriginalReceiptSha256=sha256(original).hexdigest(), OriginalPublicJsonSha256=receipt["originalPublicJsonSha256"],
                  OriginalSources=p["sources"], OriginalProtocolSha256=PROTOCOL_SHA,
                  ProtocolSha256=sha256(Path("research/PVE1_BENCHMARK_CORRECTION.md").read_bytes()).hexdigest(),
                  SelectionFilteredObservations=selection, MinimumActiveWeeks=8, Cells=cells,
                  PortfolioExecuted=False, IndependentConfirmation=False, BrokerRequests=0, OrdersSubmitted=0, CloudActivated=False)
    Path("pve1-benchmark-correction-public.json").write_text(json.dumps(result,indent=2)+"\n")


if __name__ == "__main__":
    main()
