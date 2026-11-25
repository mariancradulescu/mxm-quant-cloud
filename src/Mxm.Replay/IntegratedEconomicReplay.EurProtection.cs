using System.Text;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed class EerProtectionTape(string directory)
    {
        const long QuoteAgeMs=30_000L;
        record struct Tick(long At,long Raw);
        record struct Span(long Start,long End);
        record struct TickRange(long At,long Low,long High);

        sealed class SideTape(Tick[] ticks,Span[] coverage)
        {
            int LowerBound(long first)
            {
                int lo=0,hi=ticks.Length;
                while(lo<hi)
                {
                    int mid=lo+(hi-lo)/2;
                    if(ticks[mid].At<first)lo=mid+1;
                    else hi=mid;
                }
                return lo;
            }

            public bool Covers(long from,long through)
            {
                if(through<from)return true;
                int lo=0,hi=coverage.Length;
                while(lo<hi)
                {
                    int mid=lo+(hi-lo)/2;
                    if(coverage[mid].End<from)lo=mid+1;
                    else hi=mid;
                }
                return lo<coverage.Length && coverage[lo].Start<=from && coverage[lo].End>=through;
            }

            public Tick? QuoteAt(long at)
            {
                int i=LowerBound(at+1)-1;
                if(i<0 || at-ticks[i].At>QuoteAgeMs || !Covers(ticks[i].At,at))return null;
                var latest=ticks[i];
                while(--i>=0 && ticks[i].At==latest.At)
                    if(ticks[i].Raw!=latest.Raw)return null;
                return latest;
            }

            public IEnumerable<TickRange> Events(long from,long through)
            {
                int i=LowerBound(from);
                while(i<ticks.Length && ticks[i].At<=through)
                {
                    var first=ticks[i++];
                    long lo=first.Raw,hi=first.Raw;
                    while(i<ticks.Length && ticks[i].At==first.At)
                    {
                        lo=Math.Min(lo,ticks[i].Raw);
                        hi=Math.Max(hi,ticks[i++].Raw);
                    }
                    yield return new TickRange(first.At,lo,hi);
                }
            }
        }

        readonly Dictionary<(string Symbol,bool Bid),SideTape> sides=new();

        static void ReadPairs(string path,Action<long,long> read)
        {
            if(!File.Exists(path))return;
            using var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read,256*1024,FileOptions.SequentialScan);
            if(file.Length%16!=0)throw new InvalidDataException("EER_PROTECTION_TAPE_RECORD_LENGTH");
            using var reader=new BinaryReader(file);
            for(long i=0;i<file.Length;i+=16)read(reader.ReadInt64(),reader.ReadInt64());
        }

        SideTape Side(string symbol,bool bid)
        {
            var key=(symbol,bid);
            if(sides.TryGetValue(key,out var existing))return existing;
            string prefix=GeneralSha(Encoding.UTF8.GetBytes(symbol))+(bid?"-bid-":"-ask-");
            var ticks=new List<Tick>();
            var spans=new List<Span>();
            foreach(var lane in new[]{"full-session","eer1"})
            {
                string file=Path.Combine(directory,prefix+lane);
                ReadPairs(file+".ticks",(at,raw)=>
                {
                    if(at<=0 || raw<=0)throw new InvalidDataException("EER_PROTECTION_TICK");
                    ticks.Add(new Tick(at,raw));
                });
                ReadPairs(file+".coverage",(from,to)=>
                {
                    if(from<=0 || to<from)throw new InvalidDataException("EER_PROTECTION_COVERAGE");
                    spans.Add(new Span(from,to));
                });
            }
            var merged=new List<Span>();
            foreach(var span in spans.OrderBy(x=>x.Start))
            {
                if(merged.Count==0 || span.Start>merged[^1].End+1)merged.Add(span);
                else if(span.End>merged[^1].End)merged[^1]=merged[^1] with {End=span.End};
            }
            ticks.Sort((a,b)=>a.At.CompareTo(b.At));
            var result=new SideTape(ticks.ToArray(),merged.ToArray());
            sides.Add(key,result);
            return result;
        }

        public SourceQuote? QuoteAt(string symbol,long at)
        {
            if(Side(symbol,true).QuoteAt(at) is not { } bid || Side(symbol,false).QuoteAt(at) is not { } ask || ask.Raw<bid.Raw)
                return null;
            return new(at,bid.At,ask.At,bid.Raw/100_000m,ask.Raw/100_000m,null!);
        }

        public object AuditWitness(HistoricalStopWitness witness)
        {
            if(witness.Side is not (1 or -1) || witness.StopDistance<=0m ||
                witness.OriginalFillAt>=witness.OriginalCloseAt || QuoteAt(witness.Symbol,witness.OriginalFillAt) is not { } entry)
                throw new InvalidDataException("EER_ORIGINAL_STOP_ENTRY_QUOTE_REQUIRED");
            decimal stop=(witness.Side>0?entry.Ask:entry.Bid)-witness.Side*witness.StopDistance;
            var tradeSide=Side(witness.Symbol,witness.Side>0);
            var first=tradeSide.Events(witness.OriginalFillAt+1,witness.OriginalCloseAt)
                .FirstOrDefault(t=>NativeExecutableEconomics.TradeStopReached(witness.Side,
                    (witness.Side>0?t.Low:t.High)/100_000m,stop));
            if(first.At!=witness.FirstTradeTouchAt || !tradeSide.Covers(witness.OriginalFillAt+1,witness.OriginalCloseAt))
                throw new InvalidDataException("EER_ORIGINAL_STOP_TRIGGER_MISMATCH");
            return new {witness.Symbol,witness.Side,witness.OriginalFillAt,witness.OriginalCloseAt,
                ObservedTriggerAt=first.At,EarlierByMilliseconds=witness.OriginalCloseAt-first.At,
                TriggerQuoteSide=witness.Side>0?"BID":"ASK",TriggerMethod="Trade",ModeledFillAtOriginalStopWitness=false};
        }

        public Ucp1ProtectionObservation GridCoverage(NativeUnifiedPortfolioEngine book,long at)
            =>new(false,Array.Empty<Ucp1StopTouch>(),Array.Empty<Ucp1StopQuote>(),
                book.ProtectionWatches().Where(w=>!Side(w.Symbol,w.Side>0).Covers(w.OpenedAt+1,at))
                    .Select(w=>w.PositionId).ToArray());

        public void Between(NativeUnifiedPortfolioEngine book,long through,EerEvidence source,
            Dictionary<string,EerStream> markets,string scenario,decimal stress)
        {
            while(book.LastObservationAt>0 && book.LastObservationAt<through)
            {
                var watches=book.ProtectionWatches();
                long at=long.MaxValue;
                var touches=new List<Ucp1StopTouch>();
                var fills=new List<Ucp1StopQuote>();
                var marks=new Dictionary<(string,long),Ucp1MarketFrame?>();
                Ucp1MarketFrame? Mark(string name,long clock)
                {
                    var key=(name,clock);
                    if(!marks.TryGetValue(key,out var mark))
                        marks.Add(key,mark=source.ProtectionMark(this,markets[name].Source,clock,stress));
                    return mark;
                }

                void Select(long clock)
                {
                    if(clock==at)return;
                    at=clock;
                    touches.Clear();
                    fills.Clear();
                }

                foreach(var watch in watches)
                {
                    long from=Math.Max(book.LastObservationAt+1,watch.FillNotBefore??watch.OpenedAt+1);
                    var side=Side(watch.Symbol,watch.Side>0);
                    foreach(var tick in side.Events(from,Math.Min(through,at)))
                    {
                        if(watch.TriggerAt is long trigger)
                        {
                            if(tick.Low!=tick.High || Mark(watch.Symbol,tick.At) is not { } mark ||
                                NativeExecutableEconomics.ExitPrice(watch.Side>0?mark.Quote.Bid:mark.Quote.Ask,
                                    watch.Side,mark.SlippagePerSideQuote)<=0m)continue;
                            Select(tick.At);
                            fills.Add(new(watch.PositionId,side.Covers(trigger,tick.At)));
                        }
                        else
                        {
                            decimal far=(watch.Side>0?tick.Low:tick.High)/100_000m;
                            if(!NativeExecutableEconomics.TradeStopReached(watch.Side,far,watch.Stop))continue;
                            Select(tick.At);
                            touches.Add(new(watch.PositionId,tick.Low/100_000m,tick.High/100_000m,
                                side.Covers(watch.OpenedAt+1,tick.At)));
                        }
                        break;
                    }
                }
                if(at==long.MaxValue)return;
                var frames=watches.Select(w=>w.Symbol).Distinct(StringComparer.Ordinal)
                    .Select(n=>Mark(n,at)).OfType<Ucp1MarketFrame>().ToArray();
                source.Advance(book,new Ucp1Frame(at,frames)
                {
                    Protection=new(true,touches.ToArray(),fills.ToArray(),Array.Empty<string>())
                },markets,scenario,stress);
            }
        }
    }
}
