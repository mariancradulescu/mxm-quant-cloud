import unittest
from .pve3_original_receipt_audit import audit

class Pve3ReceiptOnlyTests(unittest.TestCase):
    def synthetic(self):
        weekly=[];paired=[]
        for w in range(27,53):
            common=dict(week=w,featureKnown=123,labelKnown=120)
            weekly.extend([dict(common,variant="FULL",normalizedPriceMse=.4,zeroPriceMse=.7),
                           dict(common,variant="OWN",normalizedPriceMse=.5,zeroPriceMse=.7)])
            paired.append(dict(week=w,fullMinusOwnPriceMseBenefit=.1,
                               fullMinusZeroPriceMseBenefit=.3))
        weeks={f"2026-W{x:02d}":0 for x in range(19,45)}
        score=dict(FundedCompletionsByIsoWeek=weeks,CompletedRoundTrips=0,NetEur=0,
            ReturnOnCapital=0,MaximumSampledFloatingDrawdown=None,
            Hard21AllEligibleWeeks=False,FullFinancialOutcomeKnown=True,
            NetExpectancyPerTradeEur=None,WinRate=None,MeanWinEur=None,
            MeanLossEur=None,ProfitFactor=None,PayoffRatio=None,MeanRiskMultiple=None,
            ExpectedShortfall5PctEur=None,WorstTradeEur=None,UnknownOrNotApplicable=["NO_FINANCED_ROUND_TRIPS_CASH_IS_NOT_PERFORMANCE"])
        policy=dict(Scorecard=score,Book=dict(ClosedNetEur=0),Completed=0,
                    Qualified=False,IndependentConfirmation=False,NoOrders=True)
        return dict(schema="MXM_PVE3_NEW_ORIGINAL_DISTRIBUTIONAL_PRICE_AND_ECONOMIC_RESEARCH_V1",
            sourceBars=836087,sourceSymbols=[str(x) for x in range(12)],
            weekCensus=[dict(week=w) for w in range(52)],
            independentConfirmation=False,qualified=False,ordersSubmitted=0,
            cloudActivated=False,executionRunId="FAKE_UNIT_TEST",
            protocolSha256="TEST",predictive=dict(weekly=weekly,pairedWeekly=paired),
            native_central={p:policy for p in ("FULL","OWN","CASH")},
            native_adverse={p:policy for p in ("FULL","OWN","CASH")})
    def test_paired_bonferroni_and_cash_na(self):
        out=audit(self.synthetic())
        self.assertEqual(out["predictivePairedBonferroni"]["OWN"]["beneficialWeeks"],26)
        self.assertGreater(out["predictivePairedBonferroni"]["ZERO_PRICE"]["bonferroniDescriptiveLower95"],0)
        self.assertEqual(out["nativeFinancialScorecard"]["adverse"]["incrementalFullVsCashEur"],0)
        self.assertIsNone(out["nativeFinancialScorecard"]["adverse"]["policies"]["FULL"]["scorecard"]["WinRate"])
    def test_mismatched_pair_rejected(self):
        r=self.synthetic();r["predictive"]["pairedWeekly"][0]["fullMinusOwnPriceMseBenefit"]=2
        with self.assertRaisesRegex(ValueError,"PAIRED_MSE"):
            audit(r)
    def test_fabricated_zero_trade_win_rate_rejected(self):
        r=self.synthetic();r["native_adverse"]["FULL"]["Scorecard"]["WinRate"]=1.0
        with self.assertRaisesRegex(ValueError,"NO_TRADE_METRIC"):
            audit(r)

if __name__=="__main__":unittest.main()
