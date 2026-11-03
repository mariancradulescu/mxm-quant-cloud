import base64,copy,unittest
from .joint_quote_extension import audit,CLOCKS,SCHEMA,UNIVERSE,m,e
from .guard import CaptureContractError

class QuoteExtensionEvidence(unittest.TestCase):
    def fixture(self):
        b=dict(schema=SCHEMA,source='Pepperstone-cTrader-OpenAPI',readOnly=True,clocks=list(CLOCKS),symbols={},raw=[])
        def raw(q,r):
            b['raw'].append(dict(type=type(r).__name__,protobuf=base64.b64encode(r.SerializeToString()).decode(),
                requestType=type(q).__name__,requestProtobuf=base64.b64encode(q.SerializeToString()).decode()))
            return len(b['raw'])-1
        for symbol in UNIVERSE:
            sid=len(b['symbols'])+1
            margin=m.ProtoOAExpectedMarginRes(ctidTraderAccountId=1,moneyDigits=2)
            margin.margin.add(volume=100000,buyMargin=3000,sellMargin=3000)
            ix=raw(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=1,symbolId=sid,volume=[100000]),margin)
            row=dict(symbolId=sid,contract=dict(minVolume=100000,stepVolume=100000,maxVolume=1000000),marginRawIndex=ix,quotes={})
            for t in CLOCKS:
                indices=[]
                for side in (e.BID,e.ASK):
                    indices.append(raw(m.ProtoOAGetTickDataReq(ctidTraderAccountId=1,symbolId=sid,type=side,
                        fromTimestamp=t+1000,toTimestamp=t+11000),m.ProtoOAGetTickDataRes(ctidTraderAccountId=1,hasMore=False)))
                row['quotes'][str(t)]=dict(rawIndices=indices,observed=None)
            b['symbols'][symbol]=row
        return b

    def test_missing_events_remain_missing(self):
        r=audit(self.fixture())
        self.assertEqual(sum(c['quoteEventsAvailable'] for c in r['contracts']),0)
        self.assertTrue(all(c['currentMinimumMarginEur']=='30' for c in r['contracts']))
        self.assertIsNone(r['brokerNetEur'])
        self.assertFalse(r['fundedReplay'])

    def test_cross_symbol_quote_cannot_be_relabelled(self):
        b=self.fixture();b['symbols']['EURUSD']['symbolId']=999
        with self.assertRaises(CaptureContractError):audit(b)

    def test_bid_ask_index_swap_rejected(self):
        b=self.fixture();b['symbols']['EURUSD']['quotes'][str(CLOCKS[0])]['rawIndices'].reverse()
        with self.assertRaises(CaptureContractError):audit(b)

    def test_missing_quote_cannot_be_fabricated(self):
        b=self.fixture();b['symbols']['EURUSD']['quotes'][str(CLOCKS[0])]['observed']=dict(time=CLOCKS[0]+1000,bid=100,ask=101)
        with self.assertRaises(CaptureContractError):audit(b)

if __name__=='__main__':unittest.main()
