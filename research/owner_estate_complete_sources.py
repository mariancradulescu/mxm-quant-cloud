"""Complete the actual 106-name estate: missing P05 shards plus original HXC/XMH context."""
import base64,gc,os
from decimal import Decimal
from pathlib import Path
from . import p05_source_economic_gate as p05
from . import mde1_cumulative_original_native as mde
from . import source_history_universe as src
from . import owner_estate_recovery as estate
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_official_breadth_spans import normalize_with_quarantine
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .decode import need
from .ctrader_proto import OpenApiMessages_pb2 as messages

def declared_period_rows(rows,tf,zero_close=False):
    width=src.PERIODS[tf]*60000;out=[]
    for row in rows:
        t=int(row[0]);need(int(row[1])==(t if zero_close else t+width),'COMPLETE_ESTATE_ORIGINAL_BAR_CLOCK')
        out.append(dict(OpenAt=t,CloseAt=t+width,Open=Decimal(int(row[2])).scaleb(-5),
            High=Decimal(int(row[3])).scaleb(-5),Low=Decimal(int(row[4])).scaleb(-5),
            Close=Decimal(int(row[5])).scaleb(-5),TickVolume=int(row[6])))
    return out

def extend(root,work,registration):
    work.mkdir(mode=0o700);spec=registration['AdditionalEstateSources'];key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
    def fetch(a,dest):verified_download(a['Artifact'],a['Run'],a['Sha256'],dest)
    fetch(spec['P05Public'],work/'p05-public');fetch(spec['P05Sealed'],work/'p05-sealed')
    receipt=read(work/'p05-public/receipt.json')
    need(sha(work/'p05-public/receipt.json')==registration['P05ReceiptSha256'] and
        str(receipt['runId'])==p05.RUN and receipt['ordersSubmitted']==0 and not receipt['cloudActivated'] and
        len(receipt['sources'])==76,'COMPLETE_ESTATE_P05_RECEIPT')
    roster_shard=next(x for x in receipt['sources'] if x['kind']=='ROSTER')
    roster=p05._roster(p05._load_sealed(roster_shard,work/'p05-sealed',key));proof=[];names=set()
    for shard in receipt['sources']:
        if shard['kind']!='MARKET':continue
        rows=p05._load_sealed(shard,work/'p05-sealed',key)
        for record in rows[1:]:
            if record.get('reqType')=='ProtoOAGetTrendbarsReq':
                req=messages.ProtoOAGetTrendbarsReq();req.ParseFromString(base64.b64decode(record['req'],validate=True))
                need(src.original_account(req.ctidTraderAccountId),'COMPLETE_ESTATE_P05_ORIGINAL_ACCOUNT')
        sid,bars=p05._bars_from_original(rows[1:]);need(sid in roster,'COMPLETE_ESTATE_P05_SYMBOL')
        name=roster[sid];published=receipt['marketCoverage'][name];counts={}
        for tf,values in bars.items():
            need(len(values)==published['timeframes'][tf]['bars'],'COMPLETE_ESTATE_P05_ORIGINAL_ROWS')
            # The old raw helper intentionally decoded with duration0; restore
            # the authenticated request's declared period before using close time.
            raw=p05.closed_at_source_cutoff(list(values.values()),src.PERIODS[tf])
            normalized=declared_period_rows(raw,tf,zero_close=True)
            normalized,quality=estate.merge_series(normalized)
            estate.save_series(root,name,tf,normalized,'P05-'+shard['name'])
            counts[tf]=dict(Raw=len(values),Closed=len(normalized),Quarantine=quality)
            if normalized:names.add(name)
        proof.append(dict(Symbol=name,Shard=shard,Periods=counts));del rows,bars;gc.collect()
    old_captured=mde.CAPTURED.copy()
    try:
        for label,run in (('XMH2',mde.XMH_RUN),('HXC1',mde.HXC_RUN)):
            folder=work/label;fetch(spec[label],folder)
            config=list(mde.CAPTURED[run]);config[0]=str(folder);mde.CAPTURED[run]=tuple(config)
            _,bundle,verified,digest=mde._one_original(run,key)
            for tag,rows in bundle['bars'].items():
                symbol,tf=tag.rsplit('/',1)
                if tf not in src.PERIODS:continue
                normalized=declared_period_rows(rows,tf)
                normalized,quality=estate.merge_series(normalized)
                estate.save_series(root,symbol,tf,normalized,label+'-'+run)
            proof.append(dict(Source=label,Archive=spec[label],CiphertextSha256=digest,Readback=verified))
            del bundle;gc.collect()
    finally:mde.CAPTURED.clear();mde.CAPTURED.update(old_captured)
    provenance=root.parent/'older/estate-provenance.json';p=read(provenance)
    p['AdditionalOriginalSources']=proof;p['P05ClosedHistorySymbols']=sorted(names)
    p['OriginalInventoryReconciliation']=dict(Expected106=registration['HistoricalUniverse106'],
        Basis='Original 90-name source census plus verified eight-market universe and eight-market continuation; progressive61 overlap, no additive universe claim')
    provenance.write_text(exact_json(p)+'\n')
    print('COMPLETE_ESTATE_P05_HXC_XMH_VERIFIED',len(names),flush=True)
