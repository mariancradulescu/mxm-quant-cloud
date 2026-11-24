using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static class OwnerSourceHistoryUse
{
    sealed record Contract(string Symbol,string Category,string? QuoteAsset,string? BaseAsset,long AvailableAt,
        string SwapKind,int? SwapCalculationType,ulong[] UnknownSwapValues,JsonElement Fields,Margin? Margin);
    sealed record Margin(decimal BuyEur,decimal SellEur,long AvailableAt,decimal VolumeUnits);
    sealed record Market(string Symbol,string Category,Dictionary<string,long[][]> Bars);
    sealed record Archive(string Source,Market[] Markets);
    sealed record Input(Contract[] Contracts,Archive[] Archives);

    static long? Wire(JsonElement fields,string name)
        =>fields.TryGetProperty(name,out var value) && value.ValueKind==JsonValueKind.Number && value.TryGetInt64(out long number)
            ?number:null;

    static int? Code(JsonElement fields,string name)=>checked((int?)Wire(fields,name));
    static string? Text(JsonElement fields,string name)
        =>fields.TryGetProperty(name,out var value)&&value.ValueKind==JsonValueKind.String?value.GetString():null;
    static bool? Flag(JsonElement fields,string name)
        =>fields.TryGetProperty(name,out var value) && value.ValueKind is JsonValueKind.True or JsonValueKind.False
            ?value.GetBoolean():null;
    static decimal? Rate(JsonElement fields,string name)
        =>fields.TryGetProperty(name,out var value) && value.ValueKind==JsonValueKind.Number && value.TryGetDecimal(out decimal number)
            ?number:null;
    static decimal? Units(JsonElement f,string name)=>Wire(f,name)/100m;

    static bool FeeAndVolumeTermsValidated(Contract c)
    {
        var f=c.Fields;
        if(c.QuoteAsset is null || Units(f,"minVolume") is not decimal minimum ||
            Units(f,"stepVolume") is not decimal step || Units(f,"maxVolume") is not decimal maximum ||
            Units(f,"lotSize") is not decimal lot || Code(f,"commissionType") is not int commissionType ||
            Wire(f,"preciseTradingCommissionRate") is not long rate ||
            Code(f,"minCommissionType") is not int minimumType || Wire(f,"preciseMinCommission") is not long floor ||
            Code(f,"pnlConversionFeeRate") is not int conversion)return false;
        var terms=new NativeObservedContractTerms(c.Symbol,c.QuoteAsset,c.AvailableAt,minimum,step,maximum,lot,
            commissionType,rate,minimumType,floor,Text(f,"minCommissionAsset"),conversion,
            c.SwapCalculationType,Rate(f,"swapLong"),Rate(f,"swapShort"),Code(f,"pipPosition"),
            Code(f,"swapPeriod"),Code(f,"swapTime"),Code(f,"swapRollover3Days"),Flag(f,"chargeSwapAtWeekends"),
            Code(f,"skipSWAPPeriods"));
        try {NativeBrokerContractCosts.Validate(terms,minimum);return true;}
        catch(ArgumentException) {return false;}
    }

    static object Summary(Contract[] contracts)
    {
        var rows=contracts.Select(c=>
        {
            var f=c.Fields;
            return new { Raw=c,Rate=NativePortfolioFunding.InterpretObservedPoint(c.SwapCalculationType,
                Rate(f,"swapLong"),Rate(f,"swapShort"),Code(f,"pipPosition"),Code(f,"digits")),
                VolumeAndFeeValid=FeeAndVolumeTermsValidated(c),
                ScheduleFieldsValid=Code(f,"swapPeriod") is >0 and <=24 &&
                    Code(f,"swapTime") is >=0 and <1440 && Code(f,"swapRollover3Days") is >=0 and <=7 &&
                    Code(f,"skipSWAPPeriods") is >=0 && Flag(f,"chargeSwapAtWeekends").HasValue,
                TradingMode=Code(f,"tradingMode"),TimeZone=Text(f,"scheduleTimeZone")};
        }).ToArray();
        return new
        {
            Count=rows.Length,
            RateTypes=rows.GroupBy(x=>x.Raw.SwapKind).ToDictionary(g=>g.Key,g=>g.Count()),
            MissingOrUnsupportedType=rows.Where(x=>x.Raw.SwapCalculationType is null)
                .GroupBy(x=>x.Raw.Category).ToDictionary(g=>g.Key,g=>g.Count()),
            UnknownEnumValues=rows.SelectMany(x=>x.Raw.UnknownSwapValues).GroupBy(x=>x)
                .ToDictionary(g=>g.Key,g=>g.Count()),
            RateUnitDistributions=rows.Where(x=>x.Rate is not null).GroupBy(x=>x.Rate!.Unit)
                .ToDictionary(g=>g.Key,g=>new {Count=g.Count(),ZeroBoth=g.Count(x=>x.Rate!.Long==0m && x.Rate.Short==0m),
                    NegativeLong=g.Count(x=>x.Rate!.Long<0m),NegativeShort=g.Count(x=>x.Rate!.Short<0m),
                    MinLong=g.Min(x=>x.Rate!.Long),MaxLong=g.Max(x=>x.Rate!.Long),
                    MinShort=g.Min(x=>x.Rate!.Short),MaxShort=g.Max(x=>x.Rate!.Short)}),
            VolumeAndFeeTermsValidated=rows.Count(x=>x.VolumeAndFeeValid),
            RolloverScheduleFieldsValidated=rows.Count(x=>x.ScheduleFieldsValid),
            TimeZones=rows.GroupBy(x=>x.TimeZone??"UNSPECIFIED").ToDictionary(g=>g.Key,g=>g.Count()),
            TradingModes=rows.GroupBy(x=>x.TradingMode?.ToString()??"UNSPECIFIED").ToDictionary(g=>g.Key,g=>g.Count()),
            QuoteCurrencies=rows.GroupBy(x=>x.Raw.QuoteAsset??"UNSPECIFIED").ToDictionary(g=>g.Key,g=>g.Count()),
            CurrencyPairsWithIdentifiedAssets=rows.Count(x=>x.Raw.QuoteAsset is not null && x.Raw.BaseAsset is not null),
            BrokerCategories=rows.GroupBy(x=>x.Raw.Category).ToDictionary(g=>g.Key,g=>g.Count()),
            VerifiedMinimumMarginObservations=rows.Count(x=>x.Raw.Margin is not null),
            BothDirectionsBelowInitialCapital=rows.Count(x=>x.Raw.Margin is { } margin &&
                Math.Max(margin.BuyEur,margin.SellEur)<OwnerRiskAuthority.InitialCapitalEur),
            QualifiedFundingOffers=0,HistoricallyEffectiveIntervals=0
        };
    }

    static NativeClosedMarketBar[] ReadBars(string period,long[][] rows)
    {
        if(!Enum.TryParse<NativeBarTimeframe>(period,out var timeframe) ||
            !Enum.IsDefined(typeof(NativeBarTimeframe),timeframe))
            throw new InvalidDataException("HISTORY_USE_PERIOD");
        long duration=NativeClosedMarketContext.Duration(timeframe);
        long last=-1;
        var bars=new NativeClosedMarketBar[rows.Length];
        for(int i=0;i<rows.Length;i++)
        {
            var row=rows[i];
            if(row.Length!=7 || row[0]<=last || row[1]-row[0]!=duration || row[4]<=0 ||
                row[3]<Math.Max(row[2],row[5]) || row[4]>Math.Min(row[2],row[5]) || row[6]<0)
                throw new InvalidDataException("HISTORY_USE_PRICE_GEOMETRY");
            bars[i]=new(row[0],row[1],row[2]/100000m,row[3]/100000m,row[4]/100000m,
                row[5]/100000m,row[6]);
            last=row[0];
        }
        return bars;
    }

    public static int Run(string input,string output)
    {
        var data=JsonSerializer.Deserialize<Input>(File.ReadAllText(input),
            new JsonSerializerOptions {NumberHandling=JsonNumberHandling.AllowReadingFromString})
            ??throw new InvalidDataException("HISTORY_USE_INPUT");
        var gross=data.Archives.Select(archive=>NativeClosedBarGrossResearch.Compare(archive.Source,
            archive.Markets.Select(m=>new NativeGrossMarket(m.Symbol,m.Category,m.Bars.ToDictionary(
                p=>p.Key,p=>ReadBars(p.Key,p.Value)))).ToArray())).ToArray();
        File.WriteAllText(output,JsonSerializer.Serialize(new
        {
            ContractPoints=Summary(data.Contracts),GrossComparisons=gross,
            Purpose="GROSS_ONLY_CLOSED_BAR_RESEARCH_ON_EXPOSED_HISTORY",
            BrokerFundingKnown=false,FinancedPortfolioReplayExecuted=false
        }));
        return 0;
    }
}
