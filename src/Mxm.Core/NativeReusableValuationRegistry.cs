using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

public sealed record NativeValuationPrefix(string Symbol,string Side,
    NativeHistoricalFundingPrefix Witness,string EvidenceSha256);

// A prefix proves the absence of a later quote only through SearchThrough.
// Reuse never extends that interval and never grants execution authority.
public sealed class NativeReusableValuationRegistry
{
    sealed record Index(NativeValuationPrefix[] Rows,long[] MaximumThrough);
    readonly Dictionary<(string Symbol,string Side),Index> rows;
    public NativeReusableValuationRegistry(IEnumerable<NativeValuationPrefix> evidence)
    {
        var input=evidence.ToArray();
        if(input.Any(r=>string.IsNullOrWhiteSpace(r.Symbol)||r.Side is not ("BID" or "ASK")||
            r.EvidenceSha256.Length!=64||!r.EvidenceSha256.All(Uri.IsHexDigit)||
            r.Witness.PriceAtCharge(r.Witness.SearchThrough,345600000L) is null))
            throw new ArgumentException("VALUATION_REGISTRY_UNPROVEN_PREFIX");
        rows=input.GroupBy(r=>(r.Symbol,r.Side)).ToDictionary(g=>g.Key,
            g=>{
                var sorted=g.OrderBy(r=>r.Witness.At).ToArray();var maximum=new long[sorted.Length];long last=-1;
                for(int i=0;i<sorted.Length;i++){last=Math.Max(last,sorted[i].Witness.SearchThrough);maximum[i]=last;}
                return new Index(sorted,maximum);
            });
    }
    public NativeHistoricalFundingPrefix? At(string symbol,bool bid,long at)
    {
        if(!rows.TryGetValue((symbol,bid?"BID":"ASK"),out var candidates))return null;
        var data=candidates.Rows;int lo=0,hi=data.Length;
        while(lo<hi){int mid=lo+(hi-lo)/2;if(data[mid].Witness.At<=at)lo=mid+1;else hi=mid;}
        var found=new List<NativeValuationPrefix>();
        for(int i=lo-1;i>=0&&candidates.MaximumThrough[i]>=at;i--)
            if(data[i].Witness.SearchFrom<=at&&at<=data[i].Witness.SearchThrough)found.Add(data[i]);
        var usable=found.ToArray();
        if(usable.Length==0)return null;
        var latest=usable[0].Witness;
        // An overlapping prefix claiming no later quote must agree with newer
        // authenticated ticks inside its own interval. Conflicts remain gaps.
        if(usable.Any(r=>r.Witness.At!=latest.At||r.Witness.Price!=latest.Price))return null;
        return latest with {SearchThrough=at};
    }
}
