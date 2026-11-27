import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import owner_native_funding_recovery_2 as recovery
from .ctrader_proto import OpenApiMessages_pb2 as m

class PreventiveRecovery(unittest.TestCase):
    def test_uncharged_future_clock_is_bound_into_capture_scope(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,GITHUB_RUN_ID='7'):
            root=Path(tmp)
            past=dict(Symbol='AAPL.US',At=1000,Side='BID')
            future=dict(Symbol='EURUSD',At=2000,Side='ASK')
            recovery.write(root/'native-0.json',dict(Targets=[past]))
            recovery.write(root/'preventive-0.json',dict(Plan=dict(Targets=[future])))
            p=dict(Study=recovery.STUDY,RunId='7',LookbackMs=345600000,Targets=[past,future],
                Sources=[dict(ReportSha256=recovery.sha(root/'native-0.json'),
                              PreventiveSha256=recovery.sha(root/'preventive-0.json'))],Orders=0,CloudActivated=False)
            recovery.write(root/'plan.json',p)
            with patch.object(recovery,'PLAN',root):
                self.assertEqual(len(recovery.checked_plan()[0]['Targets']),2)
                p['Targets']=[past];recovery.write(root/'plan.json',p)
                with self.assertRaisesRegex(Exception,'RECOVERY2_PLAN_SCOPE'):recovery.checked_plan()

    def test_one_prefix_recovers_two_closed_market_clocks_without_two_requests(self):
        class Journal:
            calls=0
            def query(self,req):
                self.calls+=1
                r=m.ProtoOAGetTickDataRes(ctidTraderAccountId=7,hasMore=True)
                r.tickData.add(timestamp=1000,tick=10000000)
                r.tickData.add(timestamp=-10,tick=-1)
                return r,None,None
        journal=Journal()
        targets=[dict(Symbol='AAPL.US',At=at,Side='BID') for at in (1200,1300)]
        with patch('research.owner_eur_archive_funding_2.plan_ids',return_value={'AAPL.US':1}):
            rows=recovery.collect(journal,7,dict(Targets=targets,LookbackMs=345600000))
        self.assertEqual(journal.calls,1)
        self.assertEqual({r['Witness']['SearchThrough'] for r in rows},{1200,1300})
        self.assertTrue(all(r['Witness']['At']==1000 for r in rows))

    def test_unresolved_witness_never_becomes_zero_or_overwrites_existing_price(self):
        at=1_000_000_000
        source=dict(Tapes=[dict(Name='AAPL.US',FundingQuotes=[])])
        row=dict(Target=dict(Symbol='AAPL.US',At=at,Side='BID'),Witness=dict(Status='NO_RETURNED_TICK'))
        registry=dict(Study=recovery.STUDY,SourceSha256=['a'*64],Rows=[row],Orders=0,CloudActivated=False)
        self.assertEqual(recovery.apply_recovered_registry(source,registry,'a'*64)['UnresolvedWitnesses'],1)
        self.assertEqual(source['Tapes'][0]['FundingQuotes'],[])
        row['Witness']=dict(Status='AUTHENTIC_LATEST_PREFIX',SearchFrom=at-345600000,SearchThrough=at,
            At=at-1000,Price='200',PrefixNewestFirst=True,LeadingTimestampComplete=True)
        self.assertEqual(recovery.apply_recovered_registry(source,registry,'a'*64)['Filled'],1)
        row['Witness']=dict(row['Witness'],Price='201')
        with self.assertRaisesRegex(Exception,'RECOVERY2_EXISTING_PREFIX_CONFLICT'):
            recovery.apply_recovered_registry(source,registry,'a'*64)

    def test_original_decimal_string_quote_is_retained_under_new_witness_metadata(self):
        at=1_000_000_000
        q=dict(At=at,RequestedCoverage=True,BidAt=at-1000,Bid='200')
        source=dict(Tapes=[dict(Name='AAPL.US',FundingQuotes=[q])])
        w=dict(Status='AUTHENTIC_LATEST_PREFIX',SearchFrom=at-345600000,SearchThrough=at,
            At=at-1000,Price='200',PrefixNewestFirst=True,LeadingTimestampComplete=True)
        registry=dict(Study=recovery.STUDY,SourceSha256=['a'*64],Rows=[dict(
            Target=dict(Symbol='AAPL.US',At=at,Side='BID'),Witness=w)],Orders=0,CloudActivated=False)
        self.assertEqual(recovery.apply_recovered_registry(source,registry,'a'*64)['Retained'],1)
        self.assertNotIn('LatestBidPrefix',q)

if __name__=='__main__':unittest.main()
