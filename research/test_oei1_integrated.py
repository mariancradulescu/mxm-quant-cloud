"""Purely synthetic verification of OEI1: never broker/alpha evidence."""
import base64,math,unittest
from datetime import datetime,timezone
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .oei1_integrated import run,START,DAY

class Oei1Synthetic(unittest.TestCase):
    def test_full_phase_source_shape_and_no_promotion(self):
        markets=[]
        for symbol_id,(market,base,amp,spread,vol) in enumerate((
            ("EURUSD",1.08,.0005,.00004,1000),
            ("ETHUSD",3000.,12.,.35,1),
            ("SpotBrent",80.,.25,.02,1),
            ("US500",5500.,10.,.7,1)), 1):
            c=e.ProtoOASymbol()
            c.symbolId=symbol_id;c.pipPosition=4
            c.minVolume=int(vol*100);c.stepVolume=int(vol*100)
            c.maxVolume=int(vol*1000);c.lotSize=10000000
            c.preciseTradingCommissionRate=300000000
            c.preciseMinCommission=0;c.commissionType=2
            c.minCommissionType=1;c.minCommissionAsset="USD"
            c.pnlConversionFeeRate=0;c.swapTime=1320;c.swapPeriod=24
            c.digits=5
            days=[]
            for j in range(84):
                d=START+j*DAY
                if datetime.fromtimestamp(d/1000,timezone.utc).weekday()>=5:continue
                bid=[];ask=[]
                for k in range(240):
                    t=d+810*60000+k*30000
                    x=base+amp*(.66*math.sin(k/7+j*.2)+.3*math.cos(k/17+j*.4))
                    bid.append([t,int((x-spread/2)*100000)])
                    ask.append([t,int((x+spread/2)*100000)])
                days.append(dict(Start=d,Bid=bid,Ask=ask))
            markets.append(dict(Name=market,Class=("fx" if market=="EURUSD" else
                "crypto" if market=="ETHUSD" else "energy" if market=="SpotBrent" else "index"),
                MinMarginEur="30",MinimumUnits=str(vol),TickSize=".00001",
                ContractProto=base64.b64encode(c.SerializeToString()).decode(),
                Days=days,M1Count=0))
        result=run(dict(Start=START,End=START+84*DAY,Symbols=markets))
        self.assertEqual(result["Study"],"OEI1_INTEGRATED_3PHASE")
        self.assertGreater(result["Phase1"]["CorpusDecisionSides"],120)
        self.assertFalse(result["Phase1"]["OracleAdverse"]["IsCausalPolicy"])
        self.assertFalse(result["FinalCloudCbotQualified"])
        self.assertEqual(len(result["Phase1"]["ScopeClasses"]),4)
        if "Evaluation" in result["Phase2"]:
            self.assertEqual(len(result["Phase2"]["Evaluation"]["Models"]),4)
            self.assertEqual(result["Phase3"]["adverse"]["CASH"]["ClosedNetEur"],0)
            self.assertEqual(result["Phase3"]["adverse"]["CASH"]["CompletedTrades"],0)
            for item in result["Phase3"]["adverse"].values():
                self.assertIsNone(item["WinRate"] if item["CompletedTrades"]==0 else None)
        self.assertFalse(result["IndependentConfirmation"] if "IndependentConfirmation" in result else False)

if __name__=="__main__":unittest.main()
