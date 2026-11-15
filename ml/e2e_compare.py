"""Compare an auto chart (work/edits/<slot>) with the human chart of the song it was made from, in seconds."""
import sys,os,json,numpy as np; sys.path[:0]=['tools','ml','.']; import chart,features as F
def gem_times(c,lead=0.0):
    f=F.tick_to_sec_fn(c['tempos'],c['tpq']); out={}
    for t in c['tracks']:
        if t['kind']!='catch': continue
        fam=F.FAMILIES[F.family(t['label'])]
        for d in range(4):
            g=np.array([x[0] for x in t['gems'] if x[1]==d],float)
            out.setdefault((fam,d),[]).append(f(g)-lead if len(g) else np.array([]))
    return {k:np.sort(np.concatenate(v)) for k,v in out.items()}
def f1(a,b,tol=0.05):
    if not len(a) or not len(b): return 0,0,0
    hit_a=np.array([np.min(np.abs(b-x))<=tol for x in a]); hit_b=np.array([np.min(np.abs(a-x))<=tol for x in b])
    p,r=hit_a.mean(),hit_b.mean(); return p,r,2*p*r/(p+r+1e-9)
slot,human=sys.argv[1],sys.argv[2]
meta=json.load(open('work/edits/%s/upload.json'%slot)); gen=gem_times(chart.load('work/edits/%s/%s.mid'%(slot,slot)),meta['lead_sec'])
hum=gem_times(chart.load('work/ark/ps3/songs/%s/%s.mid'%(human,human)))
print('model',meta['model'])
for fam in ('drums','bass','vox','synth'):
    row=[]
    for d in range(4):
        g=gen.get((fam,d),np.array([])); h=hum.get((fam,d),np.array([]))
        if fam=='synth': g=np.sort(np.concatenate([gen.get((x,d),np.array([])) for x in ('synth','keys','guitar','other')]))
        p,r,f=f1(g,h); row.append('%s F1 %.2f (n %d vs %d)'%('BIAE'[d],f,len(g),len(h)))
    print(fam.ljust(6),' | '.join(row))
