using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Core;

// Bounded deterministic joint monetary search. The beam limits computation,
// not legal volume, market universe, or position count. The caller supplies
// existing causal financeability and risk guards for each sequential preview.
internal static class NativeEurMonetaryAllocation
{
    internal sealed record Choice<T>(T[] Items,decimal ValueEur);
    internal static Choice<T> Search<T>(IReadOnlyList<T> candidates,
        Func<T,string> symbol,Func<T,decimal> net,
        Func<T,IReadOnlyList<T>,bool> feasible,int width)
    {
        if(width<1)throw new ArgumentOutOfRangeException(nameof(width));
        var best=new Choice<T>(Array.Empty<T>(),0m);
        var beam=new[]{(Indices:Array.Empty<int>(),Value:0m)};
        // All distinct symbols are eligible at each depth, including all
        // witnessed legal candidate volumes. WAIT is the empty set.
        while(beam.Length>0)
        {
            var next=new Dictionary<string,(int[] Indices,decimal Value)>(StringComparer.Ordinal);
            foreach(var state in beam)
            {
                var items=state.Indices.Select(i=>candidates[i]).ToArray();
                var used=items.Select(symbol).ToHashSet(StringComparer.Ordinal);
                for(int i=0;i<candidates.Count;i++)
                {
                    T item=candidates[i];
                    decimal value=net(item);
                    if(value<=0m||used.Contains(symbol(item))||!feasible(item,items))continue;
                    var indices=state.Indices.Append(i).ToArray();
                    decimal total=state.Value+value;
                    string key=string.Join(",",indices.OrderBy(x=>x));
                    if(!next.ContainsKey(key))next.Add(key,(indices,total));
                    if(total>best.ValueEur)best=new(indices.Select(k=>candidates[k]).ToArray(),total);
                }
            }
            beam=next.Values.OrderByDescending(s=>s.Value)
                .ThenBy(s=>string.Join(",",s.Indices),StringComparer.Ordinal).Take(width).ToArray();
        }
        return best;
    }
}
