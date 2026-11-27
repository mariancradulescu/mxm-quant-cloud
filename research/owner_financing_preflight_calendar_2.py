"""Preventive conditional funding evidence plan and immutable report audit.
No policy rerun, cash settlement, broker request or historical tariff certification.
Official calendar semantics: https://help.ctrader.com/open-api/model-messages/
"""
import argparse,json,os
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

DAY=86400000
EARLIER=(15157818327,45902423354,'8916d4536d565133a0c0a42c61ac3cb54785083db5e35fcddd567367384ea28d')
GEOMETRY=(15157252267,45902750757,'3e4c73bdeaea7614dc76f2d2df2a3a9d87339cade0de8dcf4bef457946f74d8c')
CACHE=(15156872074,45902423354,'0a24aa5f98949f49dbeadf6f2c1eb76c101eda979190074320db5d79c58d34f3')

def weekend(at):
    return datetime.fromtimestamp(at/1000,timezone.utc).weekday()>=5

def calendar_status(at,weekends):
    if type(weekends) is not bool:return 'UNKNOWN_CALENDAR'
    return 'NO_WEEKEND_SWAP_CONDITIONAL' if not weekends and weekend(at) else 'ELIGIBLE_CLOCK'

def valid_schedule(c,terms):
    minute=c.get('SwapTimeUtcMinute')
    skip=c.get('SkipSwapPeriods')
    return (terms.get('AccountSwapFree') is False and c.get('SwapPeriodHours')==24
        and type(c.get('ChargeSwapAtWeekends')) is bool and type(skip) is int and skip>=0
        and type(minute) is int and 0<=minute<1440)

def clocks(start,end,minute):
    first=start//DAY*DAY+minute*60000
    if first<start:first+=DAY
    return range(first,end+1,DAY)

def preflight(source,valid_mark):
    entries={x['Market']['Name']:x for x in source['Markets']}
    tapes={x['Name']:x for x in source['Tapes']}
    quotes={name:{q['At']:q for q in t['FundingQuotes']} for name,t in tapes.items()}
    for name,t in tapes.items():
        if len(quotes[name])!=len(t['FundingQuotes']):raise ValueError('PREFLIGHT_DUPLICATE_CLOCK')
    targets={};local=[];excluded=0;covered=0
    for name,entry in entries.items():
        terms=entry['Market'].get('DatedDevelopment') or {}
        c=terms.get('Contract') or {}
        if not valid_schedule(c,terms):
            local.append(dict(Symbol=name,Status='UNRESOLVED_CONTRACT_SCHEDULE'));continue
        rate=[c.get('LongSwap'),c.get('ShortSwap')]
        if any(x is None for x in rate) or c.get('TripleSwapWeekday') not in range(8) or c.get('SwapCalculationType') not in (0,1,2):
            local.append(dict(Symbol=name,Status='UNRESOLVED_CONTRACT_RATE'));continue
        for at in clocks(source['Start'],source['End'],c['SwapTimeUtcMinute']):
            if calendar_status(at,c['ChargeSwapAtWeekends'])!='ELIGIBLE_CLOCK' or all(Decimal(str(x))==0 for x in rate):
                excluded+=1;continue
            currency=c.get('QuoteAsset')
            route=[] if currency=='EUR' else source['Routes'].get(currency)
            if route is None or (currency!='EUR' and not route):
                local.append(dict(Symbol=name,At=at,Status='UNRESOLVED_CONVERSION_ROUTE'));continue
            req=[(name,False)] if c['SwapCalculationType']==1 else []
            req.extend((hop['Symbol'],True) for hop in route)
            for symbol,both in req:
                if symbol not in quotes:
                    local.append(dict(Symbol=name,At=at,Status='UNCOLLECTED_TAPE',RequiredSymbol=symbol));continue
                if valid_mark(quotes[symbol].get(at),at,both):
                    covered+=1;continue
                # Exact source tuple dedup; FX evidence must be valid as a pair.
                for side in ('BID','ASK') if both else ('BID',):
                    targets.setdefault((symbol,at,side),set()).add(name)
    return dict(Targets=[dict(Symbol=s,At=a,Side=d,DependentSymbols=sorted(n))
        for (s,a,d),n in sorted(targets.items())],LocalUnresolved=local,
        ExistingMarkUses=covered,ConditionalExcludedClocks=excluded,
        TermsBasis='ARCHIVED_CONDITIONAL_CONTRACT_NOT_HISTORICAL_TARIFF',
        Orders=0,CloudActivated=False,SourceBrokerRequests=0)

def classify_window(w):
    if w.get('AccountSwapFree') is not False or w.get('SwapPeriodHours')!=24:
        return [(q,'UNKNOWN_CONTRACT') for q in w['ChargeEvidence']]
    skip=w.get('SkipSwapPeriods')
    if type(skip) is not int or skip<0 or type(w.get('ChargeSwapAtWeekends')) is not bool:
        return [(q,'UNKNOWN_CONTRACT') for q in w['ChargeEvidence']]
    out=[]
    for q in sorted(w['ChargeEvidence'],key=lambda x:x['At']):
        status=calendar_status(q['At'],w['ChargeSwapAtWeekends'])
        if status=='ELIGIBLE_CLOCK':
            if skip:
                skip-=1;status='SKIPPED_PERIOD_CONDITIONAL'
            elif not w.get('ContractRateAvailable'):
                status='UNKNOWN_RATE'
            elif (w.get('SwapCalculationType')==1 and not q['HasRolloverBid']) or not q['HasRolloverConversion']:
                status='MISSING_EVIDENCE_ON_ELIGIBLE_CLOCK'
            else:status='NO_REPORTED_REQUIRED_MARK_GAP'
        out.append((q,status))
    return out

def report_audit(root,expected):
    from .merge_eur_scenarios import read
    summary=read(root/'summary.json')
    if summary['SharedPortfolioEvaluations']!=expected or summary['Orders']!=0 or summary['CloudActivated']:
        raise ValueError('PREFLIGHT_ORIGINAL_REPORT_SCOPE')
    counts={};groups={};margin=[];windows=0;books=0
    for f in sorted(root.glob('S[012].json')):
        data=read(f)
        if data['SourceSha256']!=summary['SourceSha256'] or data['ProtocolSha256']!=summary['ProtocolSha256']:
            raise ValueError('PREFLIGHT_ORIGINAL_REPORT_IDENTITY')
        for b in data['CommonBooks']:
            books+=1
            fraction=b['Result'].get('MaxSampledHeldPendingMarginFraction')
            if fraction is not None and fraction>Decimal('.70'):
                margin.append(dict(Scenario=f.stem,Book=b['Id'],Fraction=fraction))
            for w in b['Details']['OutstandingFunding']:
                windows+=1
                for q,status in classify_window(w):
                    counts[status]=counts.get(status,0)+1
                    key=(w['Symbol'],q['At'],status,q['HasRolloverBid'],q['HasRolloverConversion'])
                    groups[key]=groups.get(key,0)+1
    if books!=expected:raise ValueError('PREFLIGHT_BOOK_COUNT')
    return dict(OriginalSourceSha256=summary['SourceSha256'],Windows=windows,Books=books,
        ClockStatusCounts=counts,MarginExceedances=margin,
        DistinctClocks=[dict(Symbol=s,At=a,Status=t,HasBid=b,HasConversion=c,Occurrences=n)
          for (s,a,t,b,c),n in sorted(groups.items())],
        SettlementCertified=False,OriginalPolicyReruns=0)

def main():
    from .owner_earlier_lifecycle_digest_recovery import verified_download
    from .owner_pav1_market_time import restore_checkpoint
    from .owner_economic_mechanisms import valid_mark
    from .merge_eur_scenarios import read,exact_json
    from .verified_research_cache import sha
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    for spec,destination in ((EARLIER,'earlier-closed-original'),(GEOMETRY,'geometry-closed-original'),(CACHE,'earlier-source-cipher')):
        verified_download(*spec,Path(destination))
    earlier=report_audit(Path('earlier-closed-original'),30)
    geometry=report_audit(Path('geometry-closed-original'),24)
    restore_checkpoint(Path('earlier-source-cipher'),a.work,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),
        str(CACHE[1]),earlier['OriginalSourceSha256'],source_only=True)
    source_path=a.work/'source.json'
    if sha(source_path)!=earlier['OriginalSourceSha256']:raise ValueError('PREFLIGHT_SOURCE_IDENTITY')
    plan=preflight(read(source_path),valid_mark)
    plan.update(SourceSha256=sha(source_path),SourceArtifact=CACHE[0],SourceArchiveSha256=CACHE[2])
    out=Path('funding-preflight-report');out.mkdir()
    (out/'report.json').write_text(exact_json(dict(Earlier=earlier,Geometry=geometry,Preventive=plan,
        OriginalPolicyReruns=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False))+'\n')
    print('FINANCING_PREFLIGHT',len(plan['Targets']),'DEDUPLICATED_TARGETS',
        earlier['Windows'],geometry['Windows'],'ORIGINAL_WINDOWS',flush=True)

if __name__=='__main__':main()
