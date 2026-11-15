"""Chart 'fun' metrics computed on label arrays y[diff, step] (0 none, 1-3 lane), 12 steps per beat, 48 per bar."""
import numpy as np
BAR=48
def track_metrics(y,energy=None):
    """y: 4 x S labels for one track. energy: per-step loudness of the stem (optional). Returns dict per difficulty."""
    out=[]
    for d in range(4):
        s=np.where(y[d]>0)[0]; l=y[d][s]-1; m={}
        if len(s)<8: out.append(None); continue
        dl=np.abs(np.diff(l)); gap=np.diff(s)
        m['same']=float((dl==0).mean()); m['step']=float((dl==1).mean()); m['jump']=float((dl==2).mean())
        m['jack']=float(((dl==0)&(gap<=3)).mean())                       # same lane at 16th spacing or faster
        nb=y.shape[1]//BAR; bars=[tuple(zip(*np.where(y[d,b*BAR:(b+1)*BAR]>0),y[d,b*BAR:(b+1)*BAR][y[d,b*BAR:(b+1)*BAR]>0])) for b in range(nb)]
        full=[b for b in bars if b]; 
        from collections import Counter
        c=Counter(full); m['repeat']=float(sum(v for v in c.values() if v>1)/max(1,len(full)))   # share of non-empty bars whose exact pattern recurs
        rhythm=Counter(tuple(x[0] for x in b) for b in full); m['rhythm_repeat']=float(sum(v for v in rhythm.values() if v>1)/max(1,len(full)))
        act=np.array([bool(b) for b in bars]); m['empty_bars']=float(1-act.mean())
        runs=[];r=0
        for a in act:
            if a: r+=1
            elif r: runs.append(r); r=0
        if r: runs.append(r)
        m['phrase_bars']=float(np.mean(runs)) if runs else 0.0                # mean length of consecutive non-empty bars
        if energy is not None:
            e=np.array([energy[b*BAR:(b+1)*BAR].mean() for b in range(nb)]); dens=np.array([len(b) for b in bars],float)
            ok=act|(e>0); m['energy_corr']=float(np.corrcoef(e[ok],dens[ok])[0,1]) if ok.sum()>4 and dens[ok].std()>0 and e[ok].std()>0 else 0.0
        out.append(m)
    return out
def summarize(rows):
    keys=['same','step','jump','jack','repeat','rhythm_repeat','empty_bars','phrase_bars','energy_corr']; res={}
    for d in range(4):
        R=[r[d] for r in rows if r[d] is not None]
        res[d]={k:float(np.mean([x[k] for x in R if k in x])) for k in keys if any(k in x for x in R)}
    return res
