"""Read-only EUR feasibility from conserved receipts and bounded PR #264 diagnostics."""
import argparse
from decimal import Decimal
import gzip
from hashlib import file_digest
import json
from pathlib import Path

import numpy as np

from research import equity_clock_payoff as frozen

ROOT = Path(__file__).resolve().parents[1]
EQUITY = ROOT / "docs/EQUITY_CLOCK_PAYOFF_RESULT.json"
MARKETS = ROOT / "docs/MSP1_AUTHENTIC_CONDITIONAL_RESULT.json.gz"
D = Decimal


def digest(path):
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def availability(archive):
    bars, _ = frozen.read_archive(archive)
    ready, paths = frozen.make_panel(bars)
    model_complete, dual_complete, full_complete = [], [], []
    missing_probability = []
    no_decision = 0
    scheduled = 0
    for start in range(60, len(ready), 5):
        timed, pooled = frozen.scores(paths[start - 40:start, :, :, 0])
        for day in range(start, start + 5):
            for clock in range(len(frozen.CLOCKS)):
                scheduled += 1
                eligible = ready[day, clock] & np.isfinite(timed[clock]) & np.isfinite(pooled)
                if not eligible.any():
                    no_decision += 1
                    continue
                current = paths[day, clock, :, 0]
                selected = current[np.argmax(np.where(eligible, timed[clock], -np.inf))]
                reference = current[np.argmax(np.where(eligible, pooled, -np.inf))]
                unknown = ~np.isfinite(current[eligible])
                missing_probability.append(float(unknown.mean()))
                if np.isfinite(selected):
                    model_complete.append(selected)
                    if np.isfinite(reference):
                        dual_complete.append((selected, reference))
                        if not unknown.any():
                            full_complete.append((selected, reference))
    original = json.loads(EQUITY.read_bytes())
    if (len(full_complete) != original["overall"]["paired_clocks"]
            or len(model_complete) != original["available_case"]["clocks"]
            or not np.isclose(np.mean(model_complete), original["available_case"]["gross_bps"],
                              rtol=0, atol=1e-12)
            or not np.isclose(np.mean(full_complete, axis=0)[0],
                              original["overall"]["model"]["gross_bps"], rtol=0, atol=1e-12)):
        raise ValueError("Frozen availability or payoff parity failed")

    def paired(pairs):
        array = np.asarray(pairs)
        return {
            "clocks": len(pairs),
            "model_gross_bps": float(array[:, 0].mean()),
            "pooled_gross_bps": float(array[:, 1].mean()),
            "increment_bps": float(np.mean(array[:, 0] - array[:, 1])),
        }

    return {
        "source_receipt_sha256": digest(EQUITY),
        "source_archive_sha256": frozen.ARCHIVE_SHA,
        "scheduled": scheduled, "no_decision": no_decision,
        "decision_eligible": scheduled - no_decision,
        "model_future_missing": scheduled - no_decision - len(model_complete),
        "model_available": {"clocks": len(model_complete), "gross_bps": float(np.mean(model_complete))},
        "model_and_pooled_complete": paired(dual_complete),
        "original_uniform_complete_comparison": paired(full_complete),
        "removed_only_by_uniform_requirement": len(dual_complete) - len(full_complete),
        "mean_uniform_missing_probability_given_eligible_clock": float(np.mean(missing_probability)),
        "unconditional_uniform_return_bps": None,
        "gross_eur": None, "central_net_eur": None, "adverse_net_eur": None,
        "classification": "POSTCLOSURE_AVAILABILITY_DIAGNOSTIC_NO_POLICY_CHANGE",
    }


def euro_screen():
    with gzip.open(MARKETS, "rt") as source:
        data = json.load(source)
    if not all(a["rawAccountAndBarsReconstructed"] for a in data["SourceAudit"]):
        raise ValueError("Original market readback missing")
    amplitude = {a["Symbol"]: a for a in data["Amplitude"]
                 if a["Minutes"] == 15 and a["HorizonMinutes"] == 60}
    context_paths = [ROOT / "docs" / f"{study}_AUTHENTIC_RESULT.json"
                     for study in ("BDP1", "AIP1")]
    base_context = {}
    for path in context_paths:
        evidence = json.loads(path.read_bytes())
        if not evidence["RawReadbackMatched"]:
            raise ValueError("Cost context original readback missing")
        base_context.update({row["Symbol"]: row for row in evidence["CostContexts"]})
    contracts_path = ROOT / "docs/SEM1_AUTHENTIC_PUBLIC_RECEIPT_20261112.json"
    contracts = json.loads(contracts_path.read_bytes())
    result = {}
    for row in sorted(data["CostModel"], key=lambda x: x["Symbol"]):
        name = row["Symbol"]
        notional = D(row["MinimumNotionalEur"])
        margin = D(row["CurrentMinimumMarginEur"])
        move = amplitude[name]
        median = D(move["MedianAbsMoveBps"])
        tail = D(move["P90AbsMoveBps"])
        mean_spread = D(row["MeanObservedSpreadBps"])
        adverse_spread = max(D(row["P90ObservedSpreadBps"]),
                             mean_spread + D("2.5") * D(row["DateMeanSpreadSe"]))
        context = base_context[name]
        if (abs(D(context["MinimumNotionalEur"]) - notional) > D("0.000001")
                or D(context["CurrentMinimumMarginEur"]) != margin):
            raise ValueError(f"Reference cost context identity mismatch: {name}")
        base_cost = D(context["RoundTripBps"])
        later_contract = contracts["CurrentContractsBySymbol"].get(name)
        later_margin = contracts["ObservedMarginGridBySymbol"].get(name)
        mean_commission = D(row["MeanCurrentCommissionRoundTripBps"])
        central_partial = D("1.5") * mean_spread + mean_commission
        adverse_partial = D(2) * adverse_spread + mean_commission

        def euros(bps):
            return round(float(notional * bps / 10000), 8)

        result[name] = {
            "source_reference_minimum_notional_eur": float(notional),
            "source_minimum_margin_eur": float(margin),
            "nominal_eur_free_after_one_minimum_margin_before_risk": float(D(300) - margin),
            "source_quote_contexts": row["Samples"],
            "source_distinct_quote_dates": row["DistinctDates"],
            "development_move_labels": move["KnownDevelopmentMoves"],
            "median_absolute_move_bps": float(median),
            "p90_absolute_move_bps": float(tail),
            "median_absolute_move_eur_at_reference_notional": euros(median),
            "p90_absolute_move_eur_at_reference_notional": euros(tail),
            "partial_central_friction_eur": euros(central_partial),
            "partial_adverse_friction_eur_using_mean_commission": euros(adverse_partial),
            "illustrative_gross_bps_for_one_euro_after_partial_adverse_friction":
                round(float(D(10000) / notional + adverse_partial), 8),
            "original_base_cost_envelope_eur": euros(base_cost),
            "twice_original_base_cost_stress_eur": euros(2 * base_cost),
            "gross_bps_for_one_euro_after_twice_original_base_cost":
                round(float(D(10000) / notional + 2 * base_cost), 8),
            "margin_plus_twice_base_cost_below_210_eur_static":
                margin + notional * 2 * base_cost / 10000 <= D(210),
            "physical_minimum_units_in_msp1_public_cost_row": None,
            "later_sem1_original_contract_context": (
                {"physical_minimum_units": later_contract["MinimumUnits"],
                 "volume_step_units": later_contract["VolumeStepUnits"],
                 "observed_at_utc_ms": later_contract["ObservedAtUtcMs"],
                 "minimum_buy_sell_margin_eur": later_margin[0]}
                if later_contract is not None else None
            ),
            "source_time_matched_gross_eur": None,
            "central_net_eur": None, "adverse_net_eur": None,
        }
    return {
        "source_receipt_sha256": digest(MARKETS), "source_run": data["ExecutionRunId"],
        "source_market_runs": data["Protocol"]["sourceRuns"],
        "reference_cost_context_sha256": {p.name: digest(p) for p in context_paths},
        "later_contract_context_sha256": digest(contracts_path),
        "static_equity_scenario_eur": 210,
        "stress_definition": "2x conserved BDP1/AIP1 base round-trip cost proxy, no historical bound",
        "research_priorities": {
            "next_evidence": "GER40 and NAS100: paired source and as-of contract evidence for a distinct session-overlap mechanism",
            "comparators": "US500 and AUS200: lower minimum margin, smaller EUR move scale",
            "higher_capital_sensitivity": "XAUUSD and JPN225: large moves, higher minimum margin",
            "expanded_equity_universe": "17 US-24: minimum-margin probes only for this cohort; defer ranking in EUR pending original own-symbol terms and contemporaneous quote/FX evidence",
        },
        "capital_reference_eur": 300, "horizon_minutes": 60,
        "classification": "REFERENCE_NOTIONAL_AMPLITUDE_AND_PARTIAL_FRICTION",
        "friction_excludes": ["diffusion proxy", "commission maximum for adverse",
                              "conversion wedge", "funding"],
        "diagnostic_one_euro_target_is_not_an_admission_threshold": True,
        "markets": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = {
        "availability": availability(args.archive),
        "eur_economic_preflight": euro_screen(),
        "new_broker_requests": 0, "orders_submitted": 0, "cloud_activated": False,
        "funded_round_trips": 0, "independent_confirmation": False,
    }
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
