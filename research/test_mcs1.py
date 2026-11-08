"""MCS1 is one frozen three-class research protocol; no historical rescore."""
import unittest,json
from datetime import datetime,timezone
from pathlib import Path
from .mcs1_source import windows,quote_clocks,request_count,protocol
from .mcs1_economics import GAS,DOLLAR,EQUITY,python_decide,frames_and_context,conditional_cost_bps
from .prospective_joint_stat_gate import assess_prospective_weekly

H=3600000
def at(s):return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)
def frame(kind,symbol,prices,peer=None):
    t=at("2026-09-03T17:00:00Z")
    def pack(vals):
        return [{"CloseAt":t-(len(vals)-1-i)*H,"Open":p,"High":p,
                 "Low":p,"Close":p,"TickVolume":200 if i==len(vals)-1 else 100}
                for i,p in enumerate(vals)]
    return {"Mechanism":kind,"Symbol":symbol,"Peer":None,
            "Clock":t,"Target":pack(prices),
            "PeerBars":pack(peer) if peer is not None else None}

class AuthenticMultiClassProtocolChecks(unittest.TestCase):
    def test_price_outcome_blind_protocol_h1_source_request_budget(self):
        p=protocol()
        self.assertTrue(p["locked"])
        self.assertEqual(p["id"],"MCS1")
        self.assertEqual(p["source"]["readOnlyBrokerRequestsExact"],324)
        self.assertEqual(request_count(p),324)
        self.assertEqual(len(windows(p)),53)
        self.assertEqual(len(quote_clocks(p)),26)
        self.assertEqual(p["frequencyPrescreen"]["combinedUpperBound"],105)
        self.assertEqual(len(p["families"]),3)
        self.assertEqual(set(x["symbol"] for x in p["families"]),
                         {"NatGas","USDX","AMD.US"})
        self.assertEqual(p["source"]["historicalWeeks"],52)

    def test_three_distinct_genuine_h1_premises(self):
        gas=frame(GAS,"NatGas",[100,115,118,115,110],
                  peer=[100,100,100])
        gas["Peer"]="USDX"
        self.assertEqual(python_decide(gas),
                         {"Side":-1,"BenchmarkSide":1,"Complete":True})
        dollar=frame(DOLLAR,"USDX",[100,100.1,100.2])
        self.assertEqual(python_decide(dollar),
                         {"Side":1,"BenchmarkSide":1,"Complete":True})
        amd=frame(EQUITY,"AMD.US",[100,100,100,100,101])
        self.assertEqual(python_decide(amd),
                         {"Side":-1,"BenchmarkSide":1,"Complete":True})

    def test_gapless_h1_not_fill_from_prior_or_future(self):
        t=at("2026-09-03T17:00:00Z")
        def bars(vals):
            return {t-(len(vals)-1-i)*H:(t-(len(vals)-1-i)*H,
                   int(v),int(v),int(v),int(v),100)
                   for i,v in enumerate(vals)}
        sample={"NatGas":bars([100,115,118,115,110]),
                "USDX":bars([100,100,100]),
                "AMD.US":bars([100,100,100,100,101])}
        p=protocol();f,contexts,capacity,missing=frames_and_context(sample,p)
        self.assertTrue(any(x["Mechanism"]==GAS and
                            x["Clock"]==t for x in f))
        self.assertTrue(any(x["Mechanism"]==EQUITY and
                            x["Clock"]==t for x in f))
        del sample["NatGas"][t-2*H]
        frames,contexts,_,_=frames_and_context(sample,p)
        self.assertFalse(any(x["Mechanism"]==GAS and
                             x["Clock"]==t for x in frames))

    def test_current_cma2_equity_commission_floor_and_cost_uncertainty(self):
        t=at("2026-09-03T17:00:00Z")
        quotes=[(t-(i+1)*86400000,float(i%3+15)) for i in range(8)]
        bars={"AMD.US":{t:(t,200,200,200,20000,300)}}
        terms={"AMD.US":{"quoteAsset":"USD","commissionType":2,
            "pnlConversionBps":0,"minCommissionType":1,
            "minimumCommissionAsset":"USD","digits":2,
            "minimumUnits":.1,"lotSizeUnits":1.,
            "rateWire":2000000,"minimumWire":2000000}}
        r=conditional_cost_bps("AMD.US",t,bars,{"AMD.US":quotes},terms,"adverse")
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r["currentContractRoundTripCommissionBps"],20)
        self.assertIsNone(r["actualBrokerFillEur"])
        self.assertTrue(r["sourceTimeTariffNotHistorical"])
        self.assertIsNone(conditional_cost_bps("AMD.US",t,bars,
                          {"AMD.US":quotes[:7]},terms,"adverse"))
        self.assertIsNone(conditional_cost_bps("AMD.US",t,bars,
                          {"AMD.US":quotes},dict(terms,**{"AMD.US":dict(
                           terms["AMD.US"],quoteAsset="EUR")}),"adverse"))

    def test_joint_hac_is_both_endpoints_not_legacy_incremental_only(self):
        events=[{"week":w,"grossBps":3.,"benchmarkGrossBps":0.,
                 "centralNetBps":1.,"adverseNetBps":-1.,
                 "adverseBenchmarkNetBps":-3.}
                for w in range(52) for k in range(2)]
        z=assess_prospective_weekly(events,0,26,3)
        self.assertLess(z.cashAdverseWeeklyHacBonferroniLowerBps,0)
        self.assertGreater(z.benchmarkIncrementalWeeklyHacBonferroniLowerBps,0)
        self.assertFalse(z.passesBothProspectiveStatGates)

if __name__=="__main__":unittest.main()
