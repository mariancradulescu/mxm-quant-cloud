"""System constraints from frozen public receipts; no market/model replay.

This is arithmetic on disclosed cost summaries, not a new economic experiment.
Run with --write once to materialize the report, otherwise verify exact bytes.
"""
import hashlib
import json
import sys
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/SYSTEM_ECONOMIC_FEASIBILITY.json'
SOURCES = {
    'BDP1': ('docs/BDP1_AUTHENTIC_RESULT.json', 'ba33bc4bdd756db85c1c017c6c1f39241facd94408901787ff4db4bd53871cdb'),
    'AIP1': ('docs/AIP1_AUTHENTIC_RESULT.json', 'ed23b6d7ce289ce1eeede6626ef8d9bce09d2cfbdb59fd6fe4b4493a75a4bd3c'),
    'CCP1': ('docs/CCP1_AUTHENTIC_PREFLIGHT.json', None),
}


def number(x):
    return format(x.quantize(Decimal('0.000000000001')), 'f')


def build():
    with localcontext() as context:
        context.prec = 60
        return _build()


def _build():
    registry = json.loads((ROOT / 'research/evidence_registry.json').read_text())
    sources, provenance = {}, []
    for study, (name, pinned) in SOURCES.items():
        raw = (ROOT / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        expected = pinned or registry['frozenFileSha256'][name]
        if digest != expected:
            raise ValueError('FROZEN_RECEIPT_HASH_MISMATCH: ' + name)
        sources[study] = json.loads(raw)
        provenance.append(dict(study=study, path=name, sha256=digest))
    rows = []
    for study in ('BDP1', 'AIP1'):
        for c in sources[study]['CostContexts']:
            # Max bps and max notional need not belong to the same observation.
            # Their product is an envelope of the captured friction scenarios,
            # NOT an actually paid fee or a lower bound on future costs.
            bps = Decimal(c['RoundTripBps'])
            notional = Decimal(c['MinimumNotionalEur'])
            margin = Decimal(c['CurrentMinimumMarginEur'])
            if min(bps, notional, margin) <= 0 or c['Samples'] <= 0:
                raise ValueError('INVALID_PUBLIC_COST_CONTEXT')
            cost = notional * bps / 10000
            rows.append(dict(
                study=study, symbol=c['Symbol'], samples=c['Samples'],
                currentMinimumMarginEur=number(margin),
                maximumCapturedMinimumNotionalEur=number(notional),
                baseRoundTripScenarioBps=number(bps),
                baseRoundTripFrictionEnvelopeEur=number(cost),
                frictionFor21IdenticalMinimumTripsEur=number(21 * cost),
                frictionFor21IdenticalMinimumTripsPctInitialCapital=number(100 * 21 * cost / 200),
                primary2xFrictionFor21IdenticalMinimumTripsEur=number(42 * cost),
                zeroGrossFrictionExhaustionTripsTo60Eur=number(60 / cost),
                initialStaticMarginAndOneFrictionHeadroomEur=number(200 - margin - cost),
                at140EquityStaticMarginAndOneFrictionHeadroomEur=number(140 - margin - cost),
                oneMinimumUnitCapacityAtInitialUnderStaticScenario=margin + cost < 200,
                oneMinimumUnitCapacityAt140UnderStaticScenario=margin + cost < 140,
            ))
    ccp = sources['CCP1']
    capacity = [r for r in ccp['Rows'] if r.get('CurrentInitialCapitalCapacity')]
    if len(capacity) != 24 or len(ccp['Rows']) != 86:
        raise ValueError('FROZEN_CCP1_RECEIPT_SHAPE_CHANGED')
    # Illustrative occupied-time identities only. Neither week length is declared
    # eligible; slot counts are hypothetical and confer no capital permission.
    throughput = [dict(
        illustrativeAvailableHours=hours,
        hypotheticalConstantFundedSlots=slots,
        maximumMeanOccupiedHoursFor21Trips=number(Decimal(hours * slots) / 21),
        assumesAllTripsOpenAndCloseInsideWindow=True,
        signalsOrActualCapacityMeasured=False,
    ) for hours in (40, 120) for slots in (1, 2, 5)]
    return dict(
        schema='mxm-system-economic-constraints-v1',
        authority='docs/OWNER_SPEC.md v2.0; OWNER continuation after PR50',
        sourceHead='0e956c409ccacf2f36e622564b5f13a95f543145',
        provenance=provenance,
        initialCapitalEur=200, drawdownFraction='0.30',
        initialPeakTo30PctDrawdownCashDistanceEur=60,
        hard21RequiredCompletedFinancedTripsPerEligibleWeek=21,
        illustrative52EligibleWeeksRequiredCompletedTrips=1092,
        illustrative52WeeksIs12CalendarMonths=False,
        costContextRows=rows,
        temporalCapacityIdentities=throughput,
        ccp1FrozenCurrentCapacity=dict(
            rows=len(capacity),
            positiveRawFundingRows=sum(Decimal(r['RawCarryPerOrdinaryChargeEur']) > 0 for r in capacity),
            rawFundingMinPerOrdinaryChargeEur=number(min(Decimal(r['RawCarryPerOrdinaryChargeEur']) for r in capacity)),
            rawFundingMaxPerOrdinaryChargeEur=number(max(Decimal(r['RawCarryPerOrdinaryChargeEur']) for r in capacity)),
            crossBasketNettingEvaluated=False,
        ),
        interpretations=[
            'Cost envelopes combine separately observed maximum bps and maximum notional, plus contemporaneous margin. They are cross-time scenarios, not historical executable portfolios.',
            'Base friction is two current-tariff commissions plus three observed spreads (spread plus declared slippage); primary2x is sensitivity, not additional measured cost.',
            '21 identical minimum trips is a standardized turnover scenario for every instrument, not standalone HARD21, recommendation, forecast or a portfolio allocation.',
            '60 EUR is 30% of the initial peak, not a fee budget or risk cap per trade. Gains offset costs; later peaks change the drawdown boundary. No time-to-ruin forecast follows.',
            '140 EUR is a stress point on the same initial capital path, not a deposit, restart or second backtest. Positive static headroom does not establish risk admission.',
            'No financing, changing spread, dynamic margin, adverse floating PNL, depth or fill probability is inferred from these summaries.',
            'Temporal identities bound occupation time for a hypothetical constant number of slots. Sessions, source gaps, holding duration and actual funding can reduce capacity.',
            'Diversification cannot create positive expected NET from an unchanged fixed mix of nonpositive expected NET legs; conditional selection and netting can change the problem and need new evidence.',
            'Frozen recipe rejection is not proof of market-wide or system-wide impossibility. No sufficiently supported distinct new economic hypothesis is admitted by this arithmetic.',
        ],
        newEconomicHypotheses=0, modelCalls=0, newBrokerRequests=0,
        closedStudyRescored=False, selectionChanged=False,
        fundedNetEur=None, independentEconomicEdge=False,
        hard21Proven=False, systemImpossibilityProven=False,
        continuousDrawdownCertified=False, productQualified=False,
        ordersSubmitted=0, cloudActivated=False,
    )


def main():
    raw = (json.dumps(build(), indent=2, sort_keys=True) + '\n').encode()
    if sys.argv[1:] == ['--write']:
        OUTPUT.write_bytes(raw)
    elif not sys.argv[1:]:
        if OUTPUT.read_bytes() != raw:
            raise ValueError('SYSTEM_FEASIBILITY_RECEIPT_NOT_REPRODUCIBLE')
    else:
        raise SystemExit('usage: python -m research.system_economic_feasibility [--write]')
    print('PASS frozen-receipt systemic constraint arithmetic; no new economic qualification')


if __name__ == '__main__':
    main()
