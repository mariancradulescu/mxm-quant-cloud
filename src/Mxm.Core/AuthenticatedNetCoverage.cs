using System.Text.Json;

namespace Mxm.Core;

/// <summary>
/// A source-derived broker-cost evidence inventory. Captures which input
/// components are AUTHENTICALLY present for EUR200 replay, not fabricated
/// quantitative costs or a warmed-over strategy.
/// </summary>
public static class AuthenticatedNetCoverage
{
    public static object Examine(JsonElement root)
    {
        // Authentically admitted same native C# source before coverage analysis.
        _=EconomicSourceAdmission.ReadReceipt(root);
        var contracts=root.GetProperty("brokerContract");
        var quotes=root.GetProperty("historicalBidAsk");
        var covered=new List<object>();
        int fullyPriced=0;
        foreach(var symbol in contracts.EnumerateObject()
            .OrderBy(x=>x.Name,StringComparer.Ordinal))
        {
            var x=symbol.Value;
            bool HasNumber(string name) =>
                x.TryGetProperty(name,out var v) && v.ValueKind==JsonValueKind.Number;
            decimal? minUnits=HasNumber("minVolume") ?
                x.GetProperty("minVolume").GetDecimal()/100m:null;
            decimal? stepUnits=HasNumber("stepVolume") ?
                x.GetProperty("stepVolume").GetDecimal()/100m:null;
            bool hasMinVolume=minUnits is >0m && stepUnits is >0m;
            bool commissionMetadata=HasNumber("commissionType") &&
                HasNumber("preciseTradingCommissionRate");
            bool fundingMetadata=HasNumber("swapLong") &&
                HasNumber("swapShort") &&
                HasNumber("swapCalculationType");
            bool conversionMetadata=HasNumber("pnlConversionFeeRate");
            // Only a 60s source snapshot exists; a quote observation does NOT
            // supply the true bid/ask AT EACH future policy entry/exit.
            bool historicalEventQuotesBothTimes=false;
            bool historicalFxAtEachExit=false;
            bool historicBrokerMarginAt200=false;
            bool historicSlippageUpperBound=false;
            bool costComplete=hasMinVolume && commissionMetadata &&
                fundingMetadata && conversionMetadata &&
                historicalEventQuotesBothTimes && historicalFxAtEachExit &&
                historicBrokerMarginAt200 && historicSlippageUpperBound;
            if(costComplete)fullyPriced++;
            var q=quotes.GetProperty(symbol.Name);
            bool bidPresent=q.GetProperty("bid").GetProperty("rows")
                .GetArrayLength()>0;
            bool askPresent=q.GetProperty("ask").GetProperty("rows")
                .GetArrayLength()>0;
            covered.Add(new {
                symbol=symbol.Name,
                brokerMinimumUnits=minUnits,brokerVolumeStepUnits=stepUnits,
                brokerVolumeSpecified=hasMinVolume,
                commissionContractFieldsPresent=commissionMetadata,
                financingContractFieldsPresent=fundingMetadata,
                conversionFeeFieldPresent=conversionMetadata,
                oneMinuteHistoricalBidPresent=bidPresent,
                oneMinuteHistoricalAskPresent=askPresent,
                actualEntryAndExitQuotesAtStrategyEvents=false,
                fundedMinimumBrokerMarginConfirmed=false,
                contemporaneousQuoteCurrencyEurConversionConfirmed=false,
                historicalSlippageUpperBoundConfirmed=false,
                executableNetPathsAdmitted=0,
                status=costComplete?
                    "FEASIBILITY_INPUTS_COMPLETE_NOT_BROKER_FILLS":
                    "ECONOMIC_NET_UNPRICED_WITH_REAL_BROKER_EVIDENCE"
            });
        }
        return new {
            schema="mxm.authenticated-economic-net-availability.v1",
            source="ORIGINAL_PINNED_READ_ONLY_PEPPERSTONE_LIVE_ARCHIVE",
            observedSymbols=covered.Count,
            contracts=covered,
            symbolsWithFullExecutableNetEvidence=fullyPriced,
            historicalExecutableFundedNetEur=null as decimal?,
            hard21CompleteBrokerRoundTrips=0,
            drawdownCertified=false,
            independentConfirmation=false,
            ordersSubmitted=0
        };
    }
}
