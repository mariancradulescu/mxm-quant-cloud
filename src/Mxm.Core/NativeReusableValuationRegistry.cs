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
    sealed record Index(NativeValuationPrefix[]? Rows,NativeHistoricalFundingPrefix[]? CompactRows,long[] MaximumThrough)
    {
        public int Length=>MaximumThrough.Length;
        public NativeHistoricalFundingPrefix Witness(int i)=>Rows is not null?Rows[i].Witness:CompactRows![i];
    }
    readonly Dictionary<(string Symbol,string Side),Index> rows;
    public NativeReusableValuationRegistry(IEnumerable<NativeValuationPrefix> evidence,bool compact=false)
    {
        if(compact)
        {
            // Validate every original proof before discarding duplicate row
            // metadata. Stable ordering on equal timestamps is retained.
            var groups=new Dictionary<(string Symbol,string Side),List<NativeHistoricalFundingPrefix>>();
            foreach(var row in evidence)
            {
                if(string.IsNullOrWhiteSpace(row.Symbol)||row.Side is not ("BID" or "ASK")||
                    row.EvidenceSha256.Length!=64||!row.EvidenceSha256.All(Uri.IsHexDigit)||
                    row.Witness.PriceAtCharge(row.Witness.SearchThrough,345600000L) is null)
                    throw new ArgumentException("VALUATION_REGISTRY_UNPROVEN_PREFIX");
                var key=(row.Symbol,row.Side);
                if(!groups.TryGetValue(key,out var list))groups.Add(key,list=new());
                list.Add(row.Witness);
            }
            rows=new();
            foreach(var (key,list) in groups)
            {
                var sorted=list.OrderBy(w=>w.At).ToArray();var maximum=new long[sorted.Length];long last=-1;
                for(int i=0;i<sorted.Length;i++){last=Math.Max(last,sorted[i].SearchThrough);maximum[i]=last;}
                rows.Add(key,new Index(null,sorted,maximum));
            }
            return;
        }
        var input=evidence.ToArray();
        if(input.Any(r=>string.IsNullOrWhiteSpace(r.Symbol)||r.Side is not ("BID" or "ASK")||
            r.EvidenceSha256.Length!=64||!r.EvidenceSha256.All(Uri.IsHexDigit)||
            r.Witness.PriceAtCharge(r.Witness.SearchThrough,345600000L) is null))
            throw new ArgumentException("VALUATION_REGISTRY_UNPROVEN_PREFIX");
        rows=input.GroupBy(r=>(r.Symbol,r.Side)).ToDictionary(g=>g.Key,
            g=>{
                var sorted=g.OrderBy(r=>r.Witness.At).ToArray();var maximum=new long[sorted.Length];long last=-1;
                for(int i=0;i<sorted.Length;i++){last=Math.Max(last,sorted[i].Witness.SearchThrough);maximum[i]=last;}
                return new Index(sorted,null,maximum);
            });
    }
    public static NativeReusableValuationRegistry FromArrayStream(System.IO.Stream stream,
        System.Text.Json.JsonSerializerOptions options)
    {
        IEnumerable<NativeValuationPrefix> Rows()
        {
            var e=System.Text.Json.JsonSerializer.DeserializeAsyncEnumerable<NativeValuationPrefix>(stream,options)
                .GetAsyncEnumerator();
            try
            {
                while(e.MoveNextAsync().AsTask().GetAwaiter().GetResult())
                    yield return e.Current??throw new ArgumentException("VALUATION_REGISTRY_NULL_ROW");
            }
            finally{e.DisposeAsync().AsTask().GetAwaiter().GetResult();}
        }
        return new NativeReusableValuationRegistry(Rows(),compact:true);
    }
    public NativeHistoricalFundingPrefix? At(string symbol,bool bid,long at)
    {
        if(!rows.TryGetValue((symbol,bid?"BID":"ASK"),out var candidates))return null;
        int lo=0,hi=candidates.Length;
        while(lo<hi){int mid=lo+(hi-lo)/2;if(candidates.Witness(mid).At<=at)lo=mid+1;else hi=mid;}
        NativeHistoricalFundingPrefix? latest=null;
        // Same descending traversal and first eligible witness as the original.
        // No temporary list/array; a conflict can return immediately because
        // no remaining witness can restore agreement.
        for(int i=lo-1;i>=0&&candidates.MaximumThrough[i]>=at;i--)
        {
            var witness=candidates.Witness(i);
            if(witness.SearchFrom>at||at>witness.SearchThrough)continue;
            if(latest is null)latest=witness;
            else if(witness.At!=latest.At||witness.Price!=latest.Price)return null;
        }
        return latest is null?null:latest with {SearchThrough=at};
    }
}
