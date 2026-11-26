"""Read-only decomposition of the rejected original; never reruns a policy."""
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import sys

def analyze(report):
    out=[]
    for scenario in report['Summary']['Results']:
        for detail in scenario['TrialDetails']:
            forecasts=detail.get('Forecasts',[])
            episodes=detail['Details']['Episodes']
            grouped=defaultdict(list)
            for e in episodes:grouped[(e['Symbol'],e['Family'],e['Side'],e['CloseAt'])].append(e)
            admitted=[];unmatched=[]
            for f in forecasts:
                rows=grouped.get((f['Symbol'],f['Family'],f['Side'],f['ClosedAt']),[])
                if f['ClosedAt'] is None or len(rows)!=1:
                    unmatched.append(f);continue
                e=rows[0];payoff=f['Payoff'];scope=(payoff.get('PredictiveEvidence') or {}).get('Scope')
                factor=Decimal(e['Units'])/Decimal(f['Units'])
                admitted.append(dict(Symbol=f['Symbol'],Family=f['Family'],Side=f['Side'],Scope=scope,
                    EstimatedNetEur=payoff['NetMeanEur'],EstimatedAtFillVolumeEur=payoff['NetMeanEur']*factor,
                    RealizedNetEur=f['RealizedNetEur'],RealizedGrossEur=f['RealizedGrossEur'],
                    AdmissionUnits=f['Units'],FillUnits=e['Units'],AdmissionRiskEur=f['ReservedRiskEur'],
                    FillRiskEur=e['ReservedRiskAtFillEur'],AvailableValidationDays=(payoff.get('PredictiveEvidence') or {}).get('ValidationDays'),
                    ExitReason=e['ExitReason']))
            def summary(rows):
                rows=list(rows);known=[r for r in rows if r['RealizedNetEur'] is not None]
                return dict(Count=len(rows),EstimatedNetEur=sum((r['EstimatedNetEur'] for r in rows),Decimal(0)),
                    EstimatedAtFillVolumeEur=sum((r['EstimatedAtFillVolumeEur'] for r in rows),Decimal(0)),
                    RealizedNetEur=sum((r['RealizedNetEur'] for r in known),Decimal(0)) if len(known)==len(rows) else None,
                    RealizedGrossEur=sum((r['RealizedGrossEur'] for r in rows),Decimal(0)),
                    ReducedFillVolumes=sum(r['FillUnits']<r['AdmissionUnits'] for r in rows),
                    PooledErrorScope=sum(bool(r['Scope'] and 'POOLED_OUT_OF_TIME' in r['Scope']) for r in rows))
            by={}
            for field in ('Symbol','Family','Scope','ExitReason'):
                by[field]={str(k):summary(r for r in admitted if r[field]==k) for k in sorted({r[field] for r in admitted},key=str)}
            out.append(dict(Stress=scenario['SpreadMultiplier'],Id=detail['Id'],Matched=summary(admitted),
                ForecastReceiptsWithoutCompletedMatch=len(unmatched),By=by))
    return dict(Study='REJECTED_ORIGINAL_FINANCIAL_FORECAST_ATTRIBUTION_1',
        OriginalStudy=report['Summary']['Study'],OriginalProtocolSha256=report['Summary']['ProtocolSha256'],
        OriginalSourceSha256=report['Summary']['SourceSha256'],Results=out,
        Interpretation='Fill-volume rescaling is diagnostic, not a replacement calibrated forecast. Remaining error includes entry selection, regime transfer and lifecycle mismatch; causal attribution requires new controlled comparisons.',
        Orders=0,CloudActivated=False,OriginalRerun=False)

if __name__=='__main__':
    from .merge_eur_scenarios import exact_json
    result=analyze(json.loads(Path(sys.argv[1]).read_bytes(),parse_float=Decimal))
    Path(sys.argv[2]).write_text(exact_json(result)+'\n')
