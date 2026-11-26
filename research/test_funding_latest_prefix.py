import unittest,json,os,subprocess,tempfile
from pathlib import Path
from .owner_funding_prefix_settlement import latest
from .ctrader_proto import OpenApiMessages_pb2 as m

class LatestPrefix(unittest.TestCase):
    def response(self,more=True,rows=((1000,10000000),(-10,-1))):
        r=m.ProtoOAGetTickDataRes(ctidTraderAccountId=7,hasMore=more)
        for at,price in rows:r.tickData.add(timestamp=at,tick=price)
        return r
    def test_omitted_older_ticks_do_not_hide_a_newer_first_tick(self):
        q=latest(self.response(),7,0,1200)
        self.assertEqual(q['Status'],'AUTHENTIC_LATEST_PREFIX')
        self.assertEqual(q['At'],1000)
        self.assertTrue(q['HasOlderOmittedTicks'])
    def test_conflict_and_truncated_leading_timestamp_stay_unknown(self):
        self.assertEqual(latest(self.response(rows=((1000,10000000),(0,1))),7,0,1200)['Status'],'LATEST_TIMESTAMP_AMBIGUOUS')
        self.assertEqual(latest(self.response(rows=((1000,10000000),)),7,0,1200)['Status'],'LATEST_TIMESTAMP_AMBIGUOUS')
    def test_account_and_empty_response_do_not_produce_a_price(self):
        self.assertEqual(latest(self.response(),8,0,1200)['Status'],'UNRESOLVED_RESPONSE')
        self.assertEqual(latest(self.response(False,()),7,0,1200)['Status'],'NO_RETURNED_TICK')
    def test_preventive_planner_accepts_a_verified_price_prefix_with_stricter_fx_age(self):
        from .owner_economic_mechanisms import valid_mark
        at=1_000_000_000
        point=dict(Status='AUTHENTIC_LATEST_PREFIX',SearchFrom=at-345600000,SearchThrough=at,
                   At=at-266400000,Price='200',PrefixNewestFirst=True,LeadingTimestampComplete=True)
        q=dict(RequestedCoverage=False,LatestBidPrefix=point,LatestAskPrefix=dict(point,Price='201'))
        self.assertTrue(valid_mark(q,at,False))
        self.assertFalse(valid_mark(q,at,True))

class NativeSettlement(unittest.TestCase):
    def fixture(self,scale=1):
        friday=1788559200000;monday=1788818400000
        def point(at,price,age):return dict(Status='AUTHENTIC_LATEST_PREFIX',SearchFrom=at-345600000,
            SearchThrough=at,At=at-age,Price=str(price),PrefixNewestFirst=True,LeadingTimestampComplete=True)
        c=dict(Symbol='AAPL.US',QuoteAsset='USD',ObservedAtUtcMs=friday-10000000,MinimumUnits=.1,
            VolumeStepUnits=.1,MaximumUnits=100,LotUnits=1,CommissionType=2,PreciseRateWire=0,
            MinimumCommissionType=2,PreciseMinimumWire=0,PnlConversionFeeBps=0,SwapCalculationType=1,
            LongSwap=-3,ShortSwap=-3,PipPosition=2,SwapPeriodHours=24,SwapTimeUtcMinute=1320,
            TripleSwapWeekday=5,ChargeSwapAtWeekends=False,SkipSwapPeriods=0,OriginalBrokerAuthenticated=True)
        w=dict(PositionId='SYNTH',Symbol='AAPL.US',Side=-1,Units=.1,FromExclusive=friday-3000000,
               ClosedAt=monday+1000000,BookedSignedEur=0)
        return dict(Study='SYNTHETIC',RegistrySha256='a'*64,OriginalRun=1,OriginalArchiveSha256='b'*64,
            OriginalProtocolSha256='c'*64,OriginalSourceSha256='d'*64,Contract=c,
            Account=dict(accountSwapFree=False,accountType=0,moneyDigits=2),PriceDigits=2,Window=w,
            Episode=dict(PositionId='SYNTH',OpenAt=w['FromExclusive'],CloseAt=w['ClosedAt'],NetEur=None,
                         GrossEur=.5,ExplicitExecutionCostsEur=.1),OriginalCashEur=299.9,KnownOtherNetEur=-.5,
            Charges=[dict(At=t,Bid=point(t,200*scale,7201000 if t==friday else 266400000),
                          FxBid=point(t,1.1,1000),FxAsk=point(t,1.11,1000)) for t in (friday,monday)],EconomicPolicyReruns=0)
    def test_native_rounding_requires_real_inputs_and_is_not_a_zero_default(self):
        dll='research/NativeFundingSettlement/bin/Release/net8.0/NativeFundingSettlement.dll'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            amounts=[]
            for i,scale in enumerate((1,1000)):
                source=root/f'in{i}.json';out=root/f'out{i}.json';source.write_text(json.dumps(self.fixture(scale)))
                subprocess.run(['dotnet',dll,str(source),str(out)],check=True,capture_output=True)
                r=json.loads(out.read_bytes());amounts.append(r['FinancingSignedEur'])
                self.assertFalse(r['OriginalDecisionsReplayed'])
            self.assertEqual(amounts[0],0)
            self.assertLess(amounts[1],0)
