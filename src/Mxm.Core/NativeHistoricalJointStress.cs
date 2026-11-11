namespace Mxm.Core;

internal sealed record NativeHistoricalJointShock(
    string Id, long KnownAt, decimal NetPerUnit, decimal LossPerUnit, decimal PeakPerUnit);

internal static class NativeHistoricalJointStress
{
    internal static NativeHistoricalJointShock[]? Observe(
        NativeProductMarket market, NativeProductMarket? euro, int side, long at)
    {
        const int blocks = 8, blockBars = 3;
        if (euro is null)
            return null;
        var asset = market.M5.TakeLast(blocks * blockBars).ToArray();
        var fx = euro.M5.TakeLast(blocks * blockBars).ToArray();
        if (!Complete(asset, blocks * blockBars, at - 1500L) ||
            !Complete(fx, blocks * blockBars, at - 1500L))
            return null;

        var output = new NativeHistoricalJointShock[blocks];
        var quote = market.Quote;
        decimal mid = (quote.Bid + quote.Ask) / 2m;
        for (int i = 0; i < blocks; i++)
        {
            int first = i * blockBars;
            var prices = asset.Skip(first).Take(blockBars).ToArray();
            var currencies = fx.Skip(first).Take(blockBars).ToArray();
            decimal assetOpen = prices[0].Open;
            decimal fxOpen = currencies[0].Open;
            decimal terminalFx = currencies[^1].Close / fxOpen;
            decimal stressedEur = quote.EurDebit / (currencies.Min(x => x.Low) / fxOpen);
            decimal netQuote = side * mid * (prices[^1].Close / assetOpen - 1m);
            decimal net = netQuote * (netQuote < 0m ? quote.EurDebit : quote.EurCredit) / terminalFx;
            decimal low = side * mid * ((side > 0
                ? prices.Min(x => x.Low) : prices.Max(x => x.High)) / assetOpen - 1m);
            decimal high = side * mid * ((side > 0
                ? prices.Max(x => x.High) : prices.Min(x => x.Low)) / assetOpen - 1m);
            output[i] = new("ALIGNED_H15_" + i, prices[^1].CloseAt, net,
                Math.Max(0m, -low) * stressedEur, Math.Max(0m, high) * stressedEur);
        }
        return output;
    }

    private static bool Complete(NativeClosedMarketBar[] bars, int count, long end) =>
        bars.Length == count && bars[^1].CloseAt == end &&
        bars.All(x => x.Open > 0m && x.Low > 0m && x.CloseAt - x.OpenAt == 300000L) &&
        bars.Zip(bars.Skip(1)).All(pair => pair.First.CloseAt == pair.Second.OpenAt);
}
