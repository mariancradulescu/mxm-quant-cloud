namespace Mxm.Core;

public sealed record SequenceFeatureBlock(string Day,string Symbol,string Timeframe,long Clock,long[][] Bars);
public sealed record SequenceForecast(string Day,string Symbol,string Timeframe,string Candidate,
    long AvailableAt,int Side,double ProbabilityUp,int MatureTransitions,string Status);

// SQP1: fixed ordinal transition and duration-hazard hypotheses. No parameter
// search, inversion, closed-study reuse or execution APIs. All fitting events
// are completed bar-to-bar transitions preceding the forecast clock.
public static class SequenceOpportunityResearch
{
    public static SequenceForecast[] Describe(SequenceFeatureBlock[] blocks)
    {
        var output=new List<SequenceForecast>();
        foreach(var block in blocks)
        {
            int minutes=block.Timeframe switch {"M15"=>15,"H1"=>60,_=>throw new ArgumentException("SQP1_TIMEFRAME")};
            var bars=block.Bars.Where(x=>x.Length==7 && x[1]<=block.Clock).OrderBy(x=>x[0]).TakeLast(129).ToArray();
            if(bars.Length!=129 || bars[^1][1]!=block.Clock || bars.Any(x=>x[0]<0 || x[1]-x[0]!=minutes*60000L ||
                x[2]<=0 || x[4]<=0 || x[4]>Math.Min(x[2],x[5]) || x[3]<Math.Max(x[2],x[5]) || x[6]<0) ||
                bars.Select(x=>x[0]).Distinct().Count()!=bars.Length)continue;
            var signs=new int[128];var ages=new int[128];int age=0,prior=0;
            for(int i=0;i<128;i++)
            {
                bool contiguous=bars[i+1][0]==bars[i][1];
                int sign=contiguous?Math.Sign(bars[i+1][5]-bars[i][5]):0;
                age=sign==0?0:sign==prior?age+1:1;prior=sign;signs[i]=sign;ages[i]=age;
            }
            var transitions=new double[,]{{1,1},{1,1}};
            var stay=new double[130];var flip=new double[130];
            Array.Fill(stay,1);Array.Fill(flip,1);int n=0;
            for(int i=0;i<127;i++)
            {
                if(signs[i]==0 || signs[i+1]==0)continue;
                transitions[signs[i]>0?1:0,signs[i+1]>0?1:0]++;
                if(signs[i]==signs[i+1])stay[ages[i]]++;else flip[ages[i]]++;
                n++;
            }
            if(n<96 || signs[^1]==0)continue;
            int steps=60/minutes;
            double up=signs[^1]>0?1:0;
            for(int h=0;h<steps;h++)
                up=(1-up)*transitions[0,1]/(transitions[0,0]+transitions[0,1])+
                    up*transitions[1,1]/(transitions[1,0]+transitions[1,1]);
            Add("ORDINAL_TRANSITION_V1",up);
            var states=new Dictionary<(int Sign,int Age),double>{{(signs[^1],ages[^1]),1}};
            for(int h=0;h<steps;h++)
            {
                var next=new Dictionary<(int,int),double>();
                void Put((int,int) k,double v){next[k]=next.GetValueOrDefault(k)+v;}
                foreach(var (key,mass) in states)
                {
                    int k=Math.Min(key.Age,129);double probability=flip[k]/(flip[k]+stay[k]);
                    Put((-key.Sign,1),mass*probability);Put((key.Sign,Math.Min(129,key.Age+1)),mass*(1-probability));
                }
                states=next;
            }
            Add("DURATION_HAZARD_V1",states.Where(x=>x.Key.Sign>0).Sum(x=>x.Value));
            void Add(string family,double probability)
            {
                int direction=probability>.5?1:probability<.5?-1:0;
                output.Add(new(block.Day,block.Symbol,block.Timeframe,family+"/"+block.Timeframe,
                    block.Clock,direction,probability,n,"EXPOSED_DEVELOPMENT_FORECAST_NOT_QUALIFIED"));
            }
        }
        return output.ToArray();
    }
}
