using System.Text.Json;
namespace Mxm.Core;

// Shared USD-quoted FX monetary terms. Existing closed study remains immutable.
public sealed class BrokerQuoteNet
{
    readonly JsonElement c;
    public BrokerQuoteNet(JsonElement contract){c=contract;
        if(Min<=0 || Step<=0 || Max<Min || D("lotSize")<=0 || D("preciseTradingCommissionRate")<0 || D("preciseMinCommission")<0 || D("pnlConversionFeeRate")<0 || D("pipPosition")!=4 || (D("distanceSetIn")!=1 && D("distanceSetIn")!=2))throw new ArgumentException("INVALID_BROKER_TERMS");
    }
    public decimal D(string k)=>c.GetProperty(k).GetDecimal();
    public decimal Min=>D("minVolume")/100m;
    public decimal Step=>D("stepVolume")/100m;
    public decimal Max=>D("maxVolume")/100m;
    public decimal MinimumTarget(decimal price)=>MinimumDistance(price,"tpDistance");
    public decimal MinimumStop(decimal price)=>MinimumDistance(price,"slDistance");
    decimal MinimumDistance(decimal price,string field)
    {
        decimal raw=D(field);
        return (int)D("distanceSetIn")==1?raw/(decimal)Math.Pow(10,(int)D("digits")):price*raw/10000m;
    }
    public decimal CommissionUsd(decimal units,decimal price,decimal eurAsk)
    {
        decimal r=D("preciseTradingCommissionRate"),lot=D("lotSize")/100m;
        decimal usd=(int)D("commissionType") switch {1=>r/100000000m*units*price/1000000m,
            2 or 4=>r/100000000m*units/lot,3=>r/100000m/100m*units*price,_=>throw new ArgumentException("COMMISSION_TYPE")};
        decimal floor=D("preciseMinCommission")/100000000m;
        if((int)D("minCommissionType")==1 && c.GetProperty("minCommissionAsset").GetString()=="EUR")floor*=eurAsk;
        else if((int)D("minCommissionType")==1 && c.GetProperty("minCommissionAsset").GetString()!="USD")throw new ArgumentException("MINIMUM_CCY");
        return Math.Max(usd,floor);
    }
    public decimal CarryReserveUsd(decimal units,decimal price)
    {
        // Every new model enters >=06 UTC and exits <=18 UTC, same weekday.
        // A broker-observed DAILY schedule outside this interval implies no
        // current-schedule charge; never infer this from a missing field.
        if(c.TryGetProperty("swapPeriod",out var period) && period.ValueKind==JsonValueKind.Number && period.GetInt32()==24 &&
            c.TryGetProperty("swapTime",out var time) && time.ValueKind==JsonValueKind.Number &&
            time.GetInt32()>=0 && time.GetInt32()<1440 && (time.GetInt32()<360 || time.GetInt32()>1080))return 0;
        decimal worst=3m*Math.Max(Math.Abs(D("swapLong")),Math.Abs(D("swapShort")));
        return (int)D("swapCalculationType") switch {0=>worst*0.0001m*units,1=>worst/100m/360m*price*units,_=>throw new ArgumentException("SWAP_TYPE")};
    }
    public decimal FxFeeRate=>D("pnlConversionFeeRate")/10000m;
    public static decimal Eur(decimal usd,decimal eurBid,decimal eurAsk)=>usd>=0?usd/eurAsk:usd/eurBid;
}
