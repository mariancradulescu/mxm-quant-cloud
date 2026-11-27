"""Information-only path diagnostic on verified existing source; no original book replay."""
import argparse,subprocess
from pathlib import Path
from . import owner_controlled_recency as source
from .owner_monetary_reduce_common_book import REPLAY
from .merge_eur_scenarios import read
from .verified_research_cache import sha
from .decode import need
REGISTRY=Path('research/closed_path_information_1.json')
REPORT=Path('closed-path-report')
def check():
    p=read(REGISTRY)
    need(p['Study']=='MONETARY_CLOSED_PATH_INFORMATION_1' and p['Scopes']==['earlier','recent']
        and p['HorizonMinutes']==[15,30,60] and p['Orders']==0 and not p['CloudActivated']
        and not p['PortfolioEvaluated'],'CLOSED_PATH_REGISTRATION')
def evaluate(work,scope):
    check()
    source.prepare(work,scope)
    parent=read(source.REPORT/'source-receipt.json')
    REPORT.mkdir()
    out=REPORT/'path-information.json'
    subprocess.run(['dotnet',REPLAY,'--owner-closed-path-information',str(work/'net-plan.json'),
        str(work/'net-source.json'),str(work/'verified-protection'),str(out)],check=True)
    r=read(out)
    need(r['Study']=='MONETARY_CLOSED_PATH_INFORMATION_1' and r['SourceSha256']==parent['SourceSha256']
        and r['ProtocolSha256']==parent['ProtocolSha256'] and r['MarketCount']==(7 if scope=='earlier' else 29)
        and r['Results'] and not r['PortfolioEvaluated'] and not r['FundingIncluded']
        and r['Orders']==0 and not r['CloudActivated'],'CLOSED_PATH_REPORT_BINDING')
    (REPORT/'source-receipt.json').write_bytes((source.REPORT/'source-receipt.json').read_bytes())
def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','evaluate'])
    p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='check':check()
    else:
        need(a.scope is not None and a.work is not None,'CLOSED_PATH_SCOPE');evaluate(a.work,a.scope)
if __name__=='__main__':main()
